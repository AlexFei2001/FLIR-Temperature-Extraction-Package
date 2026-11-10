"""Standalone FLIR decoder, copied from the existing thesis thermal adapter.

Numerical functions retain the original expressions, calibration requirements,
ROI-independent native orientation and explicit byte-order selection.
This module does not import the thesis project or any segmentation modules.
"""
from pathlib import Path
import hashlib
import io
import json
import subprocess
import numpy as np
from PIL import Image

VERSION = "1.0.1"

def _preview(path):
    # Do not apply EXIF transpose, zoom, palette inversion or inferred warps.
    with Image.open(path) as im:
        return np.array(im.convert("RGB"))


FLIR_FIELDS = ("Emissivity", "ObjectDistance", "ReflectedApparentTemperature", "AtmosphericTemperature",
               "IRWindowTemperature", "IRWindowTransmission", "RelativeHumidity", "PlanckR1", "PlanckR2",
               "PlanckB", "PlanckF", "PlanckO", "RawThermalImageWidth", "RawThermalImageHeight",
               "RawThermalImageType", "RawValueMedian", "AtmosphericTransAlpha1", "AtmosphericTransAlpha2",
               "AtmosphericTransBeta1", "AtmosphericTransBeta2", "AtmosphericTransX", "Make", "Model", "DateTimeOriginal")


def _tool(command, args):
    if not isinstance(command, list) or not command or not all(isinstance(s, str) for s in command):
        raise ValueError("External tool must be a nonempty argv list, never a shell command")
    result = subprocess.run(command + args, capture_output=True, timeout=120, check=False)
    if result.returncode:
        raise ValueError(result.stderr.decode("utf-8", errors="replace")[-1600:])
    return result.stdout


def flir_raw_to_celsius(raw, m):
    """Planck inversion with metadata emissivity, reflection and two half-paths.

    Atmosphere uses the FLIR fitted water-vapour transmission coefficients.
    The window lies between two equal atmospheric paths. All inputs are recorded;
    software spot-checks are still required before physical interpretation.
    """
    required = FLIR_FIELDS[:12] + FLIR_FIELDS[16:21]
    if any(k not in m for k in required):
        raise ValueError("Missing FLIR calibration/environment metadata")
    m = {k: float(v) if k in required else v for k, v in m.items()}
    e, distance, rh, window = (m[k] for k in ("Emissivity", "ObjectDistance", "RelativeHumidity", "IRWindowTransmission"))
    if not (0 < e <= 1 and distance >= 0 and 0 <= rh <= 1 and 0 < window <= 1):
        raise ValueError("Invalid FLIR emissivity, distance, fractional humidity or window transmission")
    r1, r2, b, f, offset = (m[k] for k in ("PlanckR1", "PlanckR2", "PlanckB", "PlanckF", "PlanckO"))
    if min(r1, r2, b) <= 0 or not np.isfinite([float(m[k]) for k in required]).all():
        raise ValueError("Invalid FLIR Planck/environment parameters")
    ta = m["AtmosphericTemperature"]
    water = rh * np.exp(1.5587 + .06939 * ta - .00027816 * ta**2 + .00000068455 * ta**3)
    x = m["AtmosphericTransX"]
    tau = x * np.exp(-np.sqrt(distance / 2) * (m["AtmosphericTransAlpha1"] + m["AtmosphericTransBeta1"] * np.sqrt(water)))
    tau += (1 - x) * np.exp(-np.sqrt(distance / 2) * (m["AtmosphericTransAlpha2"] + m["AtmosphericTransBeta2"] * np.sqrt(water)))
    if not 0 < tau <= 1:
        raise ValueError("FLIR fitted atmospheric transmission outside (0,1]")
    def radiance(tc):
        if tc <= -273.15:
            raise ValueError("Temperature below absolute zero")
        return r1 / (r2 * (np.exp(b / (tc + 273.15)) - f)) - offset
    q = np.asarray(raw, dtype=np.float64) / (e * tau * window * tau)
    q -= ((1 - e) / e) * radiance(m["ReflectedApparentTemperature"])
    q -= ((1 - tau) / (e * tau)) * radiance(ta)
    q -= ((1 - window) / (e * tau * window)) * radiance(m["IRWindowTemperature"])
    q -= ((1 - tau) / (e * tau * window * tau)) * radiance(ta)
    if np.any(q + offset <= 0):
        raise ValueError("FLIR Planck inversion has nonpositive corrected signal")
    arg = r1 / (r2 * (q + offset)) + f
    if np.any(arg <= 1) or not np.isfinite(arg).all():
        raise ValueError("FLIR Planck inversion invalid; check byte order and calibration")
    t = b / np.log(arg) - 273.15
    return t, {"half_path_transmission": float(tau), "total_atmosphere_transmission": float(tau * tau)}


def _flir(path, spec, tools):
    cmd = tools.get("exiftool_command")
    if cmd is None:
        raise ValueError("FLIR radiometry requires tools.exiftool_command (argv list)")
    m = json.loads(_tool(cmd, ["-j", "-n"] + ["-" + k for k in FLIR_FIELDS] + [str(path)]))[0]
    if any(k not in m for k in ("RawThermalImageWidth", "RawThermalImageHeight", "RawThermalImageType")):
        raise ValueError("JPEG has FLIR metadata but no raw thermal image; context images cannot supply temperatures")
    payload = _tool(cmd, ["-b", "-RawThermalImage", str(path)])
    with Image.open(io.BytesIO(payload)) as im:
        a = np.array(im)
    if a.ndim != 2 or a.dtype != np.uint16 or a.shape != (int(m["RawThermalImageHeight"]), int(m["RawThermalImageWidth"])):
        raise ValueError("FLIR raw image must be an exact-size 16-bit single-channel matrix")
    order = spec.get("raw_byte_order")
    if order not in ("native", "swap16"):
        raise ValueError("FLIR requires explicit raw_byte_order: native or swap16; no silent byte-order guess")
    if order == "swap16":
        a = a.byteswap()
    original = dict(m)
    overrides = spec.get("measurement_overrides", {})
    allowed = set(FLIR_FIELDS[:7])
    if not set(overrides) <= allowed:
        raise ValueError("Unsupported FLIR measurement override")
    m.update(overrides)
    t, physics = flir_raw_to_celsius(a, m)
    meta = {"decoder": "FLIR_ExifTool_raw_plus_metadata_Planck", "raw_byte_order": order,
            "raw_payload_sha256": hashlib.sha256(payload).hexdigest(), "original_parameters": original,
            "effective_parameters": m, "measurement_overrides": overrides, **physics,
            "exiftool_version": _tool(cmd, ["-ver"]).decode().strip(),
            "radiometry_validation": "metadata_corrected_estimate; FLIR_software_numeric_check_pending"}
    return t, _preview(path), meta


def extract_frame(path, byte_order, exiftool_command, measurement_overrides=None):
    """Return native float64 Celsius, source-display RGB and extraction metadata.

    raw uint16 values are measurement counts; source-display pixels are not
    temperatures. No flips, EXIF rotation, resizing or palette inversion occur.
    """
    path = Path(path).resolve()
    if not path.is_file():
        raise ValueError("Input file does not exist: " + str(path))
    t, display, metadata = _flir(path, {"raw_byte_order": byte_order,
        "measurement_overrides": measurement_overrides or {}}, {"exiftool_command": exiftool_command})
    if not np.isfinite(t).all():
        raise ValueError("Temperature conversion returned nonfinite values")
    t = np.ascontiguousarray(t, dtype=np.float64)
    t.setflags(write=False)
    metadata.update(temperature_units="C", shape_hw=list(t.shape),
        temperature_dtype=str(t.dtype), orientation="decoded native grid; no rotation, flip or resizing",
        absolute_numeric_validation_complete=False, exporter_version=VERSION)
    return t, display, metadata

# FLIR Temperature Exporter 1.0.1

**English** | [Italiano](README_IT.md) | [中文](README_中文.md)

Extract native-resolution Celsius temperature matrices from radiometric FLIR JPEGs, individually or in batches. The package runs independently using Python, NumPy, Pillow and ExifTool.

Download the [ready-to-share v1.0.1 ZIP](https://github.com/AlexFei2001/FLIR-Temperature-Extraction-Package/raw/refs/heads/main/dist/FLIR_Temperature_Exporter_v1.0.1_2026-11-10.zip), or use **Code → Download ZIP** in the repository. The repository archive contains all source files and documentation. To run the tool from the dedicated package archive, extract its entire folder first.

## Quick start

1. Open a terminal in the extracted tool folder using Python 3.10–3.14, then install the Python dependencies:

```text
python -m pip install -r requirements.txt
```

2. Install [ExifTool](https://exiftool.sourceforge.net/install.html). On Windows rename `exiftool(-k).exe` to `exiftool.exe` and keep its companion `exiftool_files` directory. The full Perl distribution instead requires Perl and its accompanying `lib` directory.

3. Copy `config.example.json` to `config.json` (on PowerShell: `Copy-Item config.example.json config.json`; on Linux/macOS: `cp config.example.json config.json`). Set `exiftool_command` to your local executable and **verify raw byte order** for your camera/files. For example:

```json
{
  "exiftool_command": ["C:/Tools/ExifTool/exiftool.exe"],
  "raw_byte_order": "swap16",
  "measurement_overrides": {}
}
```

Use forward slashes in JSON paths. Keep an executable path containing spaces as one string, without adding quotation marks inside that string. Relative file paths are resolved from the configuration file's folder. If ExifTool is on PATH, `["exiftool"]` works. `measurement_overrides: {}` preserves the file's original settings.

4. Check dependencies, then extract one image or a whole folder:

```text
python extract_flir.py --check --config config.json
python extract_flir.py --input "D:/FLIR photos/IR_0016.jpg" --output "D:/FLIR exports" --config config.json --csv
python extract_flir.py --input "D:/FLIR photos" --output "D:/FLIR exports" --config config.json --csv
```

The example's `swap16` setting was used for four specific FLIR T1020 JPEGs. It is **not a universal FLIR setting**. `native` leaves decoded uint16 values unchanged; `swap16` swaps each value's two bytes. Wrong byte order can produce errors or plausible-looking but incorrect temperatures. Check the same pixels and measurement settings against FLIR software; do not choose byte order by visual appearance alone. `--check` confirms dependencies/configuration can be read; it does not validate temperatures or byte order.

Paths with spaces must be quoted. Use `--recursive` for nested folders; `--input` also accepts multiple files/folders. `--csv` is optional. For the full Perl distribution use e.g. `--perl perl --exiftool vendor/exiftool/exiftool --byte-order swap16`. Commands are argv lists without shell interpolation.

Alternatively run `python extract_flir.py --interactive`; Windows users may double-click `run_windows.cmd`. Conda users should activate their environment and run `python` in that terminal. The interactive entry reads a local `config.json` if present. `--help` lists all options.

## Output and API

Each batch creates a unique timestamp/UUID subfolder. Inputs and previous results are never overwritten. Each successful image produces:

- `temperature.npy`: float64 Celsius, shape `(height, width)`, native grid without resizing/flipping/rotation.
- `temperature.csv` when requested: the same Celsius matrix, no header/index, comma separator, decimal point `.`, 17 significant digits.
- `radiometry.json`: original/effective measurement parameters, source/payload/temperature hashes, byte order, units and provenance.
- `preview_gray.png`: native-size 8-bit display at 1st–99th percentiles, **not temperature values**. Display clipping does not alter numerical data.
- `source_display.png`: the JPEG's visible display, which may contain borders, text or fusion and need not share thermal-grid coordinates.

`summary.csv/json` logs successes and failures, and `manifest.json` records configuration, versions and output hashes. Ordinary JPEGs or incomplete calibration records produce errors, never invented temperatures; a mixed batch continues. Exit codes: 0 all successful with unchanged sources; 2 per-file errors/source changes; 1 configuration or tool startup failure.

Example directory structure:

```text
FLIR exports/
└── <UTC timestamp_random ID>/
    ├── manifest.json
    ├── summary.csv
    ├── summary.json
    └── 0001_IR_0016/
        ├── temperature.npy
        ├── temperature.csv       # when --csv is supplied
        ├── radiometry.json
        ├── preview_gray.png
        └── source_display.png
```

CSV matrices can be imported into Excel with a comma delimiter and `.` decimal separator. Image subfolders are numbered so identical filenames from different input directories remain distinct. The 1st–99th percentile preview range affects visualization only; exported temperatures retain the full range.

```python
import numpy as np
T = np.load("temperature.npy", allow_pickle=False)
temperature_at_x10_y20 = T[20, 10]  # zero-based coordinates, Celsius
```

`read_temperature_example.py` demonstrates array and single-pixel access. You can also import `extract_frame` from `flir_reader.py`; it returns `(temperature_c, source_display_rgb, metadata)` and takes an explicit byte order and ExifTool argv list.

## Measurement model and limitations

The decoder preserves the existing thesis adapter's Planck inversion and emissivity/reflection/atmosphere/window corrections. It requires the original metadata and assumes two equal atmospheric half-paths with the window between them. Missing camera calibration constants are rejected rather than replaced by generic defaults. It reads embedded radiometry, not palette colors.

Optional `measurement_overrides` accepts only the following fields. Original and effective values are recorded; calibration constants cannot be overridden.

| Field | Meaning and units |
|---|---|
| `Emissivity` | Emissivity, greater than 0 and at most 1 |
| `ObjectDistance` | Object distance in metres, nonnegative |
| `RelativeHumidity` | Fraction from 0 to 1; 60% is `0.6` |
| `ReflectedApparentTemperature` | Reflected apparent temperature, °C |
| `AtmosphericTemperature` | Atmospheric temperature, °C |
| `IRWindowTemperature` | Infrared window temperature, °C |
| `IRWindowTransmission` | Window transmission, greater than 0 and at most 1 |

Outputs are metadata-corrected estimates, **not independently calibrated absolute temperatures**. `absolute_numeric_validation_complete` remains false. Validate new camera/file types numerically against vendor software at matching coordinates/settings. Float64 storage precision does not imply equal sensor accuracy. This tool does not support every FLIR file format, ordinary photos, stripped JPEG exports, BMT or DJI inputs.

## Troubleshooting

- **ExifTool not found:** check `exiftool_command`, PATH and the companion `exiftool_files`/`lib` folder.
- **No raw thermal image:** use the original radiometric JPEG. A visible-light image, screenshot or palette-only export cannot supply a Celsius matrix.
- **Missing calibration/environment metadata:** the file is not fully supported; use complete original data or a temperature export from vendor software.
- **Nonpositive corrected signal / invalid Planck inversion:** verify raw byte order and measurement settings. Do not treat an unsuccessful conversion as a valid result.
- **Raw image is not exact-size uint16:** verify file type and install the specified Pillow version.
- **Some inputs fail:** examine `summary.csv`; other images continue processing.
- **Visible JPEG and thermal matrix have different dimensions:** borders, scales or fusion may be present in the JPEG. Pixel coordinates must be checked on the thermal grid.

## Tests and provenance

```text
python -m pip install -r requirements-test.txt
python -m pytest tests -q
```

`requirements-tested.txt` pins the tested NumPy/Pillow versions. See `VALIDATION.md` for real-file/regression coverage and `SOURCE_PROVENANCE.json` for copied core-function provenance. No private images, temperature dataset, external executables or local-machine configuration are distributed.

The release was tested on Windows with Python 3.10.20, NumPy 2.2.6, Pillow 12.2.0 and ExifTool 13.61. The standalone suite has 17 cases; the original adapter adds 20 regression cases. Four real FLIR T1020 files reproduced the archived matrices exactly, including full CSV round trips. These checks establish implementation consistency, not absolute thermometric calibration. See [VALIDATION.md](VALIDATION.md).

## License

The package uses the repository's [MIT license](LICENSE). ExifTool and Python libraries are installed separately and retain their own licenses.

Official references: [ExifTool installation](https://exiftool.sourceforge.net/install.html), [FLIR tags and raw image byte order](https://exiftool.sourceforge.net/TagNames/FLIR.html), [Pillow Python support](https://pillow.readthedocs.io/en/stable/installation/python-support.html). Third-party programs/libraries retain their respective licenses and are installed separately.

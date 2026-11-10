"""Batch-export radiometric FLIR JPEGs without requiring the thesis project."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import re
import shutil
import sys
import uuid

import numpy as np
from PIL import Image

from flir_reader import VERSION, extract_frame, _tool


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def array_hash(a):
    return hashlib.sha256(f'{a.dtype.str}:{a.shape}:'.encode('ascii') + np.ascontiguousarray(a).tobytes()).hexdigest()


def write_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False), encoding='utf8')


def collect_inputs(inputs, recursive=False):
    result = set()
    for item in inputs:
        path = Path(item).expanduser().resolve()
        if path.is_file():
            if path.suffix.lower() not in ('.jpg', '.jpeg'):
                raise ValueError('Expected a FLIR radiometric .jpg/.jpeg: ' + str(path))
            result.add(path)
        elif path.is_dir():
            files = path.rglob('*') if recursive else path.iterdir()
            result.update(p.resolve() for p in files if p.is_file() and p.suffix.lower() in ('.jpg', '.jpeg'))
        else:
            raise ValueError('Input path does not exist: ' + str(path))
    if not result:
        raise ValueError('No .jpg/.jpeg input files were found')
    return sorted(result, key=lambda p: str(p).casefold())


def load_options(args):
    config_path = Path(args.config).expanduser().resolve() if args.config else None
    config = json.loads(config_path.read_text(encoding='utf-8-sig')) if config_path else {}
    allowed = {'exiftool_command', 'raw_byte_order', 'measurement_overrides'}
    if not isinstance(config, dict) or set(config)-allowed:
        raise ValueError('Unknown config keys; allowed: ' + ', '.join(sorted(allowed)))
    command = config.get('exiftool_command', [shutil.which('exiftool') or shutil.which('exiftool.exe') or 'exiftool'])
    if args.exiftool:
        command = [args.perl, args.exiftool] if args.perl else [args.exiftool]
    elif args.perl:
        raise ValueError('--perl must be combined with --exiftool pointing to the Perl script')
    if not isinstance(command, list) or not command or not all(isinstance(x, str) and x for x in command):
        raise ValueError('exiftool_command must be a nonempty JSON list of executable/argument strings')
    # Configured relative file paths are relative to the config, not this PC.
    if config_path and not args.exiftool:
        command = [str((config_path.parent / s).resolve()) if not Path(s).is_absolute() and (config_path.parent / s).is_file() else s for s in command]
    order = args.byte_order or config.get('raw_byte_order')
    if order not in ('native', 'swap16'):
        raise ValueError('Choose --byte-order native or swap16 explicitly; do not guess for an unverified camera/file format')
    overrides = config.get('measurement_overrides', {})
    if not isinstance(overrides, dict):
        raise ValueError('measurement_overrides must be a JSON object')
    if set(overrides)-{'Emissivity', 'ObjectDistance', 'RelativeHumidity', 'ReflectedApparentTemperature',
                       'AtmosphericTemperature', 'IRWindowTemperature', 'IRWindowTransmission'}:
        raise ValueError('Unsupported measurement override; calibration constants cannot be overridden')
    return command, order, overrides


def preview(t):
    low, high = map(float, np.percentile(t, [1, 99]))
    a = np.zeros(t.shape, dtype=np.uint8)
    if high > low:
        a = np.rint(np.clip((t-low)/(high-low), 0, 1)*255).astype(np.uint8)
    return a, [low, high]


def export_batch(inputs, output_root, command, byte_order, overrides=None, recursive=False, csv_export=False):
    inputs = collect_inputs(inputs, recursive)
    version = _tool(command, ['-ver']).decode('utf8').strip()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ_') + uuid.uuid4().hex[:8]
    out = Path(output_root).expanduser().resolve() / stamp
    out.mkdir(parents=True, exist_ok=False)
    manifest = {'status': 'running', 'created_utc': datetime.now(timezone.utc).isoformat(),
        'exporter_version': VERSION, 'python': sys.version, 'platform': platform.platform(),
        'software': {p: importlib.metadata.version(p) for p in ['numpy', 'Pillow']},
        'exiftool_command': command, 'exiftool_version': version, 'raw_byte_order': byte_order,
        'measurement_overrides': overrides or {}, 'csv_export': csv_export,
        'temperature_units': 'C', 'csv_coordinates': 'row=y, column=x, no header/index; same shape as NPY',
        'absolute_numeric_validation_complete': False, 'files': []}
    write_json(out/'manifest.json', manifest)
    rows = []
    print('OUTPUT_DIRECTORY=' + str(out), flush=True)
    for index, source in enumerate(inputs, 1):
        row = {'input_path': str(source), 'status': 'error', 'output_folder': None}
        try:
            before = sha256(source)
            row['source_sha256'] = before
            t, display, metadata = extract_frame(source, byte_order, command, overrides)
            if sha256(source) != before:
                raise ValueError('Input changed during extraction; result rejected')
            stem = re.sub(r'[^\w.-]+', '_', source.stem)[:100] or 'image'
            folder = out / f'{index:04d}_{stem}'
            folder.mkdir(exist_ok=False)
            np.save(folder/'temperature.npy', t, allow_pickle=False)
            if csv_export:
                # 17 significant digits retain round-trip float64 values.
                np.savetxt(folder/'temperature.csv', t, delimiter=',', fmt='%.17g', encoding='utf8')
            gray, bounds = preview(t)
            Image.fromarray(gray).save(folder/'preview_gray.png')
            Image.fromarray(display).save(folder/'source_display.png')
            metadata.update(source_path=str(source), source_sha256=before,
                temperature_sha256=array_hash(t), export_sha256=sha256(folder/'temperature.npy'),
                display_percentiles=[1,99], display_range_c=bounds, preview_is_not_temperature=True,
                min_temperature_c=float(t.min()), max_temperature_c=float(t.max()),
                mean_temperature_c=float(t.mean()))
            write_json(folder/'radiometry.json', metadata)
            row.update(status='ok', output_folder=folder.name, rows=t.shape[0], columns=t.shape[1],
                min_temperature_c=float(t.min()), max_temperature_c=float(t.max()),
                mean_temperature_c=float(t.mean()), temperature_sha256=array_hash(t), error=None)
            print(f'OK {source.name}: {t.shape[0]} x {t.shape[1]}, {t.min():.3f} to {t.max():.3f} C', flush=True)
        except Exception as exc:
            row['error'] = f'{type(exc).__name__}: {exc}'
            print(f'ERROR {source.name}: {row["error"]}', file=sys.stderr, flush=True)
        rows.append(row)
        manifest['files'] = rows
        write_json(out/'manifest.json', manifest)
    ok = sum(r['status']=='ok' for r in rows)
    manifest.update(status='complete' if ok == len(rows) else 'complete_with_errors',
        completed_utc=datetime.now(timezone.utc).isoformat(), successful_files=ok, failed_files=len(rows)-ok,
        source_files_unchanged=all(Path(r['input_path']).is_file() and sha256(r['input_path']) == r['source_sha256'] for r in rows if r.get('source_sha256')))
    if not manifest['source_files_unchanged']:
        manifest['status'] = 'source_changed_results_not_validated'
    write_json(out/'summary.json', rows)
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with (out/'summary.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
    manifest['output_sha256'] = {str(p.relative_to(out)): sha256(p) for p in out.rglob('*') if p.is_file() and p.name != 'manifest.json'}
    write_json(out/'manifest.json', manifest)
    print(f'FINISHED: {ok} successful, {len(rows)-ok} failed. See summary.csv and manifest.json.', flush=True)
    return out, 0 if ok == len(rows) and manifest['source_files_unchanged'] else 2


def parser():
    p = argparse.ArgumentParser(description='Export native Celsius temperature matrices from radiometric FLIR JPEGs. Python 3.10+ and ExifTool required.')
    p.add_argument('--version', action='version', version=VERSION)
    p.add_argument('--input', '-i', nargs='+', help='One or more JPEG files or folders (quote paths containing spaces)')
    p.add_argument('--output', '-o', default='flir_exports', help='Parent directory; a new unique run subfolder is always created')
    p.add_argument('--config', help='Optional JSON tool/measurement config')
    p.add_argument('--byte-order', choices=['native','swap16'], help='Explicit raw uint16 byte order; overrides config')
    p.add_argument('--exiftool', help='ExifTool executable, or Perl script when combined with --perl')
    p.add_argument('--perl', help='Perl executable for the full Perl distribution only')
    p.add_argument('--recursive', action='store_true', help='Include JPEG files in nested input folders')
    p.add_argument('--csv', action='store_true', help='Also export a header-free Celsius CSV matrix for each successful image')
    p.add_argument('--check', action='store_true', help='Check Python/ExifTool/config without extracting files')
    p.add_argument('--interactive', action='store_true', help='Ask for one input path and output root in this terminal')
    return p


def main(argv=None):
    p = parser(); args = p.parse_args(argv)
    if args.interactive:
        if not args.config and Path(__file__).with_name('config.json').is_file():
            args.config = str(Path(__file__).with_name('config.json'))
        if not args.input:
            args.input = [input('Input JPEG file or folder / input path: ').strip().strip('"')]
        chosen = input(f'Output parent folder [press Enter for {args.output}]: ').strip().strip('"')
        if chosen: args.output = chosen
        if not args.byte_order and not args.config:
            args.byte_order = input('Raw byte order (native or swap16; must be verified for your files): ').strip()
        args.csv = input('Also export full temperature CSV matrices? [y/N]: ').strip().lower() == 'y'
    if not args.input and not args.check:
        p.error('--input is required, or use --interactive / --check')
    try:
        command, order, overrides = load_options(args)
        if args.check:
            print('Python:', sys.version.split()[0]); print('NumPy:', np.__version__)
            print('ExifTool:', _tool(command, ['-ver']).decode().strip())
            print('Raw byte order:', order); print('Measurement overrides:', overrides)
            print('Dependency check passed; no files extracted. Byte order and temperatures still require verification.')
            return 0
        _, code = export_batch(args.input, args.output, command, order, overrides, args.recursive, args.csv)
        return code
    except Exception as exc:
        print(f'ERROR: {type(exc).__name__}: {exc}', file=sys.stderr)
        print('See README_中文.md / README.md. Check the ExifTool path, dependencies and explicit byte order.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

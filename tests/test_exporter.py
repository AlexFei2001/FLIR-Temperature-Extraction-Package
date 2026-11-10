"""Self-contained tests: synthetic radiometry and portable batch/file behavior."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import flir_reader as reader
import extract_flir as exporter


def calibration():
    return dict(Emissivity=1, ObjectDistance=0, RelativeHumidity=.6, IRWindowTransmission=1,
        ReflectedApparentTemperature=22, AtmosphericTemperature=22, IRWindowTemperature=22,
        PlanckR1=16649.7109375, PlanckR2=.0155008062720299, PlanckB=1429.69995117188,
        PlanckF=1, PlanckO=-6159, AtmosphericTransAlpha1=.006569, AtmosphericTransAlpha2=.01262,
        AtmosphericTransBeta1=-.002276, AtmosphericTransBeta2=-.00667, AtmosphericTransX=1.9,
        RawThermalImageWidth=4, RawThermalImageHeight=3, RawThermalImageType='PNG')


def forward_signal(t, m):
    return m['PlanckR1']/(m['PlanckR2']*(np.exp(m['PlanckB']/(np.asarray(t)+273.15))-m['PlanckF']))-m['PlanckO']


def fixture_tools(monkeypatch, order='native', wrong_shape=False):
    metadata = calibration()
    expected = np.arange(12).reshape(3,4)+15.
    raw = np.rint(forward_signal(expected, metadata)).astype(np.uint16)
    stored = raw.byteswap() if order == 'swap16' else raw
    if wrong_shape: stored = stored[:2]
    payload = io.BytesIO(); Image.fromarray(stored).save(payload, format='PNG')
    def tool(command, args):
        if args == ['-ver']: return b'test-exiftool\n'
        if args[:2] == ['-j','-n']:
            if Path(args[-1]).name.lower().startswith('plain'):
                return b'[{"Make":"FLIR"}]'
            return json.dumps([metadata]).encode()
        if args[:2] == ['-b','-RawThermalImage']: return payload.getvalue()
        raise AssertionError(args)
    monkeypatch.setattr(reader, '_tool', tool); monkeypatch.setattr(exporter, '_tool', tool)
    return expected, raw


def jpeg(path):
    path.parent.mkdir(parents=True,exist_ok=True)
    Image.fromarray(np.zeros((3,4,3),dtype=np.uint8)).save(path)
    return path


def test_planck_inverse_and_nontrivial_equal_temperature_environment():
    m = calibration(); t = np.arange(12).reshape(3,4)+10.
    result,_ = reader.flir_raw_to_celsius(forward_signal(t,m),m)
    assert np.allclose(result,t,atol=1e-10)
    m.update(Emissivity=.7,ObjectDistance=23,IRWindowTransmission=.85,
        ReflectedApparentTemperature=20,AtmosphericTemperature=20,IRWindowTemperature=20)
    result,_ = reader.flir_raw_to_celsius(np.full((3,4),forward_signal(20,m)),m)
    assert np.allclose(result,20,atol=1e-10)


@pytest.mark.parametrize('field,value', [('Emissivity',0),('ObjectDistance',-1),('RelativeHumidity',60),('IRWindowTransmission',0)])
def test_invalid_measurement_units_and_parameters_rejected(field,value):
    m = calibration(); m[field]=value
    with pytest.raises(ValueError,match='Invalid'):
        reader.flir_raw_to_celsius(np.full((3,4),15000),m)


def test_missing_calibration_not_filled_with_camera_defaults():
    m=calibration(); del m['PlanckR1']
    with pytest.raises(ValueError,match='Missing'):
        reader.flir_raw_to_celsius(np.full((3,4),15000),m)


@pytest.mark.parametrize('order',['native','swap16'])
def test_raw_byte_order_temperature_units_and_native_orientation(tmp_path,monkeypatch,order):
    expected,raw=fixture_tools(monkeypatch,order)
    p=jpeg(tmp_path/'中文 文件.JPG'); before=p.read_bytes()
    t,display,meta=reader.extract_frame(p,order,['mock'])
    assert np.allclose(t,expected,atol=.02)
    assert t.shape==(3,4) and t.dtype==np.float64 and not t.flags.writeable
    assert display.shape==(3,4,3) and meta['temperature_units']=='C'
    assert meta['raw_byte_order']==order and p.read_bytes()==before
    assert not meta['absolute_numeric_validation_complete']


def test_raw_grid_size_mismatch_rejected(tmp_path,monkeypatch):
    fixture_tools(monkeypatch,wrong_shape=True)
    with pytest.raises(ValueError,match='exact-size'):
        reader.extract_frame(jpeg(tmp_path/'test.jpg'),'native',['mock'])


def test_plain_jpeg_cannot_produce_temperature(tmp_path,monkeypatch):
    fixture_tools(monkeypatch)
    with pytest.raises(ValueError,match='no raw thermal'):
        reader.extract_frame(jpeg(tmp_path/'plain.jpg'),'native',['mock'])


def test_batch_csv_roundtrip_manifest_hashes_and_never_overwrite(tmp_path,monkeypatch):
    expected,raw=fixture_tools(monkeypatch)
    source=jpeg(tmp_path/'输入目录'/'test.JPG'); before=source.read_bytes()
    out,code=exporter.export_batch([source],tmp_path/'output',['mock'],'native',csv_export=True)
    other,code2=exporter.export_batch([source],tmp_path/'output',['mock'],'native')
    assert code==code2==0 and out!=other and source.read_bytes()==before
    folder=next(out.glob('0001_*'))
    t=np.load(folder/'temperature.npy',allow_pickle=False)
    assert np.array_equal(t,np.loadtxt(folder/'temperature.csv',delimiter=','))
    with Image.open(folder/'preview_gray.png') as image: assert image.size==(4,3)
    m=json.loads((out/'manifest.json').read_text(encoding='utf8'))
    assert m['status']=='complete' and m['source_files_unchanged']
    for path,digest in m['output_sha256'].items():
        assert hashlib.sha256((out/path).read_bytes()).hexdigest()==digest


def test_mixed_batch_continues_and_plain_image_has_no_temperature(tmp_path,monkeypatch):
    fixture_tools(monkeypatch)
    good=jpeg(tmp_path/'thermal.jpg'); bad=jpeg(tmp_path/'plain.jpg')
    out,code=exporter.export_batch([good,bad],tmp_path/'out',['mock'],'native')
    summary=json.loads((out/'summary.json').read_text(encoding='utf8'))
    assert code==2 and sorted(r['status'] for r in summary)==['error','ok']
    assert len(list(out.rglob('temperature.npy')))==1
    assert json.loads((out/'manifest.json').read_text(encoding='utf8'))['status']=='complete_with_errors'


def test_duplicate_names_in_different_folders_remain_distinct(tmp_path,monkeypatch):
    fixture_tools(monkeypatch)
    files=[jpeg(tmp_path/'a'/'same.jpg'),jpeg(tmp_path/'b'/'same.jpg')]
    out,code=exporter.export_batch(files,tmp_path/'out',['mock'],'native')
    assert code==0 and len(list(out.rglob('temperature.npy')))==2


def test_input_selection_recursive_case_insensitive_and_deduplicated(tmp_path):
    one=jpeg(tmp_path/'one.JPG'); two=jpeg(tmp_path/'nested'/'two.jpeg')
    (tmp_path/'notes.txt').write_text('not an image')
    assert exporter.collect_inputs([tmp_path,one])==[one.resolve()]
    assert set(exporter.collect_inputs([tmp_path],True))=={one.resolve(),two.resolve()}


def test_config_explicit_byte_order_and_relative_tool_paths(tmp_path):
    p=tmp_path/'config.json'; tool=tmp_path/'tool directory'/'exiftool.exe'
    tool.parent.mkdir(); tool.write_bytes(b'placeholder')
    p.write_text(json.dumps({'exiftool_command':['tool directory/exiftool.exe'],'raw_byte_order':'swap16'}))
    args=exporter.parser().parse_args(['--check','--config',str(p)])
    command,order,overrides=exporter.load_options(args)
    assert command==[str(tool.resolve())] and order=='swap16' and overrides=={}
    args=exporter.parser().parse_args(['--check'])
    with pytest.raises(ValueError,match='Choose --byte-order'): exporter.load_options(args)


def test_measurement_override_cannot_replace_calibration_constants(tmp_path):
    p=tmp_path/'config.json'
    p.write_text(json.dumps({'raw_byte_order':'native','measurement_overrides':{'PlanckR1':999}}))
    args=exporter.parser().parse_args(['--check','--config',str(p)])
    with pytest.raises(ValueError,match='cannot be overridden'): exporter.load_options(args)


def test_input_changed_during_read_is_rejected_without_a_temperature_file(tmp_path,monkeypatch):
    fixture_tools(monkeypatch)
    source=jpeg(tmp_path/'thermal.jpg'); original=exporter.extract_frame
    def change_input(*args,**kwargs):
        result=original(*args,**kwargs)
        source.write_bytes(source.read_bytes()+b'external-change')
        return result
    monkeypatch.setattr(exporter,'extract_frame',change_input)
    out,code=exporter.export_batch([source],tmp_path/'out',['mock'],'native')
    manifest=json.loads((out/'manifest.json').read_text(encoding='utf8'))
    assert code==2 and manifest['status']=='source_changed_results_not_validated'
    assert not manifest['source_files_unchanged'] and not list(out.rglob('temperature.npy'))

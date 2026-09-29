"""P4 command and output contract checks."""
import time
import uuid
from types import SimpleNamespace as NS

import pytest

from mqtt_bridge.command_guard import CommandGuard
from mqtt_bridge.weld_codec import decode_start, encode_state, encode_result
from contact_scan_interfaces.msg import WeldResult, WeldState


def command(topic='start', payload=None, version='0.2'):
    return dict(schema_version=version, request_id=str(uuid.uuid4()),
                timestamp_ms=int(time.time() * 1000), payload=payload or {})


def test_topic_versions_and_stop_expiry():
    guard = CommandGuard()
    assert guard.validate('cmd/weld/start', command()).accepted
    assert not guard.validate('cmd/weld/start', command(version='0.1')).accepted
    assert guard.validate('cmd/scan/start', command(version='0.1')).accepted
    old = command('stop')
    old['timestamp_ms'] = 1
    assert guard.validate('cmd/weld/stop', old).accepted
    assert not guard.validate('cmd/weld/start', command(payload={'x': 1}, version='0.1')).accepted


def test_start_defaults_patch_and_invalid_range():
    message = command(payload={'scan_id': 'fixture', 'start_line': 2, 'end_line': 5,
                               'config': {'weld_speed_mm_s': 10, 'standoff_mm': 3,
                                          'tilt_deg': 45}})
    result = decode_start(message)
    assert result['start_line'] == 2 and result['end_line'] == 5
    assert result['config'] == {'weld_speed_mps': .01, 'weld_speed_set': True,
                                'standoff_m': .003, 'standoff_set': True,
                                'tilt_deg': 45., 'tilt_set': True}
    assert decode_start(command())['end_line'] == 7
    with pytest.raises(ValueError):
        decode_start(command(payload={'start_line': 7, 'end_line': 6}))
    with pytest.raises(ValueError):
        decode_start(command(payload={'config': {'weld_speed_mm_s': float('nan')}}))


def test_state_line_none_and_result_seams():
    state = WeldState()
    state.line_index = WeldState.LINE_NONE
    data = encode_state(state, 5)
    assert data['schema_version'] == '0.2' and data['line_index'] is None
    msg = WeldResult()
    msg.lines[0].seam.start.x = .1
    msg.lines[0].seam.length = .08
    msg.base_to_fixture.z = .4
    data = encode_result(msg, 5)
    assert data['base_to_fixture_mm']['z'] == 400
    assert data['lines'][0]['seam']['start']['x'] == 100
    assert data['lines'][0]['seam']['length_mm'] == 80
    assert data['lines'][0]['stop_pose'] is None

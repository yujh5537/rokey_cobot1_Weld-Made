import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from live import LiveHub
import main
from fastapi.testclient import TestClient


def message(hub, topic, **fields):
    hub.receive(topic, json.dumps({'schema_version': '0.1', **fields}).encode())


def test_ack_not_completion_and_late_ack_cannot_regress():
    hub = LiveHub()
    msg, record = hub.begin('stop')
    message(hub, 'cmd/ack', request_id=msg['request_id'], accepted=True)
    assert record['status'] == 'accepted'
    message(hub, 'scan/result', success=True)
    assert record['status'] == 'accepted'
    message(hub, 'scan/command_result', request_id=msg['request_id'], success=True)
    message(hub, 'cmd/ack', request_id=msg['request_id'], accepted=False)
    assert record['status'] == 'completed'


def test_timeout_late_response_and_rejection():
    hub = LiveHub(0)
    msg, record = hub.begin('home')
    hub.expire()
    assert record['status'] == 'unknown'
    message(hub, 'cmd/ack', request_id=msg['request_id'], accepted=False)
    assert record['status'] == 'rejected'


def test_invalid_json_is_ignored_and_null_preserved():
    hub = LiveHub()
    queue = asyncio.Queue(10); hub.clients.add(queue)
    for raw in (b'[]', b'bad', b'{"schema_version":"0.1", "value":NaN}'):
        hub.receive('scan/result', raw)
    assert queue.empty()
    message(hub, 'scan/result', width_mm=None, dims_valid=False)
    assert queue.get_nowait()['payload']['width_mm'] is None


def test_disconnect_and_slow_subscriber():
    hub = LiveHub()
    _, record = hub.begin('start')
    hub.connection(False)
    assert record['status'] == 'unknown'
    queue = asyncio.Queue(1); hub.clients.add(queue)
    hub.emit('test', {}); hub.emit('test', {})
    assert queue.get_nowait() is None
    assert queue not in hub.clients


def test_four_rest_commands_contract(monkeypatch):
    hub = LiveHub(); hub.connected = True
    monkeypatch.setattr(main, 'hub', hub)
    sent = []
    monkeypatch.setattr(main.mqtt_client, 'publish', lambda *a, **kw: (sent.append((a,kw)) or SimpleNamespace(rc=0)))
    client = TestClient(main.app)
    for action in ('start','stop','home','resume'):
        response = client.post('/api/scan/'+action, json={'scan_id':'existing'})
        assert response.status_code == 202
        assert response.json()['status'] == 'pending'
        args, opts = sent[-1]
        assert args[0] == 'cmd/scan/'+action and opts == {'qos':1,'retain':False}
        payload=json.loads(args[1]); assert UUID(payload['request_id']).version == 4
        if action == 'resume': assert payload['scan_id'] == 'existing'
    hub.connected=False
    assert client.post('/api/scan/start',json={}).status_code == 503
    assert len(sent) == 4


def test_websocket_snapshot(monkeypatch):
    hub = LiveHub(); hub.connected = True
    monkeypatch.setattr(main,'hub',hub)
    message(hub,'scan/state',phase='STOPPED',scan_id='existing')
    client=TestClient(main.app)
    with client.websocket_connect('/ws/live') as ws:
        snapshot=ws.receive_json()
        assert snapshot['payload']['latest'][0]['payload']['phase']=='STOPPED'
    assert not hub.clients

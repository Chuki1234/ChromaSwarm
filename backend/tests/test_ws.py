from fastapi.testclient import TestClient

from chromaswarm.main import app


def test_ws_drives_pipeline():
    client = TestClient(app)
    with client.websocket_connect("/ws/session/ws-demo") as ws:
        first = ws.receive_json()
        assert first["state"]["step"] == "B1"
        assert first["question"]["key"] == "raw_prompt"
        assert "write_workspace_file" not in first["tools"]

        ws.send_json({"type": "answer", "value": "Làm web bán giày thể thao"})
        msg = ws.receive_json()
        assert msg["state"]["step"] == "B2"
        assert msg["question"]["recommended"] == "landing"

        ws.send_json({"type": "approve_plan"})
        assert ws.receive_json()["type"] == "error"

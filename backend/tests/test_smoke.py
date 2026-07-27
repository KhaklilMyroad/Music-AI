"""Smoke tests: API surface works end-to-end against a mocked ACE-Step engine."""
import os
import sys
import tempfile

os.environ["POLL_INTERVAL_SECONDS"] = "0.05"
os.environ["MASTERING_ENABLED"] = "false"
os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/test.db"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

from app import main
from app.services import acestep


class FakeEngine:
    def __init__(self):
        self.tasks: dict[str, dict] = {}
        self._n = 0

    async def health(self):
        return True

    async def release_task(self, **kwargs):
        self._n += 1
        task_id = f"task-{self._n}"
        self.tasks[task_id] = kwargs
        return task_id

    async def query_results(self, task_ids):
        return {
            tid: {
                "status": 1,
                "result": {"audio_path": f"/outputs/{tid}.mp3", "bpm": 120,
                           "duration": 60.0, "key_scale": "C major", "seed": 42},
            }
            for tid in task_ids
        }

    async def stream_audio(self, path):
        yield b"ID3fakemp3data"


@pytest.fixture()
def client(monkeypatch):
    fake = FakeEngine()
    monkeypatch.setattr(acestep, "_client", fake)
    with TestClient(main.app) as c:
        c.fake = fake  # type: ignore[attr-defined]
        yield c


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["engine_reachable"] is True


def test_generate_poll_and_stream(client):
    resp = client.post("/api/songs", json={
        "prompt": "upbeat synthwave, retro, 80s", "lyrics": "[verse]\nneon lights",
        "duration": 60, "batch_size": 2,
    })
    assert resp.status_code == 201, resp.text
    track = resp.json()
    assert track["status"] == "queued"
    assert client.fake.tasks["task-1"]["batch_size"] == 2

    import anyio
    from app.services.jobs import poll_once
    anyio.run(poll_once)

    got = client.get(f"/api/songs/{track['id']}").json()
    assert got["status"] == "ready"
    assert got["bpm"] == 120
    assert got["key_scale"] == "C major"

    audio = client.get(f"/api/songs/{track['id']}/audio")
    assert audio.status_code == 200
    assert audio.content.startswith(b"ID3")


def test_studio_ops_create_children(client):
    track = client.post("/api/songs", json={"prompt": "lofi hiphop"}).json()
    import anyio
    from app.services.jobs import poll_once
    anyio.run(poll_once)

    for path, body in [
        (f"/api/studio/{track['id']}/stems", {}),
        (f"/api/studio/{track['id']}/cover", {"prompt": "jazz version", "strength": 0.5}),
        (f"/api/studio/{track['id']}/repaint", {"prompt": "heavier drums", "start": 5, "end": 15}),
        (f"/api/studio/{track['id']}/extend", {"prompt": "add an outro", "duration": 90}),
    ]:
        resp = client.post(path, json=body)
        assert resp.status_code == 201, f"{path}: {resp.text}"
        child = resp.json()
        assert child["parent_id"] == track["id"]

    task_types = {t["task_type"] for t in client.get("/api/songs").json()}
    assert {"text2music", "extract", "cover", "repaint", "complete"} <= task_types


def test_repaint_validates_range(client):
    track = client.post("/api/songs", json={"prompt": "rock"}).json()
    import anyio
    from app.services.jobs import poll_once
    anyio.run(poll_once)
    resp = client.post(f"/api/studio/{track['id']}/repaint",
                       json={"prompt": "x", "start": 10, "end": 5})
    assert resp.status_code == 422


def test_studio_requires_ready_source(client):
    track = client.post("/api/songs", json={"prompt": "ambient"}).json()
    resp = client.post(f"/api/studio/{track['id']}/stems", json={})
    assert resp.status_code == 409


def test_audio_path_found_in_nested_result_shapes():
    from app.services.jobs import _find_audio_path

    assert _find_audio_path({"audios": [{"path": "/out/a.flac"}]}) == "/out/a.flac"
    assert _find_audio_path(["/outputs/take_1.wav", "/outputs/take_2.wav"]) == "/outputs/take_1.wav"
    assert _find_audio_path({"data": {"result": {"file_url": "http://x/y.mp3?sig=1"}}}) == "http://x/y.mp3?sig=1"
    assert _find_audio_path({"prompt": "rock song", "seed": 1}) is None


def test_audio_path_extracted_from_engine_download_url():
    from app.services.jobs import _find_audio_path

    result = [{"file": "/v1/audio?path=C%3A%5CUsers%5Cronen%5Ctmp%5Cabc.flac", "wave": ""}]
    assert _find_audio_path(result) == "C:\\Users\\ronen\\tmp\\abc.flac"


def test_compose_builds_sections_and_completes(client):
    import time

    resp = client.post("/api/songs/compose", json={
        "title": "Composed Test",
        "base_prompt": "melodic techno, 124 bpm",
        "sections": [
            {"name": "Intro", "prompt": "stripped intro", "duration": 10},
            {"name": "Drop", "prompt": "full drop", "duration": 20, "lyrics": "hook line"},
        ],
    })
    assert resp.status_code == 201, resp.text
    track = resp.json()
    assert track["task_type"] == "compose"

    for _ in range(100):
        got = client.get(f"/api/songs/{track['id']}").json()
        if got["status"] in ("ready", "failed"):
            break
        time.sleep(0.1)
    assert got["status"] == "ready", got
    # first section: text2music; second: complete continuing the first audio
    tasks = client.fake.tasks
    assert tasks["task-1"]["task_type"] == "text2music"
    assert tasks["task-2"]["task_type"] == "complete"
    assert tasks["task-2"]["src_audio_path"] == "/outputs/task-1.mp3"
    assert tasks["task-2"]["lyrics"] == "hook line"


def test_upload_creates_ready_track_and_streams(client, tmp_path):
    import io

    resp = client.post("/api/songs/upload", files={
        "file": ("my_song.mp3", io.BytesIO(b"ID3fakebytes"), "audio/mpeg"),
    })
    assert resp.status_code == 201, resp.text
    track = resp.json()
    assert track["status"] == "ready"
    assert track["task_type"] == "upload"
    assert track["title"] == "my_song"

    audio = client.get(f"/api/songs/{track['id']}/audio")
    assert audio.status_code == 200
    assert audio.content == b"ID3fakebytes"


def test_upload_rejects_unknown_extension(client):
    import io

    resp = client.post("/api/songs/upload", files={
        "file": ("virus.exe", io.BytesIO(b"MZ"), "application/octet-stream"),
    })
    assert resp.status_code == 415

import pytest

import foto_api


VALID_REQUEST = {
    "width": 640,
    "height": 480,
    "rotation": 90,
    "exposure": "auto",
    "iso": 100,
}


@pytest.fixture(autouse=True)
def isolated_photo_store(monkeypatch, tmp_path):
    """Keep each test independent of /tmp and of prior requests."""
    monkeypatch.setattr(foto_api, "PHOTO_DIR", tmp_path)
    foto_api.photo_store.clear()
    yield
    foto_api.photo_store.clear()


@pytest.fixture
def client():
    return foto_api.flask_app.test_client()


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"width": 12}, "width must be"),
        ({"height": "480"}, "height must be"),
        ({"rotation": 45}, "rotation must be"),
        ({"iso": 801}, "iso must be"),
        ({"exposure": 0}, "exposure must be"),
    ],
)
def test_validate_photo_request_rejects_invalid_values(changes, message):
    request = dict(VALID_REQUEST)
    request.update(changes)

    with pytest.raises(ValueError, match=message):
        foto_api.validate_photo_request(request)


def test_post_creates_photo_and_returns_download_id(client, monkeypatch):
    captured = {}

    def fake_take_foto(**kwargs):
        captured.update(kwargs)
        kwargs["file_path"].write_bytes(b"jpeg-data")

    monkeypatch.setattr(foto_api, "take_foto", fake_take_foto)

    response = client.post("/foto/", json=VALID_REQUEST)

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "new foto created"
    assert body["foto resolution"] == "640x480"
    assert body["foto rotation"] == 90
    assert captured["file_path"] == foto_api.photo_store[body["photo_id"]]
    assert captured["exposure"] == "auto"


def test_get_downloads_photo_once_and_removes_its_file(client, tmp_path):
    photo_id = "a-photo-id"
    path = tmp_path / f"{photo_id}.jpg"
    path.write_bytes(b"jpeg-data")
    foto_api.photo_store[photo_id] = path

    response = client.get(f"/foto/?photo_id={photo_id}", buffered=False)

    assert response.status_code == 200
    assert response.data == b"jpeg-data"
    response.close()
    assert not path.exists()
    assert client.get(f"/foto/?photo_id={photo_id}").status_code == 404


def test_get_requires_photo_id(client):
    response = client.get("/foto/")

    assert response.status_code == 400
    assert response.get_json()["message"] == "photo_id query parameter is required"


def test_take_foto_configures_and_closes_camera(monkeypatch, tmp_path):
    cameras = []

    class FakeCamera:
        def __init__(self):
            cameras.append(self)
            self.closed = False

        def capture(self, path):
            self.capture_path = path

        def close(self):
            self.closed = True

    class FakePicamera:
        PiCamera = FakeCamera

    monkeypatch.setattr(foto_api, "picamera", FakePicamera)
    target = tmp_path / "photo.jpg"
    foto_api.take_foto(640, 480, 180, "1200", 200, target)

    camera = cameras[0]
    assert camera.resolution == (640, 480)
    assert camera.rotation == 180
    assert camera.ISO == 200
    assert camera.shutter_speed == 1200
    assert camera.exposure_mode == "off"
    assert camera.capture_path == str(target)
    assert camera.closed

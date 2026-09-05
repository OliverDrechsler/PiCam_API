#!/usr/bin/env python3
"""Photo API using the legacy :mod:`picamera` backend."""
import os
import threading
import uuid
from pathlib import Path

from flask import Flask, request, send_file

try:
    from flask_restx import Api, Resource, fields
except ImportError:
    try:
        from flask_restplus import Api, Resource, fields
    except ImportError:
        from flask.views import MethodView

        class _Fields:
            Integer = String = Raw = staticmethod(lambda **kwargs: kwargs)

        class Api:
            def __init__(self, app, **_kwargs): self.app = app
            def namespace(self, name, description=None):
                application, prefix = self.app, f"/{name.strip('/')}"
                class Namespace:
                    def route(self, rule):
                        def register(resource):
                            url = f"{prefix}/" if rule == "/" else f"{prefix}/{rule.lstrip('/')}"
                            methods = [m.upper() for m in ("get", "post", "put", "delete", "patch") if hasattr(resource, m)]
                            application.add_url_rule(url, view_func=resource.as_view(f"{resource.__name__}_{url}"), methods=methods)
                            return resource
                        return register
                return Namespace()
            def model(self, _name, schema): return schema
            def doc(self, **_kwargs): return lambda function: function
            def expect(self, _model): return lambda function: function

        class Resource(MethodView):
            pass
        fields = _Fields()

try:
    import picamera
except ImportError:
    picamera = None


PHOTO_DIR = Path("/tmp/picam_api")
PHOTO_DIR.mkdir(parents=True, exist_ok=True)
MIN_WIDTH, MAX_WIDTH = 64, 3280
MIN_HEIGHT, MAX_HEIGHT = 64, 2464
ALLOWED_ROTATIONS = {0, 90, 180, 270}
MIN_ISO, MAX_ISO = 0, 800
MAX_EXPOSURE_US = 1_000_000
ALLOWED_EXPOSURES = {"auto"}

photo_store = {}
photo_store_lock = threading.Lock()
camera_lock = threading.Lock()

flask_app = Flask(__name__)
app = Api(app=flask_app, version="1.0", title="Pi Camera Foto API", description="Takes photos and allows downloading them")
name_space = app.namespace("foto", description="Foto API")

model = app.model("Foto Properties", {
    "width": fields.Integer(default=640, required=True, description="Width of the photo in pixels"),
    "height": fields.Integer(default=480, required=True, description="Height of the photo in pixels"),
    "rotation": fields.Integer(default=0, required=True, description="Photo rotation: 0, 90, 180, or 270"),
    "exposure": fields.String(default="auto", required=True, description="'auto' or microseconds"),
    "iso": fields.Integer(default=100, required=True, description="ISO value from 0 to 800"),
})
post_response_model = app.model("Foto Create Response", {
    "status": fields.String(description="Status message"), "photo_id": fields.String(description="Download identifier"),
    "foto resolution": fields.String(description="WIDTHxHEIGHT"), "foto rotation": fields.Integer(description="Applied rotation"),
    "exposure mode": fields.String(description="Applied exposure"), "iso": fields.Integer(description="Applied ISO"),
})
get_response_model = app.model("Foto Download Response", {
    "content": fields.Raw(description="JPEG response body"), "content_type": fields.String(description="image/jpeg"),
    "filename": fields.String(description="Downloaded filename"),
})


def _bad_request(message: str):
    return {"message": message, "statusCode": "400"}, 400


def _normalize_exposure(exposure):
    if exposure in ALLOWED_EXPOSURES:
        return exposure
    if isinstance(exposure, int):
        value = exposure
    elif isinstance(exposure, str) and exposure.isdigit():
        value = int(exposure)
    else:
        raise ValueError("exposure must be 'auto' or a positive integer in microseconds")
    if not 1 <= value <= MAX_EXPOSURE_US:
        raise ValueError(f"exposure must be between 1 and {MAX_EXPOSURE_US} microseconds")
    return str(value)


def validate_photo_request(json_input):
    if not isinstance(json_input, dict):
        raise ValueError("JSON request body is required")
    for field in ("width", "height", "rotation", "exposure", "iso"):
        if field not in json_input:
            raise ValueError(f"Missing required field: {field}")
    width, height = json_input["width"], json_input["height"]
    rotation, iso = json_input["rotation"], json_input["iso"]
    if not isinstance(width, int) or not MIN_WIDTH <= width <= MAX_WIDTH:
        raise ValueError(f"width must be an integer between {MIN_WIDTH} and {MAX_WIDTH}")
    if not isinstance(height, int) or not MIN_HEIGHT <= height <= MAX_HEIGHT:
        raise ValueError(f"height must be an integer between {MIN_HEIGHT} and {MAX_HEIGHT}")
    if not isinstance(rotation, int) or rotation not in ALLOWED_ROTATIONS:
        raise ValueError("rotation must be one of 0, 90, 180, 270")
    if not isinstance(iso, int) or not MIN_ISO <= iso <= MAX_ISO:
        raise ValueError(f"iso must be an integer between {MIN_ISO} and {MAX_ISO}")
    return {"width": width, "height": height, "rotation": rotation, "exposure": _normalize_exposure(json_input["exposure"]), "iso": iso}


def create_photo_path(photo_id: str) -> Path:
    file_path = (PHOTO_DIR / f"{photo_id}.jpg").resolve()
    if file_path.parent != PHOTO_DIR.resolve():
        raise ValueError("Invalid photo filename")
    return file_path


def pop_photo_path(photo_id: str):
    with photo_store_lock:
        return photo_store.pop(photo_id, None)


@name_space.route("/")
class MainClass(Resource):
    @app.doc(params={"photo_id": "Identifier returned by POST /foto/"}, responses={200: ("OK", get_response_model), 400: "Invalid Argument", 404: "Not Found", 500: "Internal Server Error"})
    def get(self):
        photo_id = request.args.get("photo_id", "").strip()
        if not photo_id:
            return _bad_request("photo_id query parameter is required")
        file_path = pop_photo_path(photo_id)
        if file_path is None:
            return {"message": "Photo not found", "statusCode": "404"}, 404
        if not file_path.exists():
            return {"message": "Photo file not found", "statusCode": "404"}, 404
        try:
            response = send_file(file_path, as_attachment=True, download_name=file_path.name)
            # ``send_file`` uses direct passthrough by default.  Disable it so
            # Flask invokes this response's close callbacks after streaming.
            response.direct_passthrough = False
            def cleanup():
                try:
                    file_path.unlink(missing_ok=True)
                except OSError:
                    flask_app.logger.warning("Could not remove photo file %s", file_path)
            response.call_on_close(cleanup)
            return response
        except Exception:
            flask_app.logger.exception("Failed to deliver photo %s", photo_id)
            return {"message": "Could not retrieve photo", "statusCode": "500"}, 500

    @app.doc(responses={200: ("OK", post_response_model), 400: "Invalid Argument", 500: "Internal Server Error"})
    @app.expect(model)
    def post(self):
        try:
            photo_request = validate_photo_request(request.get_json())
            photo_id = uuid.uuid4().hex
            file_path = create_photo_path(photo_id)
            take_foto(file_path=file_path, **photo_request)
            with photo_store_lock:
                photo_store[photo_id] = file_path
            return {"status": "new foto created", "photo_id": photo_id,
                    "foto resolution": f"{photo_request['width']}x{photo_request['height']}",
                    "foto rotation": photo_request["rotation"], "exposure mode": photo_request["exposure"], "iso": photo_request["iso"]}
        except ValueError as exc:
            return _bad_request(str(exc))
        except RuntimeError:
            flask_app.logger.exception("Camera runtime error while creating a photo")
            return {"message": "Could not create photo", "statusCode": "500"}, 500
        except Exception:
            flask_app.logger.exception("Unexpected error while creating a photo")
            return {"message": "Could not create photo", "statusCode": "500"}, 500


def take_foto(width: int, height: int, rotation: int, exposure: str, iso: int, file_path: Path):
    """Capture a JPEG with the legacy picamera library."""
    file_path = file_path.resolve()
    if file_path.parent != PHOTO_DIR.resolve():
        raise ValueError("file_path must stay inside the photo directory")
    if picamera is None:
        raise RuntimeError("picamera library is not installed.")
    with camera_lock:
        camera = picamera.PiCamera()
        try:
            camera.resolution = (width, height)
            camera.rotation = rotation
            camera.ISO = iso
            if exposure == "auto":
                camera.exposure_mode = "auto"
            else:
                camera.shutter_speed = int(exposure)
                camera.exposure_mode = "off"
            camera.capture(str(file_path))
        finally:
            camera.close()


if __name__ == "__main__":
    flask_app.run(host=os.getenv("IP", "0.0.0.0"), port=8000, debug=False)

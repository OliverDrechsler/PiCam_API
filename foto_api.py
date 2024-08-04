#!/usr/bin/env python3
import os
from flask import Flask, request, send_file
from flask_restx import Api, Resource, fields
try:
    from picamera2 import Picamera2
except Exception:
    pass
import time

# Initialize Flask app
flask_app = Flask(__name__)
app = Api(
    app=flask_app,
    version="1.0",
    title="Pi Camera Foto API",
    description="Takes photos and allows downloading them"
)

# Define namespace
name_space = app.namespace('foto', description='Foto API')

# Define data model for the API
model = app.model(
    'Foto Properties',
    {
        'width': fields.Integer(
            default=640,
            required=False,
            description="Width of the photo in pixels",
            help="Specify the width in pixels like 640x480 means 640 in width"
        ),
        'height': fields.Integer(
            default=480,
            required=False,
            description="Height of the photo in pixels",
            help="Specify the height in pixels like 640x480 means 480 in height"
        ),
        'rotation': fields.Integer(
            default=90,
            required=False,
            description="Photo rotation in degrees",
            help="Photo rotation in degrees, e.g., 90"
        ),
        'exposure': fields.String(
            default='auto',
            required=False,
            description="Photo exposure mode",
            help="Photo mode auto, night, etc."
        ),
        'iso': fields.Integer(
            default=0,
            required=False,
            description="Photo ISO",
            help="ISO Mode 0 ... 800"
        ),
        'filename': fields.String(
            default='foto.jpg',
            required=False,
            description="Filename",
            help="Photo filename"
        ),
    }
)

@name_space.route("/")
class MainClass(Resource):

    @app.doc(
        responses={200: 'OK', 400: 'Invalid Argument', 500: 'Mapping Key Error'},
        params={'filename': 'Specify the photo filename'}
    )
    def get(self):
        filename = request.args.get('filename', default='foto.jpg', type=str)
        try:
            file_path = os.path.join('/tmp/', filename)
            if os.path.exists(file_path):
                response = send_file(file_path, as_attachment=True)
                os.remove(file_path)
                return response
            else:
                raise KeyError("File not found")

        except KeyError as e:
            name_space.abort(
                500, e.__doc__, status="Could not retrieve information", statusCode="500"
            )
        except Exception as e:
            name_space.abort(
                400, e.__doc__, status="Could not retrieve information", statusCode="400"
            )

    @app.doc(responses={200: 'OK', 400: 'Invalid Argument', 500: 'Mapping Key Error'})
    @app.expect(model)
    def post(self):
        try:
            json_input = request.get_json()
            take_foto(
                width=json_input['width'],
                height=json_input['height'],
                rotation=json_input['rotation'],
                exposure=json_input['exposure'],
                iso=json_input['iso'],
                filename=json_input['filename']
            )
            return {
                "status": "new foto created",
                "foto resolution": f"{json_input['width']}x{json_input['height']}",
                "foto rotation": json_input['rotation'],
                "exposure mode": json_input['exposure'],
                "iso": json_input['iso'],
                "filename": json_input['filename']
            }

        except KeyError as e:
            name_space.abort(
                500, e.__doc__, status="Could not save information", statusCode="500"
            )
        except Exception as e:
            name_space.abort(
                400, e.__doc__, status="Could not save information", statusCode="400"
            )


def take_foto(width, height, rotation, exposure, iso, filename):
    picam2 = Picamera2()
    try:
        picam2.configure(picam2.create_still_configuration(main={"size": (width, height)}))
        picam2.controls.Rotation = rotation
        picam2.controls.ExposureMode = exposure
        picam2.controls.ISO = iso
        picam2.start()
        time.sleep(2)  # Allow camera to adjust settings
        file_path = os.path.join('/tmp/', filename)
        if os.path.exists(file_path):
            os.remove(file_path)
        picam2.capture_file(file_path)
    finally:
        picam2.stop()
        picam2.close()


if __name__ == "__main__":
    flask_app.run(
        host=os.getenv('IP', '0.0.0.0'),
        port=8000
    )

# Run app manually
# export FLASK_RUN_PORT=8000 && FLASK_APP=foto_api.py flask run

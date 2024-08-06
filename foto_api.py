#!/usr/bin/env python3
import os
from flask import Flask, request, send_file
from flask_restx import Api, Resource, fields  # Updated import
import picamera
import time

flask_app = Flask(__name__)
app = Api(app=flask_app,
          version="1.0",
          title="Pi Camera Foto API",
          description="Takes photos and retrieves them by downloading")

name_space = app.namespace('foto', description='Foto API')

model = app.model(
    'Foto Properties',
    {
        'width': fields.Integer(
            default=640,
            required=False,
            description="Width of the photo in pixels",
            help="Specify the width in pixels (e.g., 640 for 640x480)"
        ),
        'height': fields.Integer(  # Corrected spelling from 'hight' to 'height'
            default=480,
            required=False,
            description="Height of the photo in pixels",
            help="Specify the height in pixels (e.g., 480 for 640x480)"
        ),
        'rotation': fields.Integer(
            default=90,
            required=False,
            description="Photo rotation in degrees",
            help="Photo rotation in degrees (e.g., 90)"
        ),
        'exposure': fields.String(
            default='auto',
            required=False,
            description="Photo exposure mode",
            help="Photo exposure mode (e.g., auto, night)"
        ),
        'iso': fields.Integer(
            default=0,
            required=False,
            description="Photo ISO setting",
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
                name_space.abort(
                    404, "File not found", status="Could not retrieve information",
                    statusCode="404"
                )

        except Exception as e:
            name_space.abort(
                400, str(e), status="Could not retrieve information",
                statusCode="400"
            )

    @app.doc(responses={200: 'OK', 400: 'Invalid Argument', 500: 'Mapping Key Error'})
    @app.expect(model)
    def post(self):
        try:
            json_input = request.get_json()
            take_foto(
                width=json_input['width'],
                height=json_input['height'],  # Use 'height' instead of 'hight'
                rotation=json_input['rotation'],
                exposure=json_input['exposure'],
                iso=json_input['iso'],
                filename=json_input['filename']
            )
            return {
                "status": "New photo created",
                "foto resolution": f"{json_input['width']}x{json_input['height']}",
                "foto rotation": json_input['rotation'],
                "exposure mode": json_input['exposure'],
                "iso": json_input['iso'],
                "filename": json_input['filename']
            }

        except KeyError as e:
            name_space.abort(
                500, str(e), status="Missing parameters",
                statusCode="500"
            )
        except Exception as e:
            name_space.abort(
                400, str(e), status="Could not save information",
                statusCode="400"
            )


def take_foto(width, height, rotation, exposure, iso, filename):
    cam = picamera.PiCamera()
    try:
        cam.resolution = (width, height)
        cam.rotation = rotation
        cam.exposure_mode = exposure
        cam.iso = iso
        cam.start_preview()
        time.sleep(2)
        file_path = os.path.join('/tmp/', filename)
        if os.path.exists(file_path):
            os.remove(file_path)
        cam.capture(file_path)
        cam.stop_preview()
    finally:
        cam.close()


if __name__ == "__main__":
    flask_app.run(
        host=os.getenv('IP', '0.0.0.0'),
        port=8000
    )

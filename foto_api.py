#!/usr/bin/env python3
import os
from flask import Flask, request, send_file
from flask_restplus import Api, Resource, fields
import picamera
import time

flask_app = Flask(__name__)
app = Api(app=flask_app,
          version="1.0",
          title="Pi Camera Foto API",
          description="takes fotos and get fotos by downloading")

name_space = app.namespace('foto', description='Foto API')

model = app.model(
    'Foto Properties',
    {'width': fields.Integer(
        default=640,
        required=False,
        description="width of the foto in pixel",
        help="specifiy the width in pixel like 640x480 means 640 in width"),
     'hight': fields.Integer(
        default=480,
        required=False,
        description="hight of the foto in pixel",
        help="specifiy the hight in pixel like 640x480 means 480 in hight"),
     'rotation': fields.Integer(
        default=90,
        required=False,
        description="foto rotation in degrees",
        help="foto rotation in degrees 90"),
     'exposure': fields.String(
        default='auto',
        required=False,
        description="foto exposure mode",
        help="foto mode auto, night, ...."),
     'iso': fields.Integer(
        default=0,
        required=False,
        description="foto ISO",
        help="ISO Mode 0 ... 800"),
     'filename': fields.String(
        default='foto.jpg',
        required=False,
        description="filename",
        help="foto filename"),

     })


@name_space.route("/")
class MainClass(Resource):

    @app.doc(
        responses={200: 'OK', 400: 'Invalid Argument',
                   500: 'Mapping Key Error'},
        params={'filename': 'Specify the foto filename'}
    )
    def get(self):
        filename = request.args.get('filename', default='foto.jpg', type=str)
        try:
            file = os.path.join('/tmp/', filename)
            if os.path.exists(file):
                return send_file(file, as_attachment=True)
                os.remove(file)
            else:
                raise KeyError

        except KeyError as e:
            name_space.abort(
                500, e.__doc__, status="Could not retrieve information",
                statusCode="500")
        except Exception as e:
            name_space.abort(
                400, e.__doc__, status="Could not retrieve information",
                statusCode="400")

    @app.doc(responses={200: 'OK', 400: 'Invalid Argument', 500: 'Mapping Key Error'})
    @app.expect(model)
    def post(self):
        try:
            json_input = request.get_json()
            take_foto(
                width=json_input['width'],
                hight=json_input['hight'],
                rotation=json_input['rotation'],
                exposure=json_input['exposure'],
                iso=json_input['iso'],
                filename=json_input['filename'])
            return {

                "status": "new foto created",
                "foto resolution": str(json_input['width']) + "x" + str(json_input['hight']),
                "foto rotation": json_input['rotation'],
                "exposure mode": json_input['exposure'],
                "iso": json_input['iso'],
                "filename": json_input['filename']
            }

        except KeyError as e:
            name_space.abort(
                500, e.__doc__, status="Could not save information",
                statusCode="500")
        except Exception as e:
            name_space.abort(
                400, e.__doc__, status="Could not save information",
                statusCode="400")


def take_foto(width, hight, rotation, exposure, iso, filename):
    cam = picamera.PiCamera()
    try:
        cam.resolution = (width, hight)
        cam.rotation = rotation
        cam.exposure_mode = exposure
        cam.ISO = iso
        cam.start_preview()
        time.sleep(2)
        file = os.path.join('/tmp/', filename)
        if os.path.exists(file):
            os.remove(file)
        cam.capture(file)
        cam.stop_preview()
    finally:
        cam.close()


if __name__ == "__main__":
    flask_app.run(
        # debug=True,
        host=os.getenv('IP', '0.0.0.0'),
        port=8000
    )

# run app manually
# export FLASK_RUN_PORT=8000 && FLASK_APP=foto_api.py flask run

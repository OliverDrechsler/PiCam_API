# PiCam API (deprecated)

> This project is no longer maintained. For new installations, use [PiCam_API_2](https://github.com/OliverDrechsler/PiCam_API_2).

A small Flask REST API for taking a JPEG with the legacy Raspberry Pi
`picamera` backend and downloading it once. It is intended for the
[Front Door Intercom automation](https://github.com/OliverDrechsler/front_door_intercom_automation).

## Breaking change: request and download API

Clients of the old API must be updated:

- The misspelled request field `hight` has been replaced by the required field
  `height`. Requests with `hight` and without `height` return HTTP 400.
- `filename` is no longer used as a request or download parameter. The server
  creates the filename itself; downloads require `photo_id` instead.
- `POST /foto/` now returns a generated `photo_id`. Pass exactly that value as
  `photo_id` when downloading with `GET /foto/`.
- A photo can be downloaded only once. It is removed from the server after the
  download response has been closed. Pending photos are also unavailable after
  an API restart because their IDs are kept in memory.

## Installation and start

Install the dependencies on a Raspberry Pi with a camera and the legacy
`picamera` package available:

```bash
python3 -m pip install -r requirements.txt
python3 foto_api.py
```

The service listens on `0.0.0.0:8000` by default. Set `IP` to change its bind
address:

```bash
IP=127.0.0.1 python3 foto_api.py
```

## API

Base URL: `http://<raspberry-pi>:8000/foto/`

### Create a photo

`POST /foto/` expects a JSON body with all fields below.

| Field | Type | Allowed values |
| --- | --- | --- |
| `width` | integer | 64–3280 pixels |
| `height` | integer | 64–2464 pixels |
| `rotation` | integer | `0`, `90`, `180`, or `270` |
| `exposure` | string or integer | `"auto"` or 1–1,000,000 microseconds |
| `iso` | integer | 0–800 |

Example:

```bash
curl -X POST http://<raspberry-pi>:8000/foto/ \
  -H 'Content-Type: application/json' \
  -d '{
    "width": 640,
    "height": 480,
    "rotation": 90,
    "exposure": "auto",
    "iso": 100
  }'
```

A successful request returns HTTP 200 and metadata including the download ID:

```json
{
  "status": "new foto created",
  "photo_id": "c4e3...",
  "foto resolution": "640x480",
  "foto rotation": 90,
  "exposure mode": "auto",
  "iso": 100
}
```

Invalid input returns HTTP 400 with a descriptive `message`. Camera or other
unexpected errors return HTTP 500.

### Download the photo

`GET /foto/?photo_id=<photo_id>` returns the JPEG as an attachment. Use the
`photo_id` returned by the create request:

```bash
curl -f -G http://<raspberry-pi>:8000/foto/ \
  --data-urlencode 'photo_id=c4e3...' \
  -o foto.jpg
```

The endpoint returns HTTP 400 when `photo_id` is missing and HTTP 404 when it
is unknown, has already been used, or its file is no longer present.

## Python client

[`get_foto.py`](get_foto.py) demonstrates the required two-step flow. Set the
server URL with `PICAM_API_URL` if necessary:

```bash
PICAM_API_URL=http://<raspberry-pi>:8000/foto/ python3 get_foto.py
```

The script creates the photo, reads its `photo_id`, and downloads it as
`foto.jpg` in the current directory.

## Tests

The unit tests mock the camera and use Flask's test client; no camera hardware
or running API service is required.

```bash
python3 -m pytest -q
```

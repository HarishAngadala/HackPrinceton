"""Dependency-free client for the team's hosted FLARE API."""
import argparse
import json
import mimetypes
import os
from pathlib import Path
import sys
import socket
import urllib.error
import urllib.request
import urllib.parse
import uuid

DEFAULT_URL = "https://continually-priest-rural-moments.trycloudflare.com"


def request(base_url, endpoint, data=None, headers=None, timeout=120):
    req = urllib.request.Request(base_url.rstrip('/') + endpoint, data=data, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            result = json.load(response)
            if not isinstance(result, dict):
                raise RuntimeError('FLARE returned an invalid response; expected a JSON object.')
            return result
    except urllib.error.HTTPError as exc:
        detail = exc.read(4096).decode(errors='replace')
        raise RuntimeError(f"FLARE HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, socket.gaierror):
            raise RuntimeError(f'Cannot resolve FLARE host {urllib.parse.urlparse(base_url).hostname}. The temporary tunnel may have expired. Restart with --api-url CURRENT_URL.') from exc
        raise RuntimeError(f'Cannot connect to FLARE: {exc.reason}') from exc
    except (TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f'FLARE timed out or returned invalid JSON: {exc}') from exc


def ready(base_url=DEFAULT_URL):
    result = request(base_url, '/ready', timeout=20)
    if result.get('model_loaded') is not True:
        raise RuntimeError(f"Model is not ready: {result}")
    return result


def transcribe(path, base_url=DEFAULT_URL):
    path = Path(path)
    if path.suffix.lower() not in {'.mp4', '.webm'}:
        raise ValueError('Use an MP4 or WebM clip, preferably 2–5 seconds, at most 60 seconds.')
    if not path.is_file() or not 0 < path.stat().st_size <= 50 * 1024 * 1024:
        raise ValueError('Video must be a nonempty file no larger than this client’s 50 MiB limit.')
    boundary = uuid.uuid4().hex
    mime = mimetypes.guess_type(path.name)[0] or 'video/mp4'
    header = (f'--{boundary}\r\nContent-Disposition: form-data; name="video"; '
              f'filename="recording{path.suffix.lower()}"\r\nContent-Type: {mime}\r\n\r\n').encode()
    body = header + path.read_bytes() + f'\r\n--{boundary}--\r\n'.encode()
    result = request(base_url, '/transcribe', body, {'Content-Type': f'multipart/form-data; boundary={boundary}'})
    if not isinstance(result.get('text'), str) or not result['text'].strip():
        raise RuntimeError(f'No usable transcript returned: {result}')
    if result.get('audio_used') is not False:
        raise RuntimeError('Server did not confirm visual-only inference (audio_used: false).')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default=os.environ.get('FLARE_API_URL', DEFAULT_URL))
    parser.add_argument('video', nargs='?', help='MP4/WebM file; omit to check readiness')
    args = parser.parse_args()
    try:
        result = transcribe(args.video, args.url) if args.video else ready(args.url)
        print(json.dumps(result, indent=2))
    except (RuntimeError, ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

# SilentOS

SilentOS turns audio-free webcam recordings into editable text through a hosted
FLARE lip-reading model. You can assemble several clips into one command, hand a
reviewed message to HeyClicky, or share reviewed captions with a second device.
These are separate flows: recording or receiving a transcript never sends a
message by itself.

## Run locally

Python **3.9 or newer** is required. The application and its MCP connector use
only the Python standard library. No local GPU, model download, API key, or extra
Python packages are needed. Use a current browser; Chrome has been used for the
local camera workflow.

On macOS or Linux, from this repository:

```sh
python3 server.py
```

Open `http://localhost:8000`, allow camera access, and press **Start**. Use
`--port 8001` if the port is occupied. Stop a foreground server with Ctrl+C.
Restart the server and reload the page after pulling updates.

On Windows, double-click `Start-SilentOS.cmd`. The PowerShell launcher uses
`python.exe`, runs the server in the background, and opens the browser. Logs are
`server.log` and `server-error.log`. From PowerShell:

```powershell
./Start-SilentOS.ps1 -Stop
./Start-SilentOS.ps1 -ApiUrl https://CURRENT-FLARE-HOST -Port 8000
```

The Windows launcher has not been exercised on this Mac.

## Record and assemble a command

1. Press **Start** and mouth a phrase facing the camera in good light.
2. **Finish phrase** submits the current clip and pauses capture. **Start** adds
   another clip to the same command. Continuous mode records the next clip while
   an earlier clip is processing, subject to queue capacity.
3. **Finish command** stops capture and waits for outstanding transcripts. Review
   or edit **Current command** when it becomes ready.
4. Choose a destination below, or copy the full transcript. **New command** starts
   a separate instruction without clearing transcript history.

FLARE text is appended both to transcript history and to the current assembly.
Edits to **Transcript** affect the copyable history; edits to **Current command**
affect the handoff and room caption. Clips are joined in order with a space.
Missing words, split words, punctuation, and overlaps are not guessed or repaired.
Ready means all recorded clips returned, not that the words or intent are correct.

The clip choices are 3, 5, 6, 8 (default), 15, 30, and 60 seconds. A 60-second clip
stops about 150ms early to leave time for recorder shutdown. Clips shorter than
half a second are skipped; empty or over-limit clips fail. There is one upload in
flight and at most two waiting clips. Capture pauses when the queue is full.

Recording/transcription failures mark an unfinished command incomplete and discard
unsent clips without retrying uploads. Use **New command** and repeat the
instruction. A late result can still appear in history, but cannot make an
incomplete command ready. An idle camera disconnect does not invalidate a command
that already finished.

The mirrored preview uses no microphone audio. Captions arrive after a whole clip
is uploaded and processed; this is not streaming word-by-word transcription. The
Details panel shows timing and connection information. Assemblies live in browser
memory and are lost on reload.

## Tasks: HeyClicky, Deep Agent, and Photon

Record and finish a command, or edit/select text in **Transcript** and click
**Use transcript / selection as task**. SilentOS routes the reviewed input:

- **General tasks → HeyClicky**, as text through the local SilentOS HTTP API.
  Examples: open a file, find a presentation, or perform supported browser work.
  Choose execute or plan-only mode. A connected active HeyClicky agent must pull
  the task; the app already supports typed input and needs no microphone conversion.
- **Optional general tasks → Deep Agent**, when explicitly selected in the task
  provider field. It runs in a separate Python 3.11+ worker, cannot claim HeyClicky
  work, and currently has read-only local queue context rather than OS control.
- **Messages → Photon 2.0**, through a separate local worker. Specify app, recipient,
  and exact message. Draft mode saves a local preview; send mode uses configured
  Photon sender/contact IDs. No personal messaging account is assumed.
- **Inbound iMessage → Deep Agent draft → Photon reply**, through the optional
  companion. Only configured senders are accepted, and every generated reply must
  be reviewed and approved in the local UI before the worker can send it.

Automatic routing uses explicit message phrasing, such as `Send Alex on WhatsApp
saying I'll be there soon`. Incomplete messaging requests remain for review. The
handoff type selector and editable fields support corrections. The opt-in automatic
queue checkbox remains off on reload. It queues finished tasks; it does not start
a HeyClicky job, bypass approvals, or invent destinations.

The persistent queue uses atomic per-provider claims and request keys. Old queue
items without a provider are retained as legacy and never automatically executed.
See [HEYCLICKY.md](HEYCLICKY.md) for the text API/worker, [PHOTON.md](PHOTON.md)
for account configuration and messaging constraints, and
[COMPANION.md](COMPANION.md) for the isolated two-way Photon + Deep Agent setup.
The configured Photon project has been authenticated and its assigned iMessage
conversation has been read successfully. A real outbound send and a complete live
Deep Agent reply approval remain manual end-to-end checks.

## Two-device captions and optional speech

This is a one-way caption demo. A speaker reviews text on the Mac; a listener
receives it and can enable browser text-to-speech. It does not provide live video,
return audio, a telephone call, or automatic caption publication.

For two devices on a trusted LAN or hotspot that permits device-to-device traffic:

```sh
python3 server.py --lan
```

Open `http://localhost:8000` on the speaker's Mac, because camera access requires
localhost. Under **Two-device conversation**, create a room, enter the Mac's LAN
IPv4 address, copy the listener link, and share it privately. Find the address in
Wi-Fi settings or use `ipconfig getifaddr en0` on macOS (the interface may differ).
The UI explains when LAN sharing is off; it is off by default.

The listener opens the link on the second device and can tap **Enable voice** and
**Test voice**. No listener camera or microphone permission is needed. Invitation
credentials stay in that browser tab's session so reloading continues to work.
When session storage is blocked, the invitation stays in the URL fragment instead.

On the speaker, finish and review a command, then click **Send reviewed command
to listener**. Captions are limited to 2,000 characters. Network retries reuse the
same caption and request key, avoiding duplicates. To send a separate caption,
use **New command**. The receipt means text was fetched, not that speech played.
Messages received before voice is enabled are shown as text only.

Rooms use HTTP polling, expire after one hour, and are held only in server memory
(up to 20 rooms and 200 captions per room). A restart clears all rooms. Anyone with
the listener link can read that room's captions. This development demo uses
unencrypted HTTP: use a trusted private network and do not expose it to the
internet. Remote clients can only load the listener and read/acknowledge captions
with its token. Camera uploads, command history, and room publication stay local.
A real second-device connection and audio playback still need manual validation.

## Hosted FLARE service

The current default endpoint is:

`https://identity-inspection-cfr-items.trycloudflare.com`

Readiness is `GET /ready`; transcription is `POST /transcribe` with multipart field
`video`. The local backend forwards clips, validates a nonempty transcript and
`audio_used: false`, then removes temporary video files. Uploading sends your clip
to the team's hosted service. This repository contains the clients and local
proxy, not the remote model server or its deployment source.

On November 15, 2026 the endpoint reported ready with `flare-llm-large` loaded on
an NVIDIA A100 and `max_clip_seconds: 60`. This is a temporary Cloudflare tunnel;
if the allocation or tunnel restarts, update the URL again. A client-side change
cannot revive an expired model service.

Override the address without changing code:

```sh
python3 server.py --api-url https://CURRENT-FLARE-HOST
```

Or set `FLARE_API_URL`. A replacement must expose the FLARE HTTP API; a notebook
login URL is not a substitute. Without it the local UI works, but transcription
does not. Timeouts are not automatically retried because inference may still be
running upstream.

The local upload limit is **50 MiB**. The hosted service currently reports a
60-second duration limit. Longer recordings can hit the upload or processing
limits even when their duration is valid. Existing project notes report a real
60-second capacity test; that does not establish long-form recognition accuracy.
The upstream preprocessing/model changes are managed outside this repository.

The standalone Python and JavaScript helpers are also available:

```sh
python3 flare.py                       # Check readiness
python3 flare.py /absolute/path/clip.mp4
python3 flare.py --url https://CURRENT-FLARE-HOST /absolute/path/clip.webm
```

```js
import { transcribeVideo } from './flare.mjs';
const result = await transcribeVideo(recordedBlob); // optional second arg: API URL
```

Use consented raw MP4/WebM recordings with one front-facing face, preferably
2–5 seconds. Do not manually crop/resize. Browser capture should set `audio: false`.
Direct browser calls to the hosted helper require appropriate upstream CORS;
Python success alone does not prove browser access.

## Run checks and understand coverage

Application runtime: Python 3.9+. Regression tests additionally need Node.js 22+.
From the repository:

```sh
python3 run_checks.py
```

The runner executes every top-level JavaScript test and all Python unit tests.
They cover clip queues and duration, command boundaries, readiness races, parser
failures, handoff retries, provider-isolated claims, companion approval state,
Photon inbound validation, SQLite concurrency/restarts, MCP stdio, local API
access, room publication/receipts, invitation reloads, and client response
validation. They never call a real model, upload a real camera clip, or send a
real message.

A live HeyClicky agent has read and claimed a command, prepared an iMessage draft,
and reported the outcome. The user then sent that draft manually. Continuous
pickup, automated sends, WhatsApp, SMS, a complete fresh FLARE-to-message run,
second-device speech, and Windows startup remain unverified. See [AUDIT.md](AUDIT.md)
for the latest review findings and checks.

The prism background is adapted from Componentry under its MIT license; attribution
is retained in `static/COMPONENTRY-LICENSE.txt` and `static/prism.js`.

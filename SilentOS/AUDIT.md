# SilentOS review — November 14, 2026

Scope: all tracked Python/JavaScript sources, browser pages, launchers, tests, and
documentation on GitHub main, starting at merge `a90d506`. The remote FLARE model
server is not in this repository and was not source-audited.

## Verified issues fixed

| Issue | Result |
|---|---|
| Listener removed its invitation fragment, so reload lost access | Keep credentials in this tab's session; retain the fragment if storage is blocked |
| Lost room-send responses could cause duplicate captions on retry | Frozen request payload and per-room idempotency key; duplicate requests return the original caption |
| Room creation/publication bypassed local Host and session-token checks | Apply the same local origin/token boundary as message commands; token-authenticated listener access stays available remotely |
| UI offered second-device sharing even when server bound only to localhost | Report LAN availability and explain the explicit `--lan` startup requirement |
| A failed reparse could leave an old recipient/message available | Clear those fields as soon as a new parse starts |
| Old handoff request cleanup could lock another command's fields | Limit that cleanup to its source command |
| Queue polling replaced unchanged DOM every five seconds | Retain unchanged rows and ignore stale refresh responses |
| Delayed readiness could start recording after Finish/New command | Recheck the selected command and current controls after awaiting readiness |
| Camera loss while idle invalidated a finished command | Mark incomplete only when capture was interrupted |
| Browser FLARE helper lacked size and JSON-object validation | Reject over-50-MiB clips before uploading; validate response shape |
| Draft instructions did not explicitly protect existing drafts | Require blocking on a nonempty draft; forbid Send/Return in draft mode |
| Malformed command IDs caused storage errors | Validate IDs before database access |
| Documentation contradicted itself and used a nonexistent recovery path | Rewrite around the current setup, features, and actual validation limits |
| Room tests inherited and reran all backend tests | Separate shared HTTP fixtures from test classes; count distinct cases |

The recording status toolbar now stays beside the camera workflow rather than
being pushed below room setup. Caption and listener scripts are separate assets
with targeted regression tests. Room retries intentionally require reloading old
pages after the server update so they use request keys and the local token.

## Validation

Run `python3 run_checks.py` from the repository. It discovers all top-level Node
tests and Python unit tests. No test sends a real message or uploads camera media.

Coverage includes: clip serialization/backpressure, 60-second capture, command
boundaries, recording readiness races, stale/failed parsing, handoff retries,
SQLite persistence/concurrent claims, result-token/draft guards, a real MCP stdio
subprocess, room roles/access/expiry/idempotency, invitation reloads, caption
receipts, and browser FLARE response validation.

The final local run passed **8 JavaScript suites and 18 distinct Python tests**.
A live browser smoke check on an isolated localhost instance parsed a typed test
command correctly, showed the LAN-off explanation, and reported no browser errors.
It did not queue a real message or send anything externally.

The current hosted `/ready` endpoint was also checked live: `model_loaded: true`
and `max_clip_seconds: 60`. This verifies readiness only, not recognition accuracy,
real recording duration, or future service availability.

Existing live checks established that a fresh HeyClicky agent can read and claim
queue work, prepare an iMessage draft, and report the result. The user manually
sent that draft afterward. Automated sending was not validated.

## Remaining limits

- No verified external event trigger or always-on HeyClicky listener. An active
  agent job must pull from the queue; sustained polling remains untested.
- WhatsApp, SMS/iPhone forwarding, automatic sends, and a fresh camera-to-message
  run need explicit live tests with the user's selected destination.
- Browser camera/device behavior and recognition accuracy cannot be established
  by simulated recorder tests alone.
- A physical second-device connection and actual text-to-speech playback are not
  established by local HTTP/DOM tests.
- Windows startup is inspected but not run on Windows; the host is macOS.
- The hosted model's temporary allocation/tunnel and its separate source remain
  the model operator's responsibility.
- This is a local/trusted-LAN development application. Local queue claims avoid
  automatic redelivery, but cannot guarantee exactly-once delivery through another
  application's UI or independently verify an agent's claimed send result.

## Subsequent task routing update

The messaging-to-HeyClicky route described in the original audit has been replaced:
general task text now reaches HeyClicky through the SilentOS HTTP API and Photon
2.0 handles messages. See HEYCLICKY.md and PHOTON.md for current behavior. The
updated local check run passes 8 JavaScript suites and 24 Python tests, including
a real MCP subprocess using the HTTP task API, provider-isolated claims, legacy
queue migration, and simulated Photon contract/uncertainty checks. Photon account
setup and real sends remain unverified.

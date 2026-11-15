# SilentAgent

SilentAgent sends FLARE's transcript to HeyClicky through HeyClicky's existing
typed **Ask HeyClicky...** input. It does not use HeyClicky's microphone, a task
queue, an MCP polling worker, Photon, or a second agent.

## Build

```sh
./build-app.sh
```

The executable is `SilentAgent.app/Contents/MacOS/silent-agent`. Packaging it as
an app gives macOS Accessibility permission a stable identity across builds.

## Send transcript text

Pass text as an argument:

```sh
SilentAgent.app/Contents/MacOS/silent-agent "Open my Notes app"
```

Or pass FLARE's `result.text` on standard input:

```sh
printf '%s' "$FLARE_TRANSCRIPT" | SilentAgent.app/Contents/MacOS/silent-agent
```

For a safe first test, insert the text without submitting it:

```sh
SilentAgent.app/Contents/MacOS/silent-agent --no-submit "This is a text-input test"
```

On first use, macOS requests Accessibility access. Add `SilentAgent.app` in
**System Settings > Privacy & Security > Accessibility** and enable its toggle.
Camera access remains the responsibility of the FLARE capture app.

## Call it after FLARE

The only handoff needed after receiving FLARE's JSON response is:

```python
import subprocess

subprocess.run(
    ["/absolute/path/to/SilentAgent/SilentAgent.app/Contents/MacOS/silent-agent"],
    input=result["text"],
    text=True,
    check=True,
)
```

The adapter activates HeyClicky, opens its native typed-input surface, writes the
transcript, and presses its native Send button. Use `--no-submit` while validating
the integration so a test phrase does not run as a real HeyClicky request.

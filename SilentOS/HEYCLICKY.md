# HeyClicky general tasks from the SilentOS API

HeyClicky 1.1.3 already has two input paths: its microphone shortcut and a typed
**Ask HeyClicky…** chat box. There is no need to convert audio or modify the signed
app. Typed chat can start a background agent. Custom MCP connectors are available
inside a fresh agent session, even when normal talk chat cannot access them.

SilentOS now supplies **general task text through its local HTTP API**. The MCP
connector translates its tools into API requests; it no longer reads the queue
SQLite file directly. Messaging is routed separately to Photon 2.0.

## Flow

`FLARE → Transcript/assembled task → SilentOS API → HeyClicky agent → result API`

Record and finish a command, or edit/select text in **Transcript** and click
**Use transcript / selection as task**. The handoff panel shows the task text.
Choose **Execute with HeyClicky** or **Review plan only**, then queue it. No app,
recipient, or message fields are required for general tasks.

Examples: `Open Downloads`, `Find my latest presentation`, or `Research this topic`.
The exact task goes to HeyClicky; its tools determine feasibility. Unsupported,
ambiguous, or sensitive operations may require clarification/approval. Messaging
must use Photon. Mixed general-task/message instructions should be split; the
agent must not send communications through its UI as a fallback.

Automatic routing uses explicit messaging patterns, not an LLM classifier. It
holds message-like but incomplete phrases for review. Use the type selector when
needed; selecting General task does not permit bypassing messaging routing.

## Connect or update the local connector

1. Run `python3 server.py` and open localhost.
2. Click **Copy HeyClicky connector command**.
3. In HeyClicky: **Settings → Integrations → Add custom connector**. Name it
   SilentOS, open **Advanced → Command on this Mac**, and enter the command.
4. For separate fields on this Mac:
   - Command: `/usr/bin/python3`
   - Arguments: `/absolute/path/to/SilentOS/heyclicky_mcp.py --api-url http://127.0.0.1:8000`
5. Quote paths with spaces. No Photon key is passed to HeyClicky. Approve access
   only if you want HeyClicky and its model providers to process queued task text.

If already connected, restart/reconnect the connector so the process loads the
new HTTP client and tool schemas. Copying the command from the UI includes its
actual server port. `SILENTOS_API_URL` is an optional alternative. Only HTTP
localhost/127.0.0.1 origins are accepted; remote URLs and redirects are rejected.

The connector needs the local server running. It obtains the current session token
from the local configuration endpoint, then accesses the task endpoints. It does
not retry ambiguous writes or persist the token. A stopped API produces a clear
connection error, not guessed input from the screen or microphone.

## API and tools

Local JSON requests require `X-SilentOS-Token` from `GET /api/config`, plus the
allowed localhost Host/Origin. The API remains unavailable to remote LAN clients.

- `POST /api/tasks/parse`: `{text, kind: "auto" | "task" | "message"}` returns routing.
- `POST /api/tasks`: `{text, request_key, mode?}` routes and queues raw text. General
  tasks default to execute; messages default to local preview. A stable request key
  deduplicates a lost-response retry. Incomplete message instructions are rejected.
- `GET /api/tasks`: general task text/status only, excluding Photon messages.
- `POST /api/tasks/next`: atomically claims one HeyClicky task and returns its token.
- `POST /api/tasks/result`: `{id, claim_token, outcome, detail}` reports
  `completed`, `reviewed`, `blocked`, or `uncertain`.

For edited structured fields, the browser uses `POST /api/commands`; the shared
history endpoint includes both providers. The result API rejects Photon work.
Photon and HeyClicky each have at most one outstanding claim, so they cannot steal
one another's work or block each other unnecessarily. Historic untyped queue items
are marked legacy and never dispatched by either worker.

The MCP tools retain the names `silentos_list_commands`,
`silentos_claim_next_command` (optional `wait_seconds`, 0–20), and
`silentos_report_result`. They now operate on general tasks through the API.
Complete/reviewed/blocked/uncertain are terminal. A crash never automatically
reclaims a task; inspect possible effects before deciding whether to repeat it.

## Start an agent worker

Click **Copy HeyClicky task starter** and paste it in HeyClicky's typed chat. It
asks a background agent to claim general task text, respect execute/review mode,
report verified results, and continue waiting for new tasks until stopped.

A connector does not wake or start a HeyClicky job by itself. No supported public
HTTP input/start-job endpoint has been verified for the installed app. The worker
must be started in HeyClicky once; it must remain active for automatic pickup.
App shutdown, sleep, tool/session limits, or approvals can stop it. Do not describe
this as a verified always-on operating-system service.

## Validation and limitations

Automated tests verify raw-text routing, provider isolation, old database migration,
message guards, and an actual MCP subprocess reading/claiming/reporting through a
live localhost HTTP server. No automated test opens a real file, sends messages,
or uses an external model.

Earlier live checks verified typed HeyClicky chat, agent access to the old
connector, and one iMessage draft. The user manually sent it afterward. That old
message-UI route is now superseded by Photon and is not proof that a Photon sender
works. Fresh general-task API behavior and a sustained active worker require live
validation; real Photon sends require separate account/channel setup.

# Photon + Deep Agent companion

The companion is an optional second worker. It adds two isolated capabilities:

- A reviewed SilentOS task can be sent to a Deep Agent instead of HeyClicky.
- An allowlisted inbound Photon iMessage can receive a Deep Agent reply draft.
  The draft is shown in the local SilentOS UI and is never sent until a person
  approves it there.

The normal app still runs with Python 3.9 and no extra packages. HeyClicky stays
the default task provider, the direct FLARE-to-HeyClicky bridge is unchanged, and
`server.py` does not start the companion automatically. Deep Agent tasks can run
without Photon configuration; only the inbound/reply portion is then disabled.

## Set up the separate worker

Deep Agents currently requires Python 3.11 or newer. From this directory:

```sh
python3.11 -m venv .companion-venv
source .companion-venv/bin/activate
python -m pip install -r companion-requirements.txt
```

Set the model using LangChain's `provider:model` form and provide the matching
provider credential. For example, when using an OpenAI model:

```sh
export DEEPAGENT_MODEL=openai:REPLACE_WITH_MODEL
export OPENAI_API_KEY=REPLACE_LOCALLY
```

Do not put model or Photon secrets in the browser, example configuration, chat,
or Git. Keep them in the worker environment or an ignored local secret manager.
Selected Deep Agent tasks and allowlisted inbound message text are sent to the
configured model provider to generate a result or draft; ordinary HeyClicky tasks
and unrelated Photon messages are not included in that model request.

## Configure the Photon iMessage channel

Copy `photon.example.json` to `.silent/photon.json` and configure the normal
Photon project credentials. In its `companion` object:

- Set `enabled` to `true`.
- Set `agent_id` to the Photon User ID assigned to the iMessage agent.
- Set `agent_handle` to the exact iMessage handle assigned to the Photon agent.
- Add only trusted human handles to `allowed_senders`.
- Leave `platform` as `imessage`; this companion does not accept other channels.

The allowlist is an additional code-side boundary, not a replacement for Photon
channel configuration. Complete Photon 2.0's iMessage assignment and inbound
conversation setup in its dashboard. The worker accepts only direct, received,
human-to-agent, plain-text iMessages whose sender and receiver handles match the
local configuration.

## Run it

Start the existing app normally in one terminal:

```sh
python3 server.py
```

With the companion virtual environment active, start the optional worker in a
second terminal:

```sh
python companion.py --api-url http://127.0.0.1:8000
```

`python companion.py --once` performs one diagnostic cycle and exits. The worker
reads the current ephemeral session token from the localhost server for each
operation and never persists it. Its durable inbox is `.silent/companion.sqlite3`.
The local UI reports whether the worker heartbeat is active and whether that
worker successfully enabled Photon polling.

For a local command, select **Deep Agent companion** before queueing. For an
inbound message, review and optionally edit the proposed reply in **Photon
companion inbox**, then click **Approve and send through Photon**. Approval only
moves the reply into the worker's send queue; Photon acceptance is recorded
separately and is not a delivery or read receipt.

## Safety and failure behavior

- No inbound message is automatically answered.
- Deep Agent has one read-only SilentOS integration tool for recent queue context.
  Deep Agents' built-in filesystem, shell, and subagent tools are explicitly
  disabled. It has no Photon send tool and cannot bypass local approval. The
  context omits outbound message bodies and recipients.
- Claims are provider-specific: the companion cannot claim HeyClicky work, and
  the HeyClicky connector cannot claim Deep Agent work.
- Execute-mode Deep Agent results must explicitly report `COMPLETED` or `BLOCKED`.
  An unlabeled or unsupported action response is stored as blocked rather than
  falsely presented as a completed OS action.
- Duplicate Photon message IDs are ignored. A changed payload reusing an ID is
  rejected.
- A definitive configuration error becomes `blocked`. An ambiguous network or
  Photon response becomes `uncertain`. Blocked items can be manually returned
  to drafting or approval after the cause is fixed. Uncertain sends cannot be
  retried because Photon may already have accepted them; inspect its dashboard.
- Stopping the companion leaves the existing recording, typed-input, HeyClicky,
  outbound Photon, and two-device caption workflows running normally.

Automated tests simulate both integrations. A real Photon iMessage account,
Deep Agent model call, delivery, and end-to-end approval still require manual
validation with the team's credentials.

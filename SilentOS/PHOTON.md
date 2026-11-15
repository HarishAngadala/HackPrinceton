# Photon 2.0 messaging setup

SilentOS uses **Photon Beta/2.0**, not Stable Spectrum. The API origin is
`https://api.photon.codes/v1`, with a `pho_prj_...` project and a Bearer API key.
The integration has been authenticated against a Photon project and verified to
read its assigned iMessage conversation. Automated tests simulate sends; **no real
outbound Photon message has been sent or delivered by this integration yet**.

## Local configuration

1. Create your Photon 2.0 account/project at <https://app.beta.photon.codes> and
   configure the intended messaging channel/sender there. Complete the required
   platform setup in Photon. This code does not provision accounts, numbers, or
   subscriptions, and cannot bypass platform recipient restrictions.
2. Copy `photon.example.json` to `.silent/photon.json` beside `server.py`. Keep the
   real file local; `.silent/` is ignored by Git. On macOS/Linux, use owner-only
   permissions (`chmod 600 .silent/photon.json`).
3. Fill in the project ID and API key. Alternatively set `PHOTON_API_KEY` in the
   environment that launches SilentOS. Use `PHOTON_CONFIG_FILE` to select another
   local file. Never put the real key in the example, browser UI, chat, or Git.
4. For each intended destination, configure one contact with:
   - `name`: exact alias you will use in the transcript/recipient field.
   - `app`: `imessage`, `sms`, or `whatsapp`.
   - `platform`: `imessage`, `sms`, `whatsapp`, or `whatsapp_business` as appropriate.
   - `space_id`: the existing, verified direct conversation in this project.
   - `sender_id`: the configured agent's Photon User ID.
   - `recipient_id`: the intended recipient's Photon User ID.
5. Restart the local server/reload the page after changing its launch environment.
   The backend reads the local contact config for each send. A configured file is
   not a live channel/identity test.

The UI does not collect credentials. It reports whether configuration is present.
Names are matched case-insensitively against this explicit contact allowlist. An
unknown or duplicate name is blocked. SilentOS fetches the Space and checks its
channel, direct kind, and exact sender/recipient participants before POSTing text.
It never silently changes channels or creates a guessed recipient conversation.
The sender is the Photon identity you configure, not necessarily your personal
Messages or WhatsApp account.

## Recording or typing an outbound message

For example: `Send Example Contact on iMessage saying I'll be there soon`.
Finish the command or use **Use transcript / selection as task**, review the fields,
and choose:

- **Prepare draft only / Save message preview**: stores a local preview. Photon
  is not contacted, and no draft is placed in Apple Messages or WhatsApp.
- **Send once through Photon**: queues an outbound request for the configured
  contact. The local Photon worker handles it without a HeyClicky agent. The UI
  disables real sends when no configuration is present.

A background worker runs with `server.py`, claims only Photon commands, and uses
`silentos-<command-id>` as the idempotency key. It does not automatically replay
claimed, blocked, or uncertain commands. Historic commands without a provider
remain `legacy` and are not automatically dispatched after updating.

**accepted** means Photon returned HTTP 202 and a Message ID, not delivered/read.
The ID appears in queue history; use Photon logs/dashboard to verify delivery.
This revision does not ingest delivery webhooks. A timeout or ambiguous response
becomes **uncertain**; inspect Photon before repeating. A definitive rejection or
missing configuration becomes **blocked**. Automatic retries are not performed.

Shared iMessage lines can send only under their documented assignment/inbound
conversation rules. SMS requires appropriate sender/recipient platform permissions
and campaign eligibility where applicable. WhatsApp Personal and Business have
different setup and capabilities. An API key alone does not establish any of these.

## Optional two-way Deep Agent companion

The same Photon 2.0 project can also provide an approval-gated iMessage companion.
This is a separate `companion.py` process: it polls allowlisted inbound messages,
asks Deep Agent for a candidate reply, and stores the draft locally. It cannot send
until a person approves the draft in SilentOS. The normal outbound Photon worker,
HeyClicky task queue, and direct FLARE-to-HeyClicky bridge continue independently.

Add the `companion` object shown in `photon.example.json`, then follow
[COMPANION.md](COMPANION.md). Only iMessage is enabled for this inbound flow. The
agent and human handles must match the Photon message snapshot exactly, the Space
must be direct, and the content must be received plain text. This integration uses
polling rather than a public webhook so the local demo does not need an inbound
internet-facing endpoint.

## References

- Version selection: <https://photon.codes/docs/llms.txt>
- Photon 2.0 getting started: <https://photon.codes/docs/beta/index>
- Send contract and restrictions: <https://photon.codes/docs/beta/api-reference/messages/send-a-message>
- Machine-readable schema used during implementation: <https://api.photon.codes/openapi.json>

The adapter uses the documented `spaceId`, `senderId`, and text content fields,
a required idempotency header, and HTTP 202 acceptance. It intentionally uses no
Stable Spectrum credentials, SDK, or API host.

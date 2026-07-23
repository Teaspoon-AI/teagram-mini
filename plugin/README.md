# openclaw-teagram-realtime

The OpenClaw **realtime-voice provider** for teagram-mini. It connects OpenClaw's
gateway-relay Talk path to the teagram-mini brain. Plain ESM with **no build
step**. It requires **Node ≥ 22** (it uses the global `WebSocket`).

- npm: `@teaspoon-ai/openclaw-teagram-realtime`
- Registers the `teagram` realtime-voice provider (see `openclaw.plugin.json`).
- Pairs with the brain in this repository (`brain/teagram_mini_brain/gateway_server.py`).

## Install and enable

```bash
# from a checkout (local dev):
openclaw plugins install --link ./plugin
openclaw plugins enable teagram-realtime
# or, once published:
# openclaw plugins install @teaspoon-ai/openclaw-teagram-realtime
```

Configure in `~/.openclaw/openclaw.json`:

```jsonc
"talk": {
  "realtime": {
    "provider": "teagram",
    "mode": "realtime",
    "transport": "gateway-relay",
    "brain": "none",                        // the teagram-mini brain orchestrates — don't double-respond
    "providers": { "teagram": {
      "url": "ws://127.0.0.1:7861/talk",    // the teagram-mini brain's /talk WS
      "voice": "af_heart",                   // optional: a voice id the engine provides
      "token": "…"                           // optional: must match the brain's GATEWAY_TOKEN
    } }
  }
}
```

The plugin appends `voice`, `language`, and `token` to the brain WebSocket URL
as query parameters for each session. The `token` value can also come from the
`TEAGRAM_MINI_GATEWAY_TOKEN` environment variable.

## Tests

```bash
npm test           # syntax gate (node --check) — no brain needed, CI-safe
npm run test:live  # full bridge<->brain integration harness — needs a running brain + Node ≥ 22
```

`test/bridge_harness.mjs` exercises the real
`createBridge → connect → sendAudio → onAudio/onTranscript` path against a
running brain, with no OpenClaw gateway in the loop.

## Status

The plugin lives in `teagram-mini` (`plugin/`) for now. The plugin and the
brain are two halves of one appliance and change together. npm publishes the
plugin from this subdirectory. It can move to its own public repository after
launch. MIT.

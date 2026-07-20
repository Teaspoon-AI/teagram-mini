// OpenClaw plugin entry: register the `teagram` realtime-voice provider.
//
// Install for local dev:  openclaw plugins install --link ./plugin
// Enable:                 openclaw plugins enable teagram-realtime
// Configure (~/.openclaw/openclaw.json):
//   talk.realtime.provider  = "teagram"
//   talk.realtime.mode      = "realtime"
//   talk.realtime.transport = "gateway-relay"
//   talk.realtime.brain     = "none"           // Pipecat orchestrates; don't double-respond
//   talk.realtime.providers.teagram.url = "ws://<pipecat-host>:7861/talk"
import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";

import { buildTeagramRealtimeProvider } from "./provider.js";

export default definePluginEntry({
  id: "teagram-realtime",
  name: "Teagram Realtime Voice",
  description:
    "Routes OpenClaw realtime voice (gateway-relay) to an external Pipecat " +
    "speech-to-speech server with heard-grounded barge-in.",
  register(api) {
    api.registerRealtimeVoiceProvider(buildTeagramRealtimeProvider());
  },
});

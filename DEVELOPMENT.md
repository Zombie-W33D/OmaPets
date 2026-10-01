# OmaPets project contract

**Identity:** OmaPets — `io.github.zombie-w33d.omapets`
**Owner:** Zombie_W33D
**Preview version:** `0.1.0-alpha.1`
**Status:** Portable runtime and bridge checks pass; live Omarchy lifecycle is unverified.

## User outcome

Show one OpenPets character for each locally configured Hermes profile that the
user enables. Render the pets as Omarchy-hosted Quickshell layer surfaces using
the Omagatchi click-through/window pattern. Hermes activity and explicit
response signals drive the animation and a short plain-text phrase. Each agent
can choose its own pet, placement and stay/wander mode, and can link its own
phrase files while sharing built-in defaults for categories it has not
customized.

## Supported surfaces

- Omarchy shell plugin kinds: `service` + `bar-widget`.
- The service owns one shared profile/config/event model and static pet-window
  slots; the bar widget has a private popup for controls. Do not declare a
  top-level `panel` kind just to load that popup.
- Hermes integration is a separate native Hermes plugin. It forwards only a
  validated profile ID and fixed event/category identifier through Omarchy's
  shell IPC. It never sends prompts, conversation text, tool arguments,
  credentials or model output to the renderer.
- No extra HTTP server, second Quickshell process, privileged helper, network
  lookup, audio playback or additional model call.

## Profile and data ownership

- Discover the default Hermes home and immediate local profiles under its
  `profiles/` directory. Resolve the active Hermes home using Hermes' own
  `get_hermes_home()` API in the native plugin; do not hardcode `~/.hermes` for
  profile-specific writes.
- Per-agent settings live under that profile's `omapets/` folder. A missing
  settings file means disabled; enabling a pet creates the file. Removing
  either plugin leaves user settings, linked phrase files and pet packages
  untouched.
- OpenPets packages are read-only inputs. Resolve `pet.json` and its local
  `spritesheetPath` only within the selected package; never load remote image
  URLs. Support the documented V1/V2 192x208 frame atlas layouts and use `idle`
  whenever a configured animation is missing or unsupported.
- Phrase files are UTF-8 Markdown text, not rendered Markdown: ignore blank
  lines and `#` comments, choose one line randomly, and avoid an immediate
  repeat when multiple phrases exist. An unlinked category uses the shared
  default; a linked empty file is deliberately silent.

## Explicit state contract

Activity states: `thinking`, `waiting_on_you`, `waiting_on_task`, `finished`,
`failed`. Response categories: `yes`, `no`, `success`. `success` means an agent
made something work; `finished` means its turn/task ended. Do not infer
categories by classifying user or assistant text.

Initial animation suggestions (all fall back to `idle` when unavailable):

| Signal | OpenPets animation |
| --- | --- |
| thinking | review |
| waiting_on_you | waiting |
| waiting_on_task | waiting |
| yes | waving |
| no | failed |
| success | jumping |
| finished | idle |
| failed | failed |

Initial activity phrases may be shown as small text near the pet. Response
categories may also select a phrase; phrases stay plain text and are never sent
back to Hermes.

## Security and resource limits

- The Quickshell plugin runs with the desktop user's privileges. Treat local
  profile config, pet metadata, phrase files and IPC arguments as untrusted.
- Validate profile/category identifiers, constrain paths to the relevant
  Hermes home or pet package, reject malformed/oversized data, and cap pets,
  phrases, output and event queues. Never execute content from a config or
  phrase file.
- Use fixed executable paths and argv arrays for helper/IPC invocations; no
  shell interpolation, `sudo`, token access or unbounded process output.
- Disable pets by default. An explicit UI toggle controls each profile.

## Lifecycle and IPC

- Omarchy IPC target is exactly `io.github.zombie-w33d.omapets`.
- Methods are limited to bounded status/refresh, profile-event delivery, and
  validated per-agent settings changes. Unknown profiles, invalid categories
  and oversized payloads fail closed.
- Service refreshes are serialized and generation-guarded so stale helper
  completions cannot re-enable a disabled pet or overwrite newer settings.
- The pet's layer surface is transparent, top-layer and click-through outside
  its hit region. Position is per profile; stay/wander controls movement. No
  host restart or global shell configuration mutation is part of ordinary use.

## Acceptance and verification

1. Portable tests cover profile discovery, safe path resolution, bounded config
   parsing/writes, OpenPets V1/V2 metadata, phrase parsing/selection, and the
   explicit event-to-animation/phrase contract.
2. Hermes plugin validation/doctor confirms manifest, hooks/tools and runtime
   callback signatures without enabling the plugin.
3. Omarchy manifest validation, pure-JavaScript tests and available QML lint or
   fixture tests pass.
4. Live checks, when authorized, cover hosted service loading, profile
   discovery, click-through/drag, animation, IPC, disablement and removal.
   No live install/enable/restart will be performed during this task because
   the user's chat/music must remain undisturbed. Report those checks as
   unrun—not passed.
5. Versioned conventional commits are pushed to a private GitHub repository
   named `OmaPets`. A tag is not a substitute for the unavailable live-surface
   evidence and must be described accordingly.

## Deferred

- Audio clips or TTS, networked pet downloads, prompt/text classification,
  extra LLM calls, remote profiles, and a public marketplace release.

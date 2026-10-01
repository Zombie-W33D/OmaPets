# OmaPets

[![Built for Omarchy: Plugin](https://raw.githubusercontent.com/tcballard/omarchy-badges/75975e5b5bf75e7ede3764bcd2950046f7abfe2c/badges/v1/omarchy-plugin.svg)](https://github.com/tcballard/omarchy-badges)

OpenPets characters as per-agent desktop companions in the Omarchy Quattro shell. **Development preview (`0.1.0-alpha.1`): portable checks pass; live shell behavior has not yet been verified.** No pet is shown until you enable that profile.

The hosted Quickshell service owns independent, transparent, click-through layer surfaces; the bar widget lets you show/hide pets, choose the next installed character, and switch stay/wander. Drag a pet to save its monitor-relative position. A separate, optional Hermes plugin sends lifecycle events without forwarding chat content or starting another model call. No audio is played.

## Requirements

- Omarchy 4 Quattro with Quickshell and `/usr/bin/python3` (Python 3.10+).
- A local OpenPets V1/V2 character package in `~/.hermes/pets/<id>/` containing `pet.json` and `spritesheet.webp`. This repository contains no character art or downloadable installer.
- Node.js is used only for development tests, not at runtime.
- Use a machine you trust: Omarchy shell plugins execute in the user's shell process; the Hermes plugin executes in the agent process. Review them before enabling.

## Installation (when ready to test on the desktop)

This private repository requires working GitHub Git authentication. Omarchy's plugin manager clones a **Git URL**, not a local folder:

```bash
omarchy plugin add git@github.com:Zombie-W33D/OmaPets.git --enable
```

The Hermes bridge is optional and installed **per Hermes home/profile**. Copy the two files from this checkout's `hermes-plugin/` into `<profile-home>/plugins/omapets-hermes/` (for example, `~/.hermes/profiles/aria/plugins/omapets-hermes/`). Review and validate with `hermes plugins doctor <destination> --ci`, then enable that plugin for the profile using the Hermes plugin manager. Until enabled, OmaPets can still display idle pets; you can send explicit events through Omarchy IPC.

This project was developed without installing or enabling either plugin in the running chat/music session. Desktop lifecycle and click-through are **unverified**; do not treat this preview as a release.

## One agent's config folder and custom phrases

OmaPets discovers the default `~/.hermes/` home and named profiles in `~/.hermes/profiles/`. Missing `omapets/config.json` means **disabled**. The bar widget's **Show** button creates a private config and selects the first valid installed character. Alternatively, an agent may set up its own profile folder explicitly:

```text
~/.hermes/profiles/aria/omapets/
├── config.json
└── phrases/
    └── thinking.md
```

Example `config.json` for that agent:

```json
{
  "schemaVersion": 1,
  "enabled": true,
  "petId": "socksy",
  "mode": "stay",
  "screen": "",
  "position": {"x": 0.85, "y": 0.9},
  "scale": 3,
  "animations": {"thinking": "review"},
  "phraseFiles": {"thinking": "phrases/thinking.md"}
}
```

Paths in `phraseFiles` are **relative to that profile's `omapets/` directory**, end in `.md`, and cannot contain `..` or symlinks. Each file starts with commented directions, followed by a few short plain-text phrases, **one per nonblank line**:

```markdown
<!--
Use one short phrase per line below. Keep it public and plain text.
Comments and blank lines are ignored. Delete every phrase for silence.
-->
I'm putting the pieces together.
Give me a moment to work this out.
```

Link only categories you want to customize. An **unlinked** category reads the matching shared `phrases/<category>.md`; a **linked empty** file is deliberately silent. A phrase cannot repeat immediately if the category has multiple choices. Files are displayed as plain text, not executed or rendered as Markdown. The eight category names are `thinking`, `waiting_on_you`, `waiting_on_task`, `yes`, `no`, `success`, `finished`, and `failed`.

You can override animations for the same categories using OpenPets row names: `idle`, `running-right`, `running-left`, `waving`, `jumping`, `failed`, `waiting`, `running`, or `review`. Unknown mappings fall back to `idle`. `success` means something worked; `finished` means a turn ended. **Yes/no/success are explicit signals, never guessed from an answer's words.** The optional Hermes bridge offers `omapets_signal(category)` with `yes`, `no`, or `success`; built-in lifecycle hooks handle the other states.

Profile settings and custom phrase files remain on disk if either plugin is removed. OmaPets never modifies the OpenPets package.

## Development and maintenance

```bash
./tests/run
python3 -m unittest discover -s tests -p 'test_*.py'
node --test tests/model.test.js
hermes plugins doctor ./hermes-plugin --ci
omarchy plugin validate .
```

`omarchy plugin update io.github.zombie-w33d.omapets` updates a Git-managed installation; `omarchy plugin remove io.github.zombie-w33d.omapets` removes the shell plugin, not your profile config. Hermes bridge removal is managed independently per profile. See `DEVELOPMENT.md` for current limitations and validation scope. An Omarchy restart, live enable/disable, monitor unplug, and clean install/removal still need a safe test window.

## Attribution and license

OmaPets code is MIT © 2026 Zombie_W33D (see `LICENSE`). OpenPets package format and atlas mapping follow [OpenPetsHQ/openpets](https://github.com/OpenPetsHQ/openpets); the fixed transparent layer surface and input-mask approach follows [SLcode777/omagotchi](https://github.com/SLcode777/omagotchi). No upstream source files or character art are bundled here; installed characters retain their own licenses.

# Control4 Extra Entities → Home Assistant: Design Spec

## Revision notes

- This spec originally proposed a from-scratch custom integration (`control4_extra`) with its
  own generic discovery/coordinator core. That plan was **superseded** after finding that
  `home-assistant/core`'s official `control4` integration already has mature `cover`, `light`,
  `climate`, and `media_player` platforms (device registry, retry logic, correct Director
  category/type filtering) — it just always imports all four with no way to opt out. Rebuilding
  that from scratch would have reinvented already-solved, non-trivial problems (the correct
  Control4 category name for blinds is `"blinds_shades"`, not the `"motorization"` this spec
  originally assumed) at lower quality. The plan below reflects the current, adopted approach:
  **fork the official integration and add a platform opt-in/out step.** The Blind Proxy
  protocol reference from the original draft is kept below for background, but the
  implementation no longer talks to that protocol directly — it goes through `pyControl4`'s
  `C4Blind` wrapper.
- This integration originally lived inside a private repo alongside an unrelated Control4
  DriverWorks (Lua) driver project. It was split out into its own public repo
  (`deliriumxp/control4_extra`) since the two projects share nothing but a vendor name, and a
  HACS-installable integration needs to be public/standalone anyway.
- Fixed a real bug: `strings.json`/`translations/en.json` (copied verbatim from upstream)
  contained `[%key:common::config_flow::...%]` references (e.g. for "Username"/"Password"/"IP
  address"). Those only resolve for integrations built into `home-assistant/core` — its release
  tooling expands them into literal text at build time. A HACS custom integration never goes
  through that step, so the config flow showed the raw `[%key:...%]` placeholder strings
  instead of readable labels. Fixed by resolving every reference to its literal text (looked up
  in core's own `homeassistant/strings.json`) directly in both files.
- Added a brand icon at `custom_components/control4_extra/brand/` (`icon.svg` source,
  rendered `icon.png`/`icon@2x.png`). Originally placed at a repo-root `brands/` folder on the
  assumption that showing up in HA requires a PR to the separate `home-assistant/brands` repo
  — wrong for current HA: as of **2026.3.0**, custom integrations can ship local brand images
  directly inside their own `custom_components/<domain>/brand/` directory (`icon.png`,
  `icon@2x.png`, optional `dark_*`/`logo*` variants) and HA reads them straight from there, no
  external PR needed (see the Feb 2026 "Custom integrations can now ship their own brand
  images" Home Assistant developer blog post). Moved the icon there accordingly. On HA
  versions older than 2026.3.0 this integration falls back to a generic icon — submitting to
  `home-assistant/brands` under `custom_integrations/control4_extra/` remains the option for
  that case, but is a separate, external PR to request explicitly if ever needed.

## Overview

`custom_components/control4_extra/` is a HACS custom integration forked from
`home-assistant/core`'s `homeassistant/components/control4/` (Apache-2.0), under a different
domain (`control4_extra`, not `control4`, since shadowing a core integration's domain via
`custom_components` is fragile and unsupported). It keeps all four upstream platforms
(`cover`, `light`, `climate`, `media_player`) but adds two things upstream doesn't have:

1. An options-flow step to choose which of those platforms are actually enabled for a given
   household. Default: `cover` only — this household handles light/climate via KNX and doesn't
   want Control4 duplicating those entities.
2. A per-cover "dry contact" flag for blinds driven by a relay with no real position feedback
   (see "Dry-contact covers" below) — their open/close buttons stay active regardless of
   Control4's (unreliable) reported status.

No C4 driver is written or modified for this integration. HA talks to Control4 Director
directly over the network; Control4 project configuration is untouched.

## Goals

- All four upstream platforms available, but **opt-in per household** via the options flow
  (`CONF_ENABLED_PLATFORMS`, default `["cover"]`) instead of hardcoded.
- Otherwise behave exactly like the upstream integration: same auth flow, same device
  registry/naming, same category/type-based discovery, same retry-on-`BadToken` handling.
- Track a **current** `pyControl4` release (`2.0.2`, not the `1.5.0` upstream still pins) —
  picked up a real latent-bug fix in the process (see "pyControl4 version" below) — vendored
  in-tree rather than pip-installed, so it can't conflict with the official integration's own
  `1.5.0` pin when both run in the same Home Assistant instance.
- Packaged for HACS from the start (custom repository, not a HACS-default one).

## Non-goals

- Anything upstream's `control4` integration doesn't already do (e.g. alarm_control_panel /
  binary_sensor — a past PR for these was closed unmerged; adding them here would mean writing
  the platform ourselves, not porting one). Not part of this pass.
- Feature parity beyond what's forked — no attempt to build a more "generic" discovery model;
  matching upstream's proven category/type approach exactly was the point.
- Contributing the platform-toggle feature upstream — this fork is for this household's own
  use, not a PR to `home-assistant/core` (though nothing here prevents that later).

## pyControl4 version: 2.0.2, not upstream's pinned 1.5.0

Verified by downloading both wheels and diffing: 1.5.0 (what `home-assistant/core`'s manifest
currently pins) uses camelCase methods (`getAccountBearerToken`, `getAllItemInfo`,
`setLevelTarget`, ...); `2.0.2` (current PyPI release) renamed everything to snake_case with
**no backwards-compatible aliases** — a straight port of upstream's files against `2.0.2`
would fail at the first API call. Full rename map applied across `__init__.py`,
`director_utils.py`, `config_flow.py`, `cover.py`, `light.py`, `climate.py`, `media_player.py`;
verified with zero leftover camelCase call sites and a real import test against the actual
`homeassistant` (2026.2.3) and `pyControl4==2.0.2` packages in a scratch venv.

Two behavioral (not just naming) differences handled:
- `get_all_item_info()` / `get_ui_configuration()` return already-parsed JSON in 2.0.2 (1.5.0
  returned the raw response text, requiring a `json.loads()` the caller had to do itself) —
  removed the now-redundant `json.loads()` calls in `__init__.py`.
- `get_all_item_variable_value()` normalizes the literal string `"Undefined"` to `None` in
  2.0.2. This actually fixes a latent bug in upstream's own `cover.py`: `int(level)` on an
  undefined `Level` variable would raise under 1.5.0; under 2.0.2 it cleanly hits the
  existing `if level is None: return None` guard instead.

### pyControl4 is vendored, not pip-installed

Found in production use: a household running both the official `control4` integration
(pinned `pyControl4==1.5.0`) and this one (originally pinned `pyControl4==2.0.2`) got
`AttributeError: 'C4Account' object has no attribute 'get_account_bearer_token'. Did you mean:
'getAccountBearerToken'?` — the 1.5.0 (camelCase) build was the one actually active. Home
Assistant runs every integration in one shared Python process/`site-packages`; only one
version of a same-named top-level package can be installed at a time, so two integrations
pinning different *exact* versions of `pyControl4` fight over which one wins on each restart
(whichever gets set up last during that boot wins the reinstall - not stable).

Fixed by vendoring pyControl4 2.0.2's source directly into
`custom_components/control4_extra/vendor/pycontrol4/` (Apache-2.0, `LICENSE` included in that
directory) instead of depending on the pip package: every `from pyControl4.x import Y` became
`from .vendor.pycontrol4.x import Y`, and two of pyControl4's own internal modules
(`blind.py`, `climate.py`, `light.py`, `room.py`, `__init__.py`) had an absolute
self-import (`from pyControl4 import C4Entity`) changed to a relative one (`from . import
C4Entity`) so they resolve within the vendored copy rather than reaching for a top-level
`pyControl4` install. `manifest.json`'s `requirements` is now empty - nothing to pip install,
nothing to conflict with the official integration's own pin. Verified with the same import
test as above, but with `pyControl4` actively *uninstalled* from the scratch venv first, to
prove there's no remaining dependency on a global install.

## Architecture

```
┌──────────────────────────────────────┐
│ Home Assistant                        │
│  control4_extra/  (forked from core)  │        HTTPS (local)       ┌──────────────┐
│   - config_flow.py  (+ platform pick) │◄───────────────────────────►│  Director    │
│   - __init__.py     (+ platform pick) │   pyControl4 2.0.2          │  (Control4   │
│   - entity.py, director_utils.py      │   (C4Account, C4Director)   │  controller) │
│   - cover.py / light.py / climate.py  │                             └──────────────┘
│     / media_player.py  (unmodified    │
│     upstream logic, renamed calls)    │
└──────────────────────────────────────┘
```

### Config flow (`config_flow.py`) — unmodified upstream auth

1. User enters Control4 account email/password + Director host/IP (same as upstream).
2. `C4Account` → account bearer token → `get_account_controllers()` → `controllerCommonName`
   → `get_director_bearer_token()`.
3. Entry created with `options={CONF_ENABLED_PLATFORMS: ["cover"]}` as the default.

### Platform selection — the actual addition

- `const.py`: `CONF_ENABLED_PLATFORMS`, `AVAILABLE_PLATFORMS` (value → label for the 4
  upstream platforms), `DEFAULT_ENABLED_PLATFORMS = ["cover"]`.
- `config_flow.py`'s `OptionsFlowHandler` (already existed upstream for `scan_interval`)
  gained a `cv.multi_select(AVAILABLE_PLATFORMS)` field. It's an `OptionsFlowWithReload`, so
  saving options already triggers an entry reload — no extra listener code needed.
- `__init__.py`: `PLATFORMS` is no longer a module-level constant; `_enabled_platforms(entry)`
  reads `entry.options[CONF_ENABLED_PLATFORMS]` and both `async_setup_entry` and
  `async_unload_entry` forward/unload only those.

### `cover.py` / `light.py` / `climate.py` / `media_player.py` — unmodified upstream logic

Ported as-is (device registry wiring, category/type discovery via
`get_items_of_category(hass, entry, category)`, per-platform `DataUpdateCoordinator`,
retry-on-`BadToken` in `director_utils.py`). Only change: the pyControl4 method renames above.
`cover.py` specifically: category `"blinds_shades"`, entity type `7`
(`CONTROL4_ENTITY_TYPE`), backed by `pyControl4.blind.C4Blind` (`open`/`close`/`stop`/
`set_level_target`), variables `Level`/`Fully Closed`/`Fully Open`/`Opening`/`Closing`.

### Dry-contact covers (`assumed_state`)

Dry-contact/relay blind drivers have no real position feedback, but Control4 still reports a
best-guess `Open`/`Fully Closed`/`Level` status. HA's cover card disables the open/close
buttons once that status says "already there" (`canOpen`/`canClose` in
`home-assistant/frontend`'s `src/data/cover.ts`) — wrong here, since the user needs to be able
to force a command through regardless of what the unreliable status claims.

Verified against the actual frontend source: `canOpen`/`canClose` return `true`
unconditionally (state permitting) when the entity reports `assumed_state=True` — the standard
HA mechanism for "status is informational, don't gate control on it".

Applied per-item, not integration-wide, since a household could plausibly mix dry-contact and
real-feedback blinds later:
- `const.py`: `CONF_DRY_CONTACT_COVERS` — list of item IDs (as strings).
- `config_flow.py`'s `OptionsFlowHandler` gained a second multi-select, populated from
  currently-known cover items (`get_items_of_category` against `CONTROL4_COVER_CATEGORY`),
  letting the user tick which specific covers are dry-contact.
- `cover.py`: `Control4Cover.__init__` takes `is_dry_contact` and sets `_attr_assumed_state`
  accordingly. Status (`is_closed`, `current_cover_position`, `is_opening`, `is_closing`) is
  computed exactly the same either way — only button availability changes.

## Reference: Control4 Blind Proxy protocol (background, not directly used)

`pyControl4.blind.C4Blind` wraps this protocol so our code never constructs these commands
directly, but it's useful background for why the variables/commands look the way they do
(confirmed from `docs/driverworks-proxyprotocol`: `32_blind_proxy_commands`,
`33_blind_protocol_notifications`, `34_blind_capabilities`, `36_blind_variables`):

- Command: `SET_LEVEL_TARGET` (`LEVEL_TARGET` int, `level_closed`..`level_open`).
- Variables: `Open`/`Fully Closed`/`Stopped`/`Fully Open`/`Level`/`Target Level`/`Opening`/
  `Closing`.
- `has_level`/`can_stop` capabilities gate whether a driver supports arbitrary position vs.
  just open/closed/stop.

The original spec draft flagged "no dedicated STOP command visible in the docs" as an open
risk. Resolved: `pyControl4.blind.C4Blind.stop()` sends a literal `"STOP"` command — it exists,
the proxy-protocol doc subset we had just didn't happen to include that page.

## Error handling

Unmodified from upstream: `ConfigEntryNotReady` on connection failure during setup,
`BadCredentials` → setup returns `False`, `BadToken` triggers a token refresh-and-retry once
in `director_utils.update_variables_for_config_entry`, `client_exceptions.ClientError` retried
up to `API_RETRY_TIMES` (5) during setup via `call_c4_api_retry`.

## Packaging

- `custom_components/control4_extra/` — `manifest.json` domain `control4_extra`, `requirements:
  []` (pyControl4 is vendored, see above), `ssdp` discovery kept (`c4:director`, same as
  upstream), `issue_tracker` set (required by HACS's integration checklist).
- `hacs.json` + `LICENSE` (Apache-2.0, matching upstream) at repo root for HACS
  custom-repository installation.
- Every forked file carries a two-line attribution comment pointing at the upstream source.

## Testing

- No physical Director/blind hardware available in this environment. Verification done so far:
  every file's syntax and real symbol resolution checked (`py_compile` + actual import against
  the real `homeassistant` 2026.2.3 and `pyControl4==2.0.2` packages in a scratch venv — zero
  errors). Behavior against a live Director/blind still needs the user's own hardware.
- Recommended follow-up once installed for real: confirm the options-flow platform toggle
  actually adds/removes entities on reload, and confirm `stop_cover` behaves as expected on the
  real 2-relay blind driver.

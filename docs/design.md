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
- Added a brand icon at `custom_components/control4_extra/brand/`. Originally a custom-drawn
  `icon.svg` (dark badge, "C4" monogram, teal "+"); replaced on request with Control4's actual
  icon/logo, pulled directly from `home-assistant/brands`' `core_integrations/control4/`
  (`icon.png`, `icon@2x.png`, `logo.png`, `logo@2x.png`) — the same images the official
  integration shows, since this integration represents the same real-world product. Originally
  placed at a repo-root `brands/` folder on the assumption that showing up in HA requires a PR
  to the separate `home-assistant/brands` repo — wrong for current HA: as of **2026.3.0**,
  custom integrations can ship local brand images directly inside their own
  `custom_components/<domain>/brand/` directory and HA reads them straight from there, no
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
- Otherwise behave like upstream's push version (PR #176238): same auth flow, device
  registry/naming, category/type-based discovery, token and `BadToken` handling - state by
  WebSocket push instead of polling, with a reconnect that actually works (see "WebSocket").
- Track the current `pyControl4` release (`2.0.2`), vendored in-tree rather than
  pip-installed, so it can't conflict with the official integration's own exact pin when
  both run in the same Home Assistant instance.
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

Upstream caught up in `home-assistant/core` #176050 (merged 2026-07-10, ships in HA 2026.8):
its manifest now pins `pyControl4==2.0.2` too, and its call sites match our rename map
line for line (re-diffed against `dev` on 2026-09-25 - the platform files differ only in
our additions listed below). 2.0.2 is still the latest pyControl4 release; the library has
had no commits since 2026-02-23.

Verified by downloading both wheels and diffing: 1.5.0 (what `home-assistant/core`'s manifest
pinned at fork time) uses camelCase methods (`getAccountBearerToken`, `getAllItemInfo`,
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
`pyControl4` install. `manifest.json` no longer requires `pyControl4` - nothing to conflict
with the official integration's own pin. The vendored copy still imports `xmltodict`
(`error_handling.py`), hence `"xmltodict>=0.13"`: a lower bound, never an exact pin, so
whatever HA already has (`requirements_all.txt` pins it for other integrations and the
official container installs that) satisfies it without a reinstall fight. It was missing
until 0.3.1 - an HA Core venv install failed at import; HA OS/container only worked by luck. Verified with the same import
test as above, but with `pyControl4` actively *uninstalled* from the scratch venv first, to
prove there's no remaining dependency on a global install.

Still vendored now that upstream pins the same 2.0.2: the conflict is structural, not
version-specific - the next time either side bumps, two exact pins fight again. Only the
modules we call are vendored (`account`, `blind`, `climate`, `director`, `error_handling`,
`light`, `room`, `websocket`); `alarm.py`, `fan.py`, `relay.py` are **not** in the copy.

### `via_device_id`, minimum Home Assistant 2026.8

`DeviceInfo(via_device=...)` is deprecated (runtime warning since HA 2026.8, removed in
2027.8 - developers.home-assistant.io blog, 2026-07-21: identifiers are only unique per
config entry). `entity.py` uses `via_device_id=dr.async_get_device_id_by_identifier(...)`
exactly like upstream #177494. That helper only exists from HA 2026.8, hence
`"homeassistant": "2026.8.0"` in `hacs.json`. The controller device it looks up is
registered in `async_setup_entry` before any platform is forwarded, so the lookup can't
race.

Deliberately *not* taken from upstream: `probatio` instead of `voluptuous` (HA 2026.9 keeps
`voluptuous` as a permanent alias for custom integrations) and PEP 758 `except X, Y:`
(Python 3.14-only syntax).

## Architecture (0.4.0+: local push)

```
┌───────────────────────────────────────┐   REST (setup, commands,   ┌──────────────┐
│ Home Assistant                         │   60 s resync)             │  Director    │
│  control4_extra/                       │◄──────────────────────────►│  (Control4   │
│   - __init__.py   (+ platform pick)    │   WebSocket push           │  controller) │
│   - director_websocket.py (reconnects) │◄───────────────────────────│              │
│   - cover/light/climate/media_player   │   vendored pyControl4 2.0.2└──────────────┘
└───────────────────────────────────────┘
```

Base: `home-assistant/core` PR [#176238](https://github.com/home-assistant/core/pull/176238)
(open, changes requested) taken through
[`deliriumxp/control4-push`](https://github.com/deliriumxp/control4-push) - the same PR as a
drop-in override of the built-in `control4`, plus `director_websocket.py`. Tests from both
come along (`tests/`); snapshots differ from the fork only in `platform: control4_extra`.

- Entities are plain `Entity` subclasses fed by push (`Control4Entity._update_callback`), not
  coordinators. Media players keep a 5 s coordinator: part of room state is never pushed.
- **Safety resync every 60 s** (`WEBSOCKET_RESYNC_INTERVAL_SEC`) re-reads every subscribed
  item over REST, in one bulk request. Kept because push demonstrably loses variables on some controllers (X4,
  `lawtancool/hass-control4` #50) and nothing else would correct the drift. Remove only if
  hardware shows push loses nothing.
- The director token is refreshed `SCHEDULE_REFRESH_ADVANCE_SEC` before `validSeconds` runs
  out and the socket reconnects with it (without that the Director stops sending, per
  pyControl4's own `sio_connect` docstring).
- No polling-interval option any more; a stored `scan_interval` is ignored.
- Upstream switched to `_attr_has_entity_name = True`: friendly names become "<device>
  <entity>". Entity IDs already in the registry don't change.

### Config flow — upstream auth, then a platforms step

1. User enters Control4 account email/password + Director host/IP (same as upstream).
2. `C4Account` → account bearer token → `get_account_controllers()` → `controllerCommonName`
   → `get_director_bearer_token()`, then a test call to the Director.
3. "platforms" step: which entity types to import; stored as
   `options={CONF_ENABLED_PLATFORMS: [...]}` (default `["cover"]`).

### Platform selection — the actual addition

- `const.py`: `CONF_ENABLED_PLATFORMS`, `AVAILABLE_PLATFORMS` (value → label for the 4
  upstream platforms), `DEFAULT_ENABLED_PLATFORMS = ["cover"]`.
- `config_flow.py`: `OptionsFlowHandler` (upstream push has none) with a
  `cv.multi_select(AVAILABLE_PLATFORMS)` field. It's an `OptionsFlowWithReload`, so saving
  options triggers an entry reload.
- `__init__.py`: `PLATFORMS` lists everything the integration can provide;
  `_enabled_platforms(entry)` is the subset enabled in the options. Setup stores what it
  forwarded in `runtime_data.platforms` and unload uses exactly that list: the options flow
  saves the new options *before* its reload unloads, so unloading "the enabled ones" would
  try to unload a just-enabled platform that was never loaded ("Config entry was never
  loaded!" - found on hardware in 0.3.1, the entry stayed broken until restart).

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

From upstream push: `ConfigEntryNotReady` on connection failures during setup,
`BadToken` on a REST call triggers one refresh-and-retry, the WebSocket disconnect marks
entities unavailable until the reconnect resync brings them back. Fixed on top (review of
the fork, 0.4.1 / control4-push 0.2.0, each with a test in `test_robustness.py`):

- The scheduled token refresh reschedules on *any* error and hands auth failures to a
  reauth flow (`async_step_reauth`: new password, same entry). Upstream only retried on
  `ConfigEntryNotReady`, so a `C4Exception` ended the chain and push died at token expiry.
- **One bulk request, never a request per item.** Upstream fetched
  `/api/v1/items/<id>/variables` per item, concurrently at startup (one TLS connection
  each) and one by one in the resync. On hardware after an HA restart all ~80 initial
  requests timed out at 10 s and, since upstream skips items without initial variables,
  every light vanished until the next restart. Measured on a 4.2.1 controller: 80 parallel
  new TLS connections to the broker take 6x as long as the same 80 requests over one.
  Now setup (`fetch_initial_variables`) and the resync each make one
  `/api/v1/items/variables?varnames=` call with the platforms' variable names - what the
  official polling version always did; a Director that doesn't answer makes the platform
  `PlatformNotReady`, which HA retries with backoff. A state write that fails for one item
  doesn't end the resync for the rest.
- Options flow: saving merges into the stored options (the dry-contact field is absent
  when the cover list can't be fetched - replacing wiped the marks); any Director error
  just hides that field; ids of covers gone from the project are dropped from the default
  (`multi_select` rejects a default it doesn't list, which blocked saving).

**Diagnostics** (`diagnostics.py`): Download diagnostics gives every light/cover item with
its raw Director variables, credentials redacted - the only way to see from here what a
live Director reports.

## Packaging

- `custom_components/control4_extra/` — `manifest.json` domain `control4_extra`,
  `iot_class: local_push`, `requirements: ["xmltodict>=0.13", "python-socketio-v4>=4.6.1"]`
  (what the vendored pyControl4 imports; lower bounds only, see above), `ssdp` discovery
  kept (`c4:director`), `issue_tracker` set (required by HACS's integration checklist).
- `hacs.json` + `LICENSE` (Apache-2.0, matching upstream) at repo root for HACS
  custom-repository installation.
- Every forked file carries an attribution comment pointing at its upstream source.

## WebSocket: why `director_websocket.py`

pyControl4's `C4Websocket` as released can't be used as-is; all findings below are
reproduced in `tests/test_director_websocket.py` against a fake Director.

1. **SSL in `C4Websocket` (pyControl4 [#53](https://github.com/lawtancool/pyControl4/issues/53)
   / [#62](https://github.com/lawtancool/pyControl4/issues/62)) - reproduced and root-caused
   2026-09-25, fix proven; applies to 2.0.2 as released, #62 still open with no maintainer
   reply.** Reproduced against a fake Director (TLS with a self-signed cert, Engine.IO v3 /
   Socket.IO v2 on `/socket.io/`, subscription via `GET /api/v1/items/datatoui`, the server
   drops the socket once) with HA's detector emulated by wrapping
   `SSLContext.load_default_certs` / `set_default_verify_paths`. The transport is the
   `python-socketio-v4` / `python-engineio-v3` forks; the code in question is
   `engineio_v3/asyncio_client.py`. Two different failures, depending on the session:
   - **No session passed** (`C4Websocket(ip)`): `ssl_verify=False` makes engineio call
     `ssl.create_default_context()` inside `_connect_websocket` (line 299) on **every** connect
     *and every automatic reconnect attempt* - exactly the #62 traceback. Reconnect itself works.
   - **HA's no-verify session passed** (what 2.0.2's #54 fix, `hass-control4` 1.7.0 and core
     PR #176238 do): the first connect is clean - no blocking calls, events arrive. But
     after **any** drop, reconnect never succeeds: engineio's `_reset()` closes its session
     wrapper, and the next attempt creates a bare `aiohttp.ClientSession()` (verifying
     connector, `ssl_verify=True`) → `ClientConnectorCertificateError: self-signed
     certificate` on the Director's cert, retried forever and swallowed. Push stays dead until the
     next `sio_connect()` - the daily token refresh. In #176238 entities go `unavailable` on the
     drop and come back only through its 60 s resync poll, so it silently degrades to 60 s
     polling for up to a day.
   - **Fix (proven on the same rig: no blocking calls, reconnect succeeds, events flow
     again):** subclass engineio's `AsyncClient` to (re)bind its session to the caller's
     connector (`ClientSession(connector=..., connector_owner=False)`) whenever it is
     missing or closed - in `_connect_websocket` and `_send_request` - and to drop the
     reference in `_reset()`; subclass the socketio `AsyncClient` so that
     `_engineio_v3_client_class()` returns it (`functools.partial` with the connector) and
     `ssl_verify=True` (the connector's no-verify context applies). Require the session - no
     library-owned fallback. Implemented in `director_websocket.py` (see above).
2. **Disconnect leaves the reconnect loop running.** `socketio_v4`'s `disconnect()` doesn't stop
   a pending automatic reconnect, and the loop swallows `CancelledError` while it sleeps
   between attempts - cancelling alone doesn't stop it. After an unload or token refresh
   during a Director outage the old loop keeps retrying with the old token and, once the
   Director is back, opens a second socket (duplicate events). `DirectorWebsocket`'s client
   sets the loop's abort event, waits for it to exit and cancels only if it's stuck in a
   connect attempt.

## Cloud dependency at startup; local token (investigated 2026-09-25)

Every setup and every token refresh goes to the Control4 cloud
(`apis.control4.com/authentication/v1/rest/authorization`) for the director JWT; without it
`/api/v1/items…` answers `401 Token required`. pyControl4 puts no timeout on these calls.
Seen on hardware (EA-1 object, fork 0.2.1): the object's link to that endpoint hung ~4 min
and ended in `Server disconnected` while the cloud answered in 0.6 s from elsewhere and the
Director was healthy - the integration stayed down until the link recovered by itself.

Not done yet, both options open:
- a timeout (~30 s) on the cloud calls, so a hang becomes a quick `ConfigEntryNotReady` retry;
- **local token.** The broker lists `/api/v1/localjwt` (`GET /api/v1/routes`, pyControl4
  #58). Checked read-only on a CORE1 at OS 4.2.1: its built-in page
  `/api/v1/localjwt/html` posts `{"user", "password"}` to `/api/v1/localjwt` and expects
  `{"token"}`; an unknown user gets `401 "User not allowed."`, an empty body a 500.
  Unknown: which local user is allowed, and whether the Director accepts that token for
  items, variables and the WebSocket. Needs the controller's local credentials to test.
  (`/api/v1/jwt` on the same broker is the cloud login - email, app key, env - not local.)

## Testing

- `tests/` runs on `pytest-homeassistant-custom-component` against the minimum supported HA
  (Python 3.14): `uv venv -p 3.14 && uv pip install "homeassistant==2026.8.*"
  pytest-homeassistant-custom-component xmltodict python-socketio-v4 && pytest`. Upstream's
  push tests (Director mocked) plus `test_extra.py` (platform toggle, dry contact, device
  link) and `test_director_websocket.py` (real sockets against a fake TLS Director). Nothing
  here proves behavior against real hardware.
- The platform-toggle test loads the `light` domain first on purpose: on a real instance other
  integrations (KNX) have it loaded, and only then does HA actually try to unload a platform
  that was never set up - found on hardware as "Config entry was never loaded!", invisible
  in a bare test instance.
- Needs hardware (checklist in `deliriumxp/control4-push`'s README): state lands within ~1 s,
  no blocking-call warnings, push resumes by itself after a Director reboot, one event per
  change after a reload during an outage, still pushing after the ~24 h token refresh;
  `stop_cover` on the real 2-relay blind driver.

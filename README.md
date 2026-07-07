# Control4 Extra

A [HACS](https://hacs.xyz/) custom integration for Home Assistant that talks to a Control4
Director, forked from Home Assistant core's official
[`control4`](https://www.home-assistant.io/integrations/control4/) integration.

## Why this exists instead of the official integration

The official `control4` integration is great, but it always imports all four of its platforms
(`cover`, `light`, `climate`, `media_player`) with no way to opt out. If you already handle
lights and climate through something else (KNX, in this case) and only want Control4 for,
say, blinds, you end up with duplicate entities you don't want.

This fork keeps 100% of the upstream logic (auth, device registry, Director category/type
discovery, retry/reauth handling — see [`docs/design.md`](docs/design.md) for exactly what
changed and why) and adds:

- **A platform picker.** Settings → Devices & services → Control4 Extra → Configure → choose
  which of the four platforms are actually enabled. Default: `cover` only.
- **A per-cover "dry contact" flag.** For blinds driven by a relay with no real position
  feedback, Control4's reported status can't be trusted to gate the open/close buttons in the
  UI — mark those specific covers in the same options screen and their buttons stay active
  regardless of what the status claims.

It also tracks the current `pyControl4` release (`2.0.2`) rather than the older `1.5.0`
upstream still pins.

## Installation (HACS)

1. HACS → the three-dot menu → **Custom repositories**.
2. Add this repository URL, category **Integration**.
3. Install **Control4 Extra**, restart Home Assistant.
4. Settings → Devices & services → **Add Integration** → search for **Control4 Extra**.
5. Enter your Control4 account email/password and your Director's local IP/hostname.
6. Open the integration's **Configure** dialog to pick which entity types to import, and to
   mark any dry-contact covers.

## Brand icon

Ships Control4's own icon/logo (sourced from `home-assistant/brands`' `core_integrations/control4/`,
the same images the official integration uses) at `custom_components/control4_extra/brand/`.
Home Assistant 2026.3+ reads local brand images directly from the integration directory, no
`home-assistant/brands` PR needed. On older HA versions you'll see a generic fallback icon
instead.

## License

Apache License 2.0 — see [`LICENSE`](LICENSE), same as the Home Assistant core project this
is forked from. Every file adapted from upstream carries a comment pointing at its source.

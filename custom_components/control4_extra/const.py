# Adapted from home-assistant/core homeassistant/components/control4 (Apache-2.0).
# See https://github.com/home-assistant/core/tree/dev/homeassistant/components/control4
#
# Differences from upstream: renamed domain (runs alongside, not instead of, the
# core `control4` integration namespace); added CONF_ENABLED_PLATFORMS so a
# household can opt out of domains it already handles elsewhere (e.g. lights/
# climate via KNX) instead of always importing all four platforms; added
# CONF_DRY_CONTACT_COVERS so individual dry-contact (no position feedback)
# blinds can be marked as such, instead of that behavior applying to every
# cover regardless of hardware.
"""Constants for the Control4 Extra integration."""

from homeassistant.const import Platform

DOMAIN = "control4_extra"

DEFAULT_SCAN_INTERVAL = 5
MIN_SCAN_INTERVAL = 1

API_RETRY_TIMES = 5

CONF_CONTROLLER_UNIQUE_ID = "controller_unique_id"

CONTROL4_ENTITY_TYPE = 7
CONTROL4_COVER_CATEGORY = "blinds_shades"

CONF_ENABLED_PLATFORMS = "enabled_platforms"

# Item IDs (as strings, for JSON/options-flow storage) of covers that are
# driven by a dry contact / relay with no real position feedback. For these,
# Control4's reported status is shown but must never gate the open/close
# buttons - see Control4Cover.assumed_state in cover.py.
CONF_DRY_CONTACT_COVERS = "dry_contact_covers"

# value -> display label, in the order shown in the options flow.
AVAILABLE_PLATFORMS = {
    Platform.COVER.value: "Covers (blinds/shades)",
    Platform.LIGHT.value: "Lights",
    Platform.CLIMATE.value: "Climate",
    Platform.MEDIA_PLAYER.value: "Media players",
}

DEFAULT_ENABLED_PLATFORMS = [Platform.COVER.value]

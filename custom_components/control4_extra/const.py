# Adapted from home-assistant/core PR #176238 (Control4 local push, Apache-2.0) via
# github.com/deliriumxp/control4-push, which adds the reconnect-safe DirectorWebsocket.
#
# Differences from upstream: renamed domain (runs alongside, not instead of, the
# core `control4` integration namespace); added CONF_ENABLED_PLATFORMS so a
# household can opt out of domains it already handles elsewhere (e.g. lights/
# climate via KNX) instead of always importing all four platforms; added
# CONF_DRY_CONTACT_COVERS so individual dry-contact (no position feedback)
# blinds can be marked as such, instead of that behavior applying to every
# cover regardless of hardware; runtime data remembers the platforms it loaded.
"""Constants for the Control4 Extra integration."""

import asyncio
from dataclasses import dataclass, field
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import CALLBACK_TYPE

from .director_websocket import DirectorWebsocket
from .vendor.pycontrol4.account import C4Account
from .vendor.pycontrol4.director import C4Director

DOMAIN = "control4_extra"


@dataclass
class Control4RuntimeData:
    """Runtime data for a Control4 config entry; fields past account/director/websocket are set once during async_setup_entry."""

    account: C4Account
    director: C4Director
    websocket: DirectorWebsocket
    controller_unique_id: str = ""
    director_sw_version: str = ""
    director_model: str = ""
    director_all_items: list[dict[str, Any]] = field(default_factory=list)
    ui_configuration: dict[str, Any] | None = None
    cancel_token_refresh_callback: CALLBACK_TYPE | None = None
    cancel_periodic_resync_callback: CALLBACK_TYPE | None = None
    token_refresh_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    resync_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    # What async_setup_entry actually forwarded. Unload must use this, not the
    # options: the options flow saves new options *before* its reload unloads, so
    # a just-enabled platform would be "unloaded" without ever having been loaded.
    platforms: list[Platform] = field(default_factory=list)


type Control4ConfigEntry = ConfigEntry[Control4RuntimeData]

CONF_CONTROLLER_UNIQUE_ID = "controller_unique_id"

CONTROL4_ENTITY_TYPE = 7
CONTROL4_COVER_CATEGORY = "blinds_shades"

RETRY_BACKOFF_MAX_SEC = 30
SCHEDULE_REFRESH_ADVANCE_SEC = 300

DEFAULT_SCAN_INTERVAL = 5
WEBSOCKET_RESYNC_INTERVAL_SEC = 60
RESYNC_CONCURRENCY = 4

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

# Adapted from home-assistant/core homeassistant/components/control4 (Apache-2.0).
# See https://github.com/home-assistant/core/tree/dev/homeassistant/components/control4
"""Platform for Control4 Covers (blinds and shades)."""

from datetime import timedelta
import logging
from typing import Any, override

from .vendor.pycontrol4.blind import C4Blind
from .vendor.pycontrol4.error_handling import C4Exception

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import Control4ConfigEntry, get_items_of_category
from .const import CONF_DRY_CONTACT_COVERS, CONTROL4_COVER_CATEGORY, CONTROL4_ENTITY_TYPE
from .director_utils import update_variables_for_config_entry
from .entity import Control4Entity

_LOGGER = logging.getLogger(__name__)

CONTROL4_CATEGORY = CONTROL4_COVER_CATEGORY

CONTROL4_LEVEL = "Level"
CONTROL4_FULLY_CLOSED = "Fully Closed"
CONTROL4_FULLY_OPEN = "Fully Open"
CONTROL4_OPENING = "Opening"
CONTROL4_CLOSING = "Closing"

VARIABLES_OF_INTEREST = {
    CONTROL4_LEVEL,
    CONTROL4_FULLY_CLOSED,
    CONTROL4_FULLY_OPEN,
    CONTROL4_OPENING,
    CONTROL4_CLOSING,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Control4ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Control4 covers from a config entry."""
    runtime_data = entry.runtime_data
    dry_contact_ids = set(entry.options.get(CONF_DRY_CONTACT_COVERS, []))

    async def async_update_data() -> dict[int, dict[str, Any]]:
        """Fetch data from Control4 director for blinds."""
        try:
            return await update_variables_for_config_entry(
                hass, entry, VARIABLES_OF_INTEREST
            )
        except C4Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    coordinator = DataUpdateCoordinator[dict[int, dict[str, Any]]](
        hass,
        _LOGGER,
        name="cover",
        update_method=async_update_data,
        update_interval=timedelta(seconds=runtime_data.scan_interval),
        config_entry=entry,
    )

    await coordinator.async_refresh()

    items_of_category = await get_items_of_category(hass, entry, CONTROL4_CATEGORY)
    entity_list = []
    for item in items_of_category:
        try:
            if item["type"] != CONTROL4_ENTITY_TYPE:
                continue
            item_name = item["name"]
            item_id = item["id"]
            item_parent_id = item["parentId"]
            item_manufacturer = None
            item_device_name = None
            item_model = None

            for parent_item in items_of_category:
                if parent_item["id"] == item_parent_id:
                    item_manufacturer = parent_item.get("manufacturer")
                    item_device_name = parent_item.get("roomName")
                    item_model = parent_item.get("model")
        except KeyError:
            _LOGGER.exception(
                "Unknown device properties received from Control4: %s",
                item,
            )
            continue

        if item_id not in coordinator.data:
            _LOGGER.warning(
                "Couldn't get cover state data for %s (ID: %s), skipping setup",
                item_name,
                item_id,
            )
            continue

        entity_list.append(
            Control4Cover(
                runtime_data,
                coordinator,
                item_name,
                item_id,
                item_device_name,
                item_manufacturer,
                item_model,
                item_parent_id,
                is_dry_contact=str(item_id) in dry_contact_ids,
            )
        )

    async_add_entities(entity_list)


class Control4Cover(Control4Entity, CoverEntity):
    """Control4 cover entity."""

    _attr_has_entity_name = True
    _attr_translation_key = "blind"
    _attr_device_class = CoverDeviceClass.SHADE
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )

    def __init__(
        self,
        runtime_data,
        coordinator,
        name,
        idx,
        device_name,
        device_manufacturer,
        device_model,
        device_id,
        is_dry_contact: bool = False,
    ) -> None:
        """Initialize Control4 cover entity.

        `is_dry_contact` marks covers driven by a relay/dry-contact driver
        with no real position feedback (set via the options flow, per item).
        For these, `assumed_state` is reported so the HA frontend always
        keeps the open/close buttons enabled - see `data/cover.ts`'s
        `canOpen`/`canClose` in home-assistant/frontend, which otherwise
        disable them once the (unreliable) reported status says "fully
        open"/"fully closed". Status (`is_closed`, `current_cover_position`,
        ...) is still reported normally either way, only button
        availability is affected.
        """
        super().__init__(
            runtime_data,
            coordinator,
            name,
            idx,
            device_name,
            device_manufacturer,
            device_model,
            device_id,
        )
        self._attr_assumed_state = is_dry_contact

    @property
    @override
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self._cover_data is not None

    def _create_api_object(self) -> C4Blind:
        """Create a pyControl4 device object.

        This exists so the director token used is always the latest one,
        without needing to re-init the entire entity.
        """
        return C4Blind(self.runtime_data.director, self._idx)

    @property
    def _cover_data(self) -> dict[str, Any] | None:
        """Return the cover data from the coordinator."""
        return self.coordinator.data.get(self._idx)

    @property
    @override
    def current_cover_position(self) -> int | None:
        """Return current position of cover (0 closed, 100 open)."""
        data = self._cover_data
        if data is None:
            return None
        level = data.get(CONTROL4_LEVEL)
        if level is None:
            return None
        return int(level)

    @property
    @override
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        data = self._cover_data
        if data is None:
            return None
        if (fully_closed := data.get(CONTROL4_FULLY_CLOSED)) is not None:
            return bool(fully_closed)
        position = self.current_cover_position
        if position is None:
            return None
        return position == 0

    @property
    @override
    def is_opening(self) -> bool | None:
        """Return if the cover is opening."""
        data = self._cover_data
        if data is None:
            return None
        opening = data.get(CONTROL4_OPENING)
        if opening is None:
            return None
        return bool(opening)

    @property
    @override
    def is_closing(self) -> bool | None:
        """Return if the cover is closing."""
        data = self._cover_data
        if data is None:
            return None
        closing = data.get(CONTROL4_CLOSING)
        if closing is None:
            return None
        return bool(closing)

    @override
    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        c4_blind = self._create_api_object()
        await c4_blind.open()
        await self.coordinator.async_request_refresh()

    @override
    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        c4_blind = self._create_api_object()
        await c4_blind.close()
        await self.coordinator.async_request_refresh()

    @override
    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        c4_blind = self._create_api_object()
        await c4_blind.stop()
        await self.coordinator.async_request_refresh()

    @override
    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        c4_blind = self._create_api_object()
        await c4_blind.set_level_target(kwargs[ATTR_POSITION])
        await self.coordinator.async_request_refresh()

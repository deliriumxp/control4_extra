"""Импорт всех модулей и via_device_id против настоящего реестра устройств HA."""

import importlib
from types import SimpleNamespace

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

MODULES = ["__init__", "config_flow", "const", "cover", "light", "climate", "media_player", "entity", "director_utils"]


def test_все_модули_импортируются():
    for name in MODULES:
        suffix = "" if name == "__init__" else "." + name
        importlib.import_module("custom_components.control4_extra" + suffix)


@pytest.mark.asyncio
async def test_via_device_id_указывает_на_контроллер(hass):
    from custom_components.control4_extra.const import DOMAIN
    from custom_components.control4_extra.entity import Control4Entity

    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    controller = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, "control4_ea5_000fff")}
    )
    coordinator = DataUpdateCoordinator(hass, None, name="t", config_entry=entry)
    runtime = SimpleNamespace(controller_unique_id="control4_ea5_000fff")
    entity = Control4Entity(runtime, coordinator, "Штора", 42, "Штора", "C4", "blind", 41)
    entity.hass = hass

    info = entity.device_info
    assert info["via_device_id"] == controller.id
    assert "via_device" not in info

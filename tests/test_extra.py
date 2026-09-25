"""Что добавляет Control4 Extra поверх push-интеграции: выбор платформ, «сухой контакт», связка устройств."""

import importlib
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.control4_extra.const import (
    CONF_DRY_CONTACT_COVERS,
    CONF_ENABLED_PLATFORMS,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ASSUMED_STATE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from . import setup_integration

COVER_ID = 234
COVER_ENTITY = "cover.test_controller_living_room_shade"
MODULES = ["", ".config_flow", ".const", ".cover", ".light", ".climate", ".media_player",
           ".entity", ".director_utils", ".director_websocket"]


@pytest.fixture
def platforms() -> list[Platform]:
    return [Platform.CLIMATE, Platform.COVER, Platform.LIGHT, Platform.MEDIA_PLAYER]


@pytest.fixture
def cover_variables(mock_c4_director: MagicMock) -> None:
    async def get_item_variables(item_id: int) -> list[dict[str, Any]]:
        if item_id != COVER_ID:
            return []
        values = {"Level": 50, "Fully Closed": False, "Opening": False, "Closing": False}
        return [{"varName": name, "value": value} for name, value in values.items()]

    mock_c4_director.get_item_variables = AsyncMock(side_effect=get_item_variables)


def test_все_модули_импортируются() -> None:
    for suffix in MODULES:
        importlib.import_module("custom_components.control4_extra" + suffix)


async def _set_options(hass: HomeAssistant, entry: MockConfigEntry, options: dict) -> None:
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(flow["flow_id"], options)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_c4_account", "mock_c4_director")
@pytest.mark.parametrize(
    ("before", "after"),
    [(["cover"], ["cover", "light"]), (["cover", "light"], ["cover"])],
    ids=["включение_света", "выключение_света"],
)
async def test_смена_платформ_перезагружает_запись(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, caplog, before, after
) -> None:
    """Воспроизведение с объекта: включили свет — «Config entry was never loaded!»."""
    # На объекте домен light уже загружен другими интеграциями (KNX); без этого HA
    # выгрузку незагруженной платформы молча пропускает и дефект не виден.
    assert await async_setup_component(hass, "light", {})
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_ENABLED_PLATFORMS: before}
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await _set_options(hass, mock_config_entry, {CONF_ENABLED_PLATFORMS: after})

    assert "Error unloading entry" not in caplog.text
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data.platforms == [
        platform for platform in [Platform.COVER, Platform.LIGHT] if platform.value in after
    ]


@pytest.mark.usefixtures("mock_c4_account", "cover_variables")
@pytest.mark.parametrize(("dry_contact", "assumed"), [(True, True), (False, None)])
async def test_сухой_контакт_оставляет_кнопки_шторы(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, dry_contact, assumed
) -> None:
    """Штора с «сухим контактом» отдаёт assumed_state: фронт не гасит открыть/закрыть по статусу."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={
            CONF_ENABLED_PLATFORMS: ["cover"],
            CONF_DRY_CONTACT_COVERS: [str(COVER_ID)] if dry_contact else [],
        },
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(COVER_ENTITY)
    assert state is not None
    assert state.attributes.get(ATTR_ASSUMED_STATE) is assumed


@pytest.mark.usefixtures("mock_c4_account", "cover_variables")
async def test_устройство_привязано_к_контроллеру(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """via_device_id: устройство шторы висит под контроллером той же записи."""
    await setup_integration(hass, mock_config_entry)

    entity = er.async_get(hass).async_get(COVER_ENTITY)
    devices = dr.async_get(hass)
    device = devices.async_get(entity.device_id)
    controller = devices.async_get_device(
        identifiers={(DOMAIN, mock_config_entry.data["controller_unique_id"])}
    )
    assert device.via_device_id == controller.id

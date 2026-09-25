"""Enabling/disabling platforms in the options flow reloads the entry cleanly."""

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.control4_extra.const import CONF_ENABLED_PLATFORMS
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_SCAN_INTERVAL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


async def _set_platforms(hass: HomeAssistant, entry: MockConfigEntry, platforms: list[str]) -> None:
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(
        flow["flow_id"],
        {CONF_ENABLED_PLATFORMS: platforms, CONF_SCAN_INTERVAL: 5},
    )
    await hass.async_block_till_done()


@pytest.mark.usefixtures("director")
@pytest.mark.parametrize(
    ("before", "after"),
    [(["cover"], ["cover", "light"]), (["cover", "light"], ["cover"])],
    ids=["включение_света", "выключение_света"],
)
async def test_смена_платформ_перезагружает_запись(
    hass: HomeAssistant, config_entry: MockConfigEntry, caplog, before, after
) -> None:
    """Воспроизведение с объекта: включили свет — «Config entry was never loaded!»."""
    # На объекте домен light уже загружен другими интеграциями (KNX); без этого HA
    # выгрузку незагруженной платформы молча пропускает и дефект не виден.
    assert await async_setup_component(hass, "light", {})
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry, options={CONF_ENABLED_PLATFORMS: before}
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    await _set_platforms(hass, config_entry, after)

    assert "Error unloading entry" not in caplog.text
    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.runtime_data.platforms == [Platform(p) for p in after]

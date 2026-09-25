"""Fixtures: a loadable Control4 Extra entry against a mocked Director."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.control4_extra.const import (
    CONF_CONTROLLER_UNIQUE_ID,
    CONF_ENABLED_PLATFORMS,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

CONTROLLER_UNIQUE_ID = "control4_core1_000FFF9E4A5B"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Load custom_components/control4_extra."""


@pytest.fixture
def config_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title=CONTROLLER_UNIQUE_ID,
        data={
            CONF_HOST: "192.0.2.10",
            CONF_USERNAME: "user",
            CONF_PASSWORD: "pass",
            CONF_CONTROLLER_UNIQUE_ID: CONTROLLER_UNIQUE_ID,
        },
        options={CONF_ENABLED_PLATFORMS: ["cover"]},
    )


@pytest.fixture
def director() -> Generator[None]:
    """C4Account/C4Director that answer like an empty project."""
    with (
        patch("custom_components.control4_extra.C4Account", autospec=True) as account,
        patch("custom_components.control4_extra.C4Director", autospec=True) as director,
    ):
        account.return_value.get_director_bearer_token = AsyncMock(
            return_value={"token": "t", "validSeconds": 86400}
        )
        account.return_value.get_account_controllers = AsyncMock(
            return_value={"href": "https://example/controller"}
        )
        account.return_value.get_controller_os_version = AsyncMock(return_value="3.4.0")
        director.return_value.get_all_item_info = AsyncMock(return_value=[])
        director.return_value.get_ui_configuration = AsyncMock(return_value={})
        director.return_value.get_all_items_by_category = AsyncMock(return_value=[])
        director.return_value.get_all_item_variable_value = AsyncMock(return_value=[])
        yield

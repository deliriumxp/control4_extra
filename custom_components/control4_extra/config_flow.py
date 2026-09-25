# Adapted from home-assistant/core PR #176238 (Control4 local push, Apache-2.0) via
# github.com/deliriumxp/control4-push.
#
# Differences from upstream:
#  - The user flow gains a "platforms" step right after auth succeeds, so the
#    household picks which entity types to import during setup.
#  - An options flow (upstream push has none) re-picks the platforms and marks
#    individual dry-contact covers. No polling interval: state comes by push.
"""Config flow for Control4 Extra integration."""

import logging
from typing import Any, override

from aiohttp.client_exceptions import ClientError
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.device_registry import format_mac

from . import get_items_of_category
from .const import (
    AVAILABLE_PLATFORMS,
    CONF_CONTROLLER_UNIQUE_ID,
    CONF_DRY_CONTACT_COVERS,
    CONF_ENABLED_PLATFORMS,
    CONTROL4_COVER_CATEGORY,
    CONTROL4_ENTITY_TYPE,
    DEFAULT_ENABLED_PLATFORMS,
    DOMAIN,
    Control4ConfigEntry,
)
from .vendor.pycontrol4.account import C4Account
from .vendor.pycontrol4.director import C4Director
from .vendor.pycontrol4.error_handling import BadCredentials, NotFound, Unauthorized

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class Control4ExtraConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Control4 Extra."""

    VERSION = 1

    _connect_data: dict[str, Any]

    async def _async_try_connect(
        self, user_input: dict[str, Any]
    ) -> tuple[dict[str, str], dict[str, Any] | None, dict[str, str]]:
        """Try to connect to Control4 and return errors, data, and placeholders."""
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}
        data: dict[str, Any] | None = None

        host = user_input[CONF_HOST]
        username = user_input[CONF_USERNAME]
        password = user_input[CONF_PASSWORD]

        # Step 1: Authenticate with Control4 cloud API
        account_session = aiohttp_client.async_get_clientsession(self.hass)
        account = C4Account(username, password, account_session)
        try:
            await account.get_account_bearer_token()

            account_controllers = await account.get_account_controllers()
            controller_unique_id = account_controllers["controllerCommonName"]

            director_bearer_token = (
                await account.get_director_bearer_token(controller_unique_id)
            )["token"]
        except BadCredentials, Unauthorized:
            errors["base"] = "invalid_auth"
            return errors, data, description_placeholders
        except NotFound:
            errors["base"] = "controller_not_found"
            return errors, data, description_placeholders
        except Exception:
            _LOGGER.exception(
                "Unexpected exception during Control4 account authentication"
            )
            errors["base"] = "unknown"
            return errors, data, description_placeholders

        # Step 2: Connect to local Control4 Director
        director_session = aiohttp_client.async_get_clientsession(
            self.hass, verify_ssl=False
        )
        director = C4Director(host, director_bearer_token, director_session)
        try:
            await director.get_all_item_info()
        except Unauthorized:
            errors["base"] = "director_auth_failed"
            return errors, data, description_placeholders
        except ClientError, TimeoutError:
            errors["base"] = "cannot_connect"
            description_placeholders["host"] = host
            return errors, data, description_placeholders
        except Exception:
            _LOGGER.exception(
                "Unexpected exception during Control4 director connection"
            )
            errors["base"] = "unknown"
            return errors, data, description_placeholders

        # Success - return the data needed for entry creation
        data = {
            CONF_HOST: host,
            CONF_USERNAME: username,
            CONF_PASSWORD: password,
            CONF_CONTROLLER_UNIQUE_ID: controller_unique_id,
        }

        return errors, data, description_placeholders

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}

        if user_input is not None:
            errors, data, description_placeholders = await self._async_try_connect(
                user_input
            )

            if not errors and data is not None:
                controller_unique_id = data[CONF_CONTROLLER_UNIQUE_ID]
                mac = (controller_unique_id.split("_", 3))[2]
                formatted_mac = format_mac(mac)
                await self.async_set_unique_id(formatted_mac)
                self._abort_if_unique_id_configured()
                self._connect_data = data
                return await self.async_step_platforms()

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
            description_placeholders=description_placeholders,
        )

    async def async_step_platforms(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick which entity types to import, before creating the entry."""
        if user_input is not None:
            data = self._connect_data
            return self.async_create_entry(
                title=data[CONF_CONTROLLER_UNIQUE_ID],
                data=data,
                options={CONF_ENABLED_PLATFORMS: user_input[CONF_ENABLED_PLATFORMS]},
            )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_ENABLED_PLATFORMS, default=DEFAULT_ENABLED_PLATFORMS
                ): cv.multi_select(AVAILABLE_PLATFORMS),
            }
        )
        return self.async_show_form(step_id="platforms", data_schema=schema)

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: Control4ConfigEntry,
    ) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler()


class OptionsFlowHandler(OptionsFlowWithReload):
    """Handle an options flow for Control4 Extra."""

    async def _async_get_known_covers(self) -> dict[str, str]:
        """Return {item_id: name} for currently known Control4 cover items.

        Used to let the user mark specific covers as dry-contact (no position
        feedback) rather than applying that to every cover. Empty if the
        entry isn't currently loaded (runtime_data unset) - the option is
        still editable, just with nothing to pick yet.
        """
        try:
            items = await get_items_of_category(
                self.hass, self.config_entry, CONTROL4_COVER_CATEGORY
            )
        except AttributeError:
            return {}
        return {
            str(item["id"]): item["name"]
            for item in items
            if item.get("type") == CONTROL4_ENTITY_TYPE
        }

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        known_covers = await self._async_get_known_covers()

        schema: dict[Any, Any] = {
            vol.Required(
                CONF_ENABLED_PLATFORMS,
                default=self.config_entry.options.get(
                    CONF_ENABLED_PLATFORMS, DEFAULT_ENABLED_PLATFORMS
                ),
            ): cv.multi_select(AVAILABLE_PLATFORMS),
        }
        if known_covers:
            schema[
                vol.Optional(
                    CONF_DRY_CONTACT_COVERS,
                    default=self.config_entry.options.get(CONF_DRY_CONTACT_COVERS, []),
                )
            ] = cv.multi_select(known_covers)

        return self.async_show_form(step_id="init", data_schema=vol.Schema(schema))

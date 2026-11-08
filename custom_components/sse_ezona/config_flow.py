"""Config flow for the SSE eZóna integration."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import (
    SseEzonaApi,
    SseEzonaAuthError,
    SseEzonaError,
    SseEzonaUnsupportedLoginError,
)
from .const import (
    CONF_DELIVERY_POINTS,
    CONF_ENERGY_AID,
    CONF_ENERGY_AID_AMOUNT,
    DOMAIN,
    ENERGY_AID_AUTO,
    ENERGY_AID_MODES,
)
from .coordinator import electricity_points, point_label

_LOGGER = logging.getLogger(__name__)

USERNAME_SELECTOR = TextSelector(
    TextSelectorConfig(type=TextSelectorType.EMAIL, autocomplete="username")
)
PASSWORD_SELECTOR = TextSelector(
    TextSelectorConfig(type=TextSelectorType.PASSWORD, autocomplete="current-password")
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): USERNAME_SELECTOR,
        vol.Required(CONF_PASSWORD): PASSWORD_SELECTOR,
    }
)
STEP_REAUTH_DATA_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): PASSWORD_SELECTOR})

ENERGY_AID_MODE_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=list(ENERGY_AID_MODES),
        translation_key="energy_aid_mode",
        mode=SelectSelectorMode.DROPDOWN,
    )
)
# The collapsed section holding the aid amount override.
SECTION_ADVANCED = "advanced"
ENERGY_AID_AMOUNT_SELECTOR = NumberSelector(
    NumberSelectorConfig(
        min=0,
        max=1000,
        step=0.01,
        unit_of_measurement="€/MWh",
        mode=NumberSelectorMode.BOX,
    )
)


def _points_schema(available: dict[str, str], selected: list[str]) -> vol.Schema:
    """Return a form for picking delivery points, ``selected`` ticked."""
    return vol.Schema(
        {
            vol.Required(CONF_DELIVERY_POINTS, default=selected): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        SelectOptionDict(value=point_id, label=label)
                        for point_id, label in available.items()
                    ],
                    multiple=True,
                    mode=SelectSelectorMode.LIST,
                )
            )
        }
    )


class SseEzonaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SSE eZóna."""

    VERSION = 1

    def __init__(self) -> None:
        """Start with nothing known about the account."""
        self._user_input: dict[str, Any] = {}
        self._available: dict[str, str] = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> SseEzonaOptionsFlow:
        """Let the user change which delivery points are added."""
        return SseEzonaOptionsFlow()

    async def _login(
        self, username: str, password: str
    ) -> tuple[str | None, dict[str, str]]:
        """Log in once; return an error key and the account's delivery points."""
        api = SseEzonaApi(async_get_clientsession(self.hass), username, password)
        try:
            async with api.logged_in_session():
                info = await api.get_user_info()
        except SseEzonaUnsupportedLoginError:
            return "unsupported_login", {}
        except SseEzonaAuthError:
            return "invalid_auth", {}
        except SseEzonaError as err:
            _LOGGER.debug("Login check failed: %s", err)
            return "cannot_connect", {}
        points = electricity_points(info or {})
        return None, {raw["id"]: point_label(raw) for raw in points}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the eZóna credentials and check them."""
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_USERNAME].lower())
            self._abort_if_unique_id_configured()
            error, available = await self._login(
                user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
            )
            if error is None and not available:
                error = "no_delivery_points"
            if error is None:
                self._user_input = user_input
                self._available = available
                if len(available) == 1:
                    return self._create_entry(list(available))
                return await self.async_step_delivery_points()
            errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )

    async def async_step_delivery_points(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick the delivery points to add."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input[CONF_DELIVERY_POINTS]:
                return self._create_entry(user_input[CONF_DELIVERY_POINTS])
            errors["base"] = "no_selection"

        return self.async_show_form(
            step_id="delivery_points",
            data_schema=_points_schema(self._available, list(self._available)),
            errors=errors,
        )

    def _create_entry(self, selected: list[str]) -> ConfigFlowResult:
        return self.async_create_entry(
            title=self._user_input[CONF_USERNAME],
            data=self._user_input,
            options={CONF_DELIVERY_POINTS: selected},
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start reauthentication after the portal rejected the credentials."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the new password."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            error, _ = await self._login(
                entry.data[CONF_USERNAME], user_input[CONF_PASSWORD]
            )
            if error is None:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]}
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            description_placeholders={"username": entry.data[CONF_USERNAME]},
            errors=errors,
        )


class SseEzonaOptionsFlow(OptionsFlowWithReload):
    """Change which delivery points are added and whether the aid applies."""

    def __init__(self) -> None:
        """Start without a selection."""
        self._available: dict[str, str] = {}
        self._selected: list[str] = []

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the account's delivery points from the last update."""
        entry = self.config_entry
        coordinator = getattr(entry, "runtime_data", None)
        if coordinator is None or coordinator.data is None:
            return self.async_abort(reason="not_loaded")
        available = self._available = coordinator.data.available

        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input[CONF_DELIVERY_POINTS]:
                self._selected = user_input[CONF_DELIVERY_POINTS]
                return await self.async_step_energy_aid()
            errors["base"] = "no_selection"

        selected = entry.options.get(CONF_DELIVERY_POINTS, list(available))
        return self.async_show_form(
            step_id="init",
            data_schema=_points_schema(
                available, [p for p in selected if p in available]
            ),
            errors=errors,
        )

    async def async_step_energy_aid(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose per delivery point whether the energy aid applies.

        The fields are named by the points' labels, which are what the form
        shows for a field without a translation.
        """
        options = self.config_entry.options
        modes: dict[str, str] = dict(options.get(CONF_ENERGY_AID) or {})
        labels = {
            point_id: self._available.get(point_id, point_id)
            for point_id in self._selected
        }

        if user_input is not None:
            for point_id, label in labels.items():
                modes[point_id] = user_input.get(label, ENERGY_AID_AUTO)
            data: dict[str, Any] = {
                CONF_DELIVERY_POINTS: self._selected,
                CONF_ENERGY_AID: modes,
            }
            # An emptied field removes the override.
            amount = (user_input.get(SECTION_ADVANCED) or {}).get(
                CONF_ENERGY_AID_AMOUNT
            )
            if amount is not None:
                data[CONF_ENERGY_AID_AMOUNT] = float(amount)
            return self.async_create_entry(data=data)

        fields: dict[Any, Any] = {
            vol.Required(
                label, default=modes.get(point_id, ENERGY_AID_AUTO)
            ): ENERGY_AID_MODE_SELECTOR
            for point_id, label in labels.items()
        }
        amount = options.get(CONF_ENERGY_AID_AMOUNT)
        fields[vol.Required(SECTION_ADVANCED)] = section(
            vol.Schema(
                {
                    vol.Optional(
                        CONF_ENERGY_AID_AMOUNT,
                        description={"suggested_value": amount},
                    ): ENERGY_AID_AMOUNT_SELECTOR
                }
            ),
            # Open when an override is set, so it isn't forgotten.
            {"collapsed": amount is None},
        )
        return self.async_show_form(
            step_id="energy_aid", data_schema=vol.Schema(fields)
        )

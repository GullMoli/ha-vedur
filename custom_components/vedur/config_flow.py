"""Config flow for Veðurstofa Íslands integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any
from xml.etree import ElementTree

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DOMAIN,
    CONF_STATION_ID,
    CONF_STATION_NAME,
    CONF_ALERT_LANGUAGE,
    FORECAST_URL,
    POPULAR_STATIONS,
    ALERT_LANGUAGES,
)

_LOGGER = logging.getLogger(__name__)


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""


class InvalidStation(Exception):
    """Error to indicate the station ID is invalid."""


async def validate_station(hass: HomeAssistant, station_id: str) -> dict[str, Any]:
    """Validate the station ID by fetching data from the API."""
    url = FORECAST_URL.format(station_id=station_id)
    session = async_get_clientsession(hass)

    try:
        async with asyncio.timeout(30):
            async with session.get(url) as response:
                if response.status != 200:
                    raise CannotConnect(f"API returned status {response.status}")
                xml_text = await response.text()
    except asyncio.TimeoutError as err:
        raise CannotConnect("Connection timeout") from err
    except CannotConnect:
        raise
    except Exception as err:
        raise CannotConnect(f"Connection error: {err}") from err

    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError as err:
        raise InvalidStation(f"Invalid XML response: {err}") from err

    station = root.find(".//station")
    if station is None:
        raise InvalidStation("No station data in response")

    if station.get("valid", "0") != "1":
        raise InvalidStation(f"Station {station_id} is not valid")

    name_elem = station.find("n")
    if name_elem is not None and name_elem.text:
        station_name = name_elem.text.strip()
    else:
        station_name = POPULAR_STATIONS.get(station_id, f"Station {station_id}")

    if not station.findall(".//forecast"):
        raise InvalidStation(f"No forecast data for station {station_id}")

    return {"station_id": station_id, "station_name": station_name}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Veðurstofa Íslands."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._station_id: str | None = None
        self._station_name: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step — choose setup method."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["popular", "custom"],
        )

    async def async_step_popular(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle selection from popular stations."""
        errors: dict[str, str] = {}

        if user_input is not None:
            station_id = user_input[CONF_STATION_ID]
            try:
                info = await validate_station(self.hass, station_id)
                self._station_id = info["station_id"]
                self._station_name = info["station_name"]
                return await self.async_step_language()
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidStation:
                errors["base"] = "invalid_station"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        station_options = {
            k: f"{v} ({k})"
            for k, v in sorted(POPULAR_STATIONS.items(), key=lambda x: x[1])
        }

        return self.async_show_form(
            step_id="popular",
            data_schema=vol.Schema(
                {vol.Required(CONF_STATION_ID, default="1"): vol.In(station_options)}
            ),
            errors=errors,
            last_step=False,
        )

    async def async_step_custom(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle custom station ID entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            station_id = str(user_input[CONF_STATION_ID]).strip()
            try:
                info = await validate_station(self.hass, station_id)
                self._station_id = info["station_id"]
                self._station_name = info["station_name"]
                return await self.async_step_language()
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidStation:
                errors["base"] = "invalid_station"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="custom",
            data_schema=vol.Schema({vol.Required(CONF_STATION_ID): str}),
            errors=errors,
            last_step=False,
        )

    async def async_step_language(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle language selection for alerts."""
        if user_input is not None:
            await self.async_set_unique_id(self._station_id)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=self._station_name,
                data={
                    CONF_STATION_ID: self._station_id,
                    CONF_STATION_NAME: self._station_name,
                    CONF_ALERT_LANGUAGE: user_input[CONF_ALERT_LANGUAGE],
                },
            )

        return self.async_show_form(
            step_id="language",
            data_schema=vol.Schema(
                {vol.Required(CONF_ALERT_LANGUAGE, default="is"): vol.In(ALERT_LANGUAGES)}
            ),
            last_step=True,
        )

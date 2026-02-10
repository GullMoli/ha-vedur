"""Weather platform for Veðurstofa Íslands."""
from __future__ import annotations

from typing import Any

from homeassistant.components.weather import (
    Forecast,
    WeatherEntity,
    WeatherEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, highest_severity
from .coordinator import VedurDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Vedur weather entity."""
    coordinator: VedurDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([VedurWeather(coordinator)])


class VedurWeather(CoordinatorEntity[VedurDataUpdateCoordinator], WeatherEntity):
    """Representation of Vedur weather."""

    _attr_has_entity_name = True
    _attr_name = None  # Use device name
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_wind_speed_unit = UnitOfSpeed.METERS_PER_SECOND
    _attr_native_pressure_unit = UnitOfPressure.HPA
    _attr_supported_features = (
        WeatherEntityFeature.FORECAST_HOURLY | WeatherEntityFeature.FORECAST_DAILY
    )

    def __init__(self, coordinator: VedurDataUpdateCoordinator) -> None:
        """Initialize the weather entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.station_id}_weather"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.station_id)},
            name=f"Veður {coordinator.station_name}",
            manufacturer="Veðurstofa Íslands",
        )

    def _val(self, key: str) -> Any:
        """Get a value from coordinator data, or None."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(key)

    @property
    def native_temperature(self) -> float | None:
        return self._val("temperature")

    @property
    def native_wind_speed(self) -> float | None:
        return self._val("wind_speed")

    @property
    def native_wind_gust_speed(self) -> float | None:
        return self._val("wind_gust")

    @property
    def wind_bearing(self) -> float | str | None:
        return self._val("wind_bearing")

    @property
    def condition(self) -> str | None:
        return self._val("condition")

    @property
    def humidity(self) -> float | None:
        return self._val("humidity")

    @property
    def native_pressure(self) -> float | None:
        return self._val("pressure")

    @property
    def native_apparent_temperature(self) -> float | None:
        return self._val("feels_like")

    @property
    def cloud_coverage(self) -> int | None:
        cover = self._val("cloud_cover")
        return int(cover) if cover is not None else None

    @property
    def extra_state_attributes(self) -> dict | None:
        if self.coordinator.data is None:
            return None

        attrs: dict = {}
        alerts = self.coordinator.data.get("alerts", [])
        attrs["alert_count"] = len(alerts)
        attrs["highest_alert_severity"] = highest_severity(alerts) if alerts else "none"
        if alerts:
            attrs["alerts"] = alerts

        precip = self.coordinator.data.get("precipitation")
        if precip is not None:
            attrs["precipitation"] = precip

        obs_time = self.coordinator.data.get("observation_time")
        if obs_time:
            attrs["observation_time"] = obs_time

        return attrs

    async def async_forecast_hourly(self) -> list[Forecast] | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("forecast_hourly")

    async def async_forecast_daily(self) -> list[Forecast] | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("forecast_daily")

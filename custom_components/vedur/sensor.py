"""Sensor platform for Veðurstofa Íslands."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DEGREE,
    PERCENTAGE,
    UnitOfLength,
    UnitOfPressure,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, highest_severity
from .coordinator import VedurDataUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class VedurSensorEntityDescription(SensorEntityDescription):
    """Describes a Vedur sensor entity."""

    value_fn: Callable[[dict], Any]


SENSOR_DESCRIPTIONS: tuple[VedurSensorEntityDescription, ...] = (
    VedurSensorEntityDescription(
        key="temperature",
        translation_key="temperature",
        name="Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("temperature"),
    ),
    VedurSensorEntityDescription(
        key="feels_like",
        translation_key="feels_like",
        name="Feels Like",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer-lines",
        value_fn=lambda data: data.get("feels_like"),
    ),
    VedurSensorEntityDescription(
        key="wind_speed",
        translation_key="wind_speed",
        name="Wind Speed",
        native_unit_of_measurement="m/s",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:weather-windy",
        value_fn=lambda data: data.get("wind_speed"),
    ),
    VedurSensorEntityDescription(
        key="wind_gust",
        translation_key="wind_gust",
        name="Wind Gust",
        native_unit_of_measurement="m/s",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:weather-windy-variant",
        value_fn=lambda data: data.get("wind_gust"),
    ),
    VedurSensorEntityDescription(
        key="wind_direction",
        translation_key="wind_direction",
        name="Wind Direction",
        icon="mdi:compass-outline",
        value_fn=lambda data: data.get("wind_direction"),
    ),
    VedurSensorEntityDescription(
        key="wind_bearing",
        translation_key="wind_bearing",
        name="Wind Bearing",
        native_unit_of_measurement=DEGREE,
        icon="mdi:compass",
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.get("wind_bearing"),
    ),
    VedurSensorEntityDescription(
        key="precipitation",
        translation_key="precipitation",
        name="Precipitation",
        native_unit_of_measurement="mm",
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:weather-rainy",
        value_fn=lambda data: data.get("precipitation"),
    ),
    VedurSensorEntityDescription(
        key="cloud_cover",
        translation_key="cloud_cover",
        name="Cloud Cover",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:cloud",
        value_fn=lambda data: data.get("cloud_cover"),
    ),
    VedurSensorEntityDescription(
        key="humidity",
        translation_key="humidity",
        name="Humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("humidity"),
    ),
    VedurSensorEntityDescription(
        key="pressure",
        translation_key="pressure",
        name="Pressure",
        native_unit_of_measurement=UnitOfPressure.HPA,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("pressure"),
    ),
    VedurSensorEntityDescription(
        key="visibility",
        translation_key="visibility",
        name="Visibility",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:eye",
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.get("visibility"),
    ),
    VedurSensorEntityDescription(
        key="condition",
        translation_key="condition",
        name="Condition",
        icon="mdi:weather-cloudy",
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.get("condition"),
    ),
    VedurSensorEntityDescription(
        key="condition_text",
        translation_key="condition_text",
        name="Weather Description",
        icon="mdi:text",
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.get("condition_text"),
    ),
    VedurSensorEntityDescription(
        key="alert_count",
        translation_key="alert_count",
        name="Active Alerts",
        icon="mdi:alert",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: len(data.get("alerts", [])),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Vedur sensors based on a config entry."""
    coordinator: VedurDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        VedurSensor(coordinator, desc) for desc in SENSOR_DESCRIPTIONS
    )


class VedurSensor(CoordinatorEntity[VedurDataUpdateCoordinator], SensorEntity):
    """Representation of a Vedur sensor."""

    entity_description: VedurSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: VedurDataUpdateCoordinator,
        description: VedurSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.station_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.station_id)},
            name=f"Veður {coordinator.station_name}",
            manufacturer="Veðurstofa Íslands",
        )

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict | None:
        """Return additional state attributes for the alert sensor."""
        if self.coordinator.data is None:
            return None

        if self.entity_description.key != "alert_count":
            return None

        alerts = self.coordinator.data.get("alerts", [])
        if not alerts:
            return None

        return {
            "alerts": alerts,
            "highest_severity": highest_severity(alerts),
        }

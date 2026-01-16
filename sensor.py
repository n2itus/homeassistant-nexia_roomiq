#Sensors for individual Nexia/Trane RoomIQ temperatures
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from homeassistant.components.nexia.const import DOMAIN as NEXIA_DOMAIN
from homeassistant.components.nexia.coordinator import NexiaDataUpdateCoordinator
from homeassistant.components.nexia.entity import NexiaEntity

from .const import DOMAIN

# Descriptions for the sensors we want to expose
ROOM_IQ_SENSOR_TYPES = [
    SensorEntityDescription(
        key="temperature",
        name="RoomIQ Temperature",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,  # will adjust if needed
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        has_entity_name=True,
    ),
    SensorEntityDescription(
        key="humidity",
        name="RoomIQ Humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category="diagnostic",
      has_entity_name=True,
    ),
    SensorEntityDescription(
        key="battery_level",
        name="RoomIQ Battery",
        native_unit_of_measurement=PERCENTAGE,
        entity_category="diagnostic",
        state_class=SensorStateClass.MEASUREMENT,
        has_entity_name=True,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    # Set up Nexia RoomIQ sensors from a config entry
    # We don't have our own config entry — we piggyback on nexia's coordinator
    # Find the nexia coordinator(s) from hass.data
    coordinators = [
        entry_data["coordinator"]
        for entry_id, entry_data in hass.data[NEXIA_DOMAIN].items()
        if "coordinator" in entry_data
    ]

    entities = []

    for coordinator in coordinators:  # usually one, but support multiple houses
        data = coordinator.data

        for house in data.houses.values():
            for thermostat in house.thermostats.values():
                for zone_id, zone in thermostat.zones.items():
                    if not hasattr(zone, "room_iq_sensors") or not zone.room_iq_sensors:
                        continue

                    for sensor_data in zone.room_iq_sensors:
                        sensor_id = sensor_data["id"]
                        sensor_name = sensor_data["name"]

                        # Create one entity per type (temp, etc.)
                        for description in ROOM_IQ_SENSOR_TYPES:
                            entities.append(
                                NexiaRoomIQSensors(
                                    coordinator,
                                    zone_id,
                                    sensor_id,
                                    sensor_name,
                                    description,
                                )
                            )

    if entities:
        async_add_entities(entities)


class NexiaRoomIQSensors(NexiaEntity, SensorEntity):
    # Individual RoomIQ sensor value from Nexia

    def __init__(
        self,
        coordinator: NexiaDataUpdateCoordinator,
        zone_id: int,
        sensor_id: int,
        sensor_name: str,
        description: SensorEntityDescription,
    ) -> None:
        # Initialize the sensor.
        super().__init__(coordinator, zone_id)
        self._sensor_id = sensor_id
        self.entity_description = description

        self._attr_unique_id = f"{DOMAIN}_{zone_id}_{sensor_id}_{description.key}"
        self._attr_name = f"{sensor_name} {description.name}"

        # Make sure it groups nicely under the thermostat/zone device
        # Reuse the device info from the parent NexiaEntity
        self._attr_device_info = self.coordinator.get_device_info(zone_id)  # may need adjustment

    @property
    def native_value(self) -> float | None:
        # Return the current value
        zone = self.coordinator.data.zones.get(self._zone_id)
        if not zone or not zone.room_iq_sensors:
            return None

        for s in zone.room_iq_sensors:
            if s["id"] == self._sensor_id:
                key = self.entity_description.key
                value = s.get(key)
                if value is not None and s.get(f"{key}_valid", True):
                    return value
        return None

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        value = self.native_value
        return value is not None

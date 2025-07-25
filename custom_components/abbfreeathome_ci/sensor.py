"""Create ABB-free@home sensor entities."""

from typing import Any

from abbfreeathome import FreeAtHome
from abbfreeathome.channels.brightness_sensor import BrightnessSensor
from abbfreeathome.channels.movement_detector import (
    BlockableMovementDetector,
    MovementDetector,
)
from abbfreeathome.channels.temperature_sensor import TemperatureSensor
from abbfreeathome.channels.wind_sensor import WindSensor
from abbfreeathome.channels.window_door_sensor import (
    WindowDoorSensor,
    WindowDoorSensorPosition,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import LIGHT_LUX, UnitOfSpeed, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_CREATE_SUBDEVICES, CONF_SERIAL, DOMAIN, MANUFACTURER

SENSOR_DESCRIPTIONS = {
    "BrightnessSensor": {
        "channel_class": BrightnessSensor,
        "value_attribute": "state",
        "entity_description_kwargs": {
            "device_class": SensorDeviceClass.ILLUMINANCE,
            "native_unit_of_measurement": LIGHT_LUX,
            "state_class": SensorStateClass.MEASUREMENT,
            "translation_key": "brightness_sensor",
        },
    },
    "MovementDetectorBrightness": {
        "channel_class": MovementDetector,
        "value_attribute": "brightness",
        "entity_description_kwargs": {
            "device_class": SensorDeviceClass.ILLUMINANCE,
            "native_unit_of_measurement": LIGHT_LUX,
            "state_class": SensorStateClass.MEASUREMENT,
            "translation_key": "movement_detector_brightness",
        },
    },
    "BlockableMovementDetectorBrightness": {
        "channel_class": BlockableMovementDetector,
        "value_attribute": "brightness",
        "entity_description_kwargs": {
            "device_class": SensorDeviceClass.ILLUMINANCE,
            "native_unit_of_measurement": LIGHT_LUX,
            "state_class": SensorStateClass.MEASUREMENT,
            "translation_key": "movement_detector_brightness",
        },
    },
    "WindowDoorSensorPosition": {
        "channel_class": WindowDoorSensor,
        "value_attribute": "position",
        "entity_description_kwargs": {
            "device_class": SensorDeviceClass.ENUM,
            "options": [position.name for position in WindowDoorSensorPosition],
            "translation_key": "window_position",
        },
    },
    "TemperatureSensor": {
        "channel_class": TemperatureSensor,
        "value_attribute": "state",
        "entity_description_kwargs": {
            "device_class": SensorDeviceClass.TEMPERATURE,
            "native_unit_of_measurement": UnitOfTemperature.CELSIUS,
            "state_class": SensorStateClass.MEASUREMENT,
            "translation_key": "temperature_sensor",
        },
    },
    "WindSensorSpeed": {
        "channel_class": WindSensor,
        "value_attribute": "state",
        "entity_description_kwargs": {
            "device_class": SensorDeviceClass.WIND_SPEED,
            "native_unit_of_measurement": UnitOfSpeed.METERS_PER_SECOND,
            "state_class": SensorStateClass.MEASUREMENT,
            "translation_key": "wind_sensor_speed",
        },
    },
    "WindSensorForce": {
        "channel_class": WindSensor,
        "value_attribute": "force",
        "entity_description_kwargs": {
            "device_class": SensorDeviceClass.WIND_SPEED,
            "native_unit_of_measurement": UnitOfSpeed.BEAUFORT,
            "suggested_unit_of_measurement": UnitOfSpeed.BEAUFORT,
            "state_class": SensorStateClass.MEASUREMENT,
            "translation_key": "wind_sensor_force",
        },
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors."""
    free_at_home: FreeAtHome = hass.data[DOMAIN][entry.entry_id]

    for key, description in SENSOR_DESCRIPTIONS.items():
        async_add_entities(
            FreeAtHomeSensorEntity(
                channel,
                value_attribute=description.get("value_attribute"),
                entity_description_kwargs={"key": key}
                | description.get("entity_description_kwargs"),
                sysap_serial_number=entry.data[CONF_SERIAL],
                create_subdevices=entry.data[CONF_CREATE_SUBDEVICES],
            )
            for channel in free_at_home.get_channels_by_class(
                channel_class=description.get("channel_class")
            )
            if getattr(channel, description.get("value_attribute")) is not None
        )


class FreeAtHomeSensorEntity(SensorEntity):
    """Defines a free@home sensor entity."""

    _attr_should_poll: bool = False

    def __init__(
        self,
        channel: BrightnessSensor | MovementDetector | TemperatureSensor | WindSensor,
        value_attribute: str,
        entity_description_kwargs: dict[str:Any],
        sysap_serial_number: str,
        create_subdevices: bool,
    ) -> None:
        """Initialize the sensor."""
        super().__init__()
        self._channel = channel
        self._value_attribute = value_attribute
        self._sysap_serial_number = sysap_serial_number
        self._create_subdevices = create_subdevices

        self.entity_description = SensorEntityDescription(
            has_entity_name=True,
            name=channel.channel_name,
            translation_placeholders={"channel_id": channel.channel_id},
            **entity_description_kwargs,
        )

    async def async_added_to_hass(self) -> None:
        """Run when this Entity has been added to HA."""
        self._channel.register_callback(
            callback_attribute=self._value_attribute, callback=self.async_write_ha_state
        )

    async def async_will_remove_from_hass(self) -> None:
        """Entity being removed from hass."""
        self._channel.remove_callback(
            callback_attribute=self._value_attribute, callback=self.async_write_ha_state
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Information about this entity/device."""
        if self._create_subdevices and self._channel.device.is_multi_device:
            return DeviceInfo(
                identifiers={
                    (
                        DOMAIN,
                        f"{self._channel.device_serial}_{self._channel.channel_id}",
                    )
                },
                name=f"{self._channel.device_name} ({self._channel.channel_id})",
                manufacturer=MANUFACTURER,
                serial_number=f"{self._channel.device_serial}_{self._channel.channel_id}",
                hw_version=f"{self._channel.device.device_id} (sub)",
                suggested_area=self._channel.room_name,
                via_device=(DOMAIN, self._channel.device_serial),
            )

        return DeviceInfo(identifiers={(DOMAIN, self._channel.device_serial)})

    @property
    def native_value(self) -> float | None:
        """Return state of the sensor."""
        return getattr(self._channel, self._value_attribute)

    @property
    def unique_id(self) -> str | None:
        """Return a unique ID."""
        return f"{self._channel.device_serial}_{self._channel.channel_id}_{self.entity_description.key}"

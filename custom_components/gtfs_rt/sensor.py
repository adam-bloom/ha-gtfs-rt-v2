"""GTFS Realtime sensor platform."""

import logging

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_DUE_AT,
    ATTR_DUE_IN,
    ATTR_NEXT_DEPARTURES,
    ATTR_NEXT_UP,
    ATTR_ROUTE,
    ATTR_STOP_ID,
    ATTR_DIRECTION_ID,
    CONF_DEPARTURES,
    CONF_DIRECTION_ID,
    CONF_ICON,
    CONF_NUM_DEPARTURES,
    CONF_ROUTE,
    CONF_STOP_ID,
    DEFAULT_DIRECTION,
    DEFAULT_ICON,
    DEFAULT_NUM_DEPARTURES,
    DOMAIN,
    TIME_STR_FORMAT,
)
from .coordinator import GtfsRtCoordinator, due_in_minutes

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Old YAML platform setup — no longer used, config flow handles setup."""
    return


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up GTFS-RT sensors from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    departures = entry.data.get(CONF_DEPARTURES, [])
    num_departures = entry.options.get(CONF_NUM_DEPARTURES, DEFAULT_NUM_DEPARTURES)

    entities = []
    for departure in departures:
        entities.append(
            GtfsRtSensor(
                coordinator=coordinator,
                entry=entry,
                departure=departure,
                num_departures=num_departures,
            )
        )

    async_add_entities(entities)


class GtfsRtSensor(CoordinatorEntity, SensorEntity):
    """Representation of a GTFS Realtime sensor."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "min"

    def __init__(
        self,
        coordinator: GtfsRtCoordinator,
        entry: ConfigEntry,
        departure: dict,
        num_departures: int,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._name = departure[CONF_NAME]
        self._stop = str(departure[CONF_STOP_ID])
        self._route = str(departure[CONF_ROUTE])
        self._direction = str(departure.get(CONF_DIRECTION_ID, DEFAULT_DIRECTION))
        self._icon_str = departure.get(CONF_ICON, DEFAULT_ICON)
        self._num_departures = num_departures

        self._attr_unique_id = (
            f"{entry.entry_id}_{self._route}_{self._stop}_{self._direction}"
        )

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return self._icon_str

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info to group sensors under one device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=f"GTFS-RT {self._entry.title}",
            manufacturer="GTFS-Realtime",
            entry_type=DeviceEntryType.SERVICE,
        )

    def _get_next_services(self):
        """Get upcoming services for this route/direction/stop."""
        if self.coordinator.data is None:
            _LOGGER.debug("%s: coordinator data is None", self._name)
            return []
        result = (
            self.coordinator.data
            .get(self._route, {})
            .get(self._direction, {})
            .get(self._stop, [])
        )
        if not result and self.coordinator.data:
            available_routes = list(self.coordinator.data.keys())[:5]
            _LOGGER.debug(
                "%s: no data for route=%s dir=%s stop=%s. "
                "Available routes: %s",
                self._name, self._route, self._direction, self._stop,
                available_routes,
            )
        return result

    @property
    def native_value(self):
        """Return minutes until next arrival."""
        next_services = self._get_next_services()
        if next_services:
            return due_in_minutes(next_services[0].arrival_time)
        return None

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        next_services = self._get_next_services()
        num = min(self._num_departures, len(next_services))

        attrs = {
            ATTR_STOP_ID: self._stop,
            ATTR_ROUTE: self._route,
            ATTR_DIRECTION_ID: self._direction,
        }

        # Backward-compatible flat attributes
        if num > 0:
            attrs[ATTR_DUE_IN] = due_in_minutes(next_services[0].arrival_time)
            attrs[ATTR_DUE_AT] = next_services[0].arrival_time.strftime(TIME_STR_FORMAT)
            if next_services[0].position:
                attrs[ATTR_LATITUDE] = next_services[0].position.latitude
                attrs[ATTR_LONGITUDE] = next_services[0].position.longitude
        if num > 1:
            attrs[ATTR_NEXT_UP] = next_services[1].arrival_time.strftime(TIME_STR_FORMAT)

        # Structured list of next departures
        next_departures = []
        for i in range(num):
            dep = {
                "departure": next_services[i].arrival_time.strftime(TIME_STR_FORMAT),
                "minutes": due_in_minutes(next_services[i].arrival_time),
            }
            if next_services[i].position:
                dep["latitude"] = next_services[i].position.latitude
                dep["longitude"] = next_services[i].position.longitude
            next_departures.append(dep)
        attrs[ATTR_NEXT_DEPARTURES] = next_departures

        return attrs

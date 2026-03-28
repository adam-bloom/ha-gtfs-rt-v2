"""DataUpdateCoordinator for GTFS Realtime integration."""

import logging
from collections import namedtuple
from datetime import datetime, timedelta

import homeassistant.util.dt as dt_util
import requests
from google.transit import gtfs_realtime_pb2
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_API_KEY,
    CONF_API_KEY_HEADER_NAME,
    CONF_ROUTE_DELIMITER,
    CONF_TRIP_UPDATE_URL,
    CONF_UPDATE_INTERVAL,
    CONF_VEHICLE_POSITION_URL,
    CONF_X_API_KEY,
    DEFAULT_API_KEY_HEADER_NAME,
    DEFAULT_DIRECTION,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

StopDetails = namedtuple("StopDetails", ["arrival_time", "position"])


def due_in_minutes(timestamp):
    """Get the remaining minutes from now until a given datetime object."""
    diff = timestamp - dt_util.now().replace(tzinfo=None)
    return int(diff.total_seconds() / 60)


def _get_gtfs_feed_entities(url, headers, label):
    """Fetch and parse a GTFS-RT feed."""
    feed = gtfs_realtime_pb2.FeedMessage()
    response = requests.get(url, headers=headers, timeout=20)
    if response.status_code != 200:
        raise UpdateFailed(
            f"Error fetching {label}: HTTP {response.status_code}"
        )
    feed.ParseFromString(response.content)
    return feed.entity


class GtfsRtCoordinator(DataUpdateCoordinator):
    """Coordinator to manage GTFS-RT data fetching."""

    def __init__(self, hass, entry):
        """Initialize the coordinator."""
        update_interval = entry.options.get(
            CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
        )
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=update_interval),
        )
        self.config_entry = entry
        self._trip_update_url = entry.data[CONF_TRIP_UPDATE_URL]
        self._vehicle_position_url = entry.data.get(CONF_VEHICLE_POSITION_URL, "")
        self._route_delimiter = entry.data.get(CONF_ROUTE_DELIMITER)

        # Build auth headers
        api_key = entry.data.get(CONF_API_KEY)
        x_api_key = entry.data.get(CONF_X_API_KEY)
        api_key_header = entry.data.get(
            CONF_API_KEY_HEADER_NAME, DEFAULT_API_KEY_HEADER_NAME
        )
        if api_key:
            self._headers = {api_key_header: api_key}
        elif x_api_key:
            self._headers = {"x-api-key": x_api_key}
        else:
            self._headers = None

    async def _async_update_data(self):
        """Fetch data from GTFS-RT feeds."""
        try:
            data = await self.hass.async_add_executor_job(self._fetch_data)
        except requests.RequestException as err:
            raise UpdateFailed(f"Error communicating with GTFS-RT feed: {err}") from err

        if _LOGGER.isEnabledFor(logging.DEBUG):
            routes = list(data.keys())
            total_stops = sum(
                len(stops)
                for route in data.values()
                for direction in route.values()
                for stops in direction.values()
            )
            _LOGGER.debug(
                "GTFS-RT update: %d routes, %d total stop entries. Routes: %s",
                len(routes), total_stops, routes[:10],
            )
        return data

    def _fetch_data(self):
        """Fetch and parse GTFS-RT data (runs in executor)."""
        positions = {}
        if self._vehicle_position_url:
            positions = self._get_vehicle_positions()

        return self._get_route_statuses(positions)

    def _get_route_statuses(self, vehicle_positions):
        """Parse trip update feed into departure times dict."""
        departure_times = {}

        feed_entities = _get_gtfs_feed_entities(
            url=self._trip_update_url, headers=self._headers, label="trip data"
        )

        for entity in feed_entities:
            if not entity.HasField("trip_update"):
                continue

            trip = entity.trip_update.trip

            # Handle route delimiter splitting
            if self._route_delimiter is not None:
                route_id_split = trip.route_id.split(self._route_delimiter)
                if route_id_split[0] == self._route_delimiter:
                    route_id = trip.route_id
                else:
                    route_id = route_id_split[0]
            else:
                route_id = trip.route_id

            if route_id not in departure_times:
                departure_times[route_id] = {}

            direction_id = (
                str(trip.direction_id)
                if trip.direction_id is not None
                else DEFAULT_DIRECTION
            )
            if direction_id not in departure_times[route_id]:
                departure_times[route_id][direction_id] = {}

            for stop in entity.trip_update.stop_time_update:
                stop_id = stop.stop_id
                if stop_id not in departure_times[route_id][direction_id]:
                    departure_times[route_id][direction_id][stop_id] = []

                # Use arrival time; fall back on departure time
                stop_time = stop.departure.time if stop.arrival.time == 0 else stop.arrival.time

                # Ignore arrival times in the past
                arrival_dt = datetime.fromtimestamp(stop_time)
                if due_in_minutes(arrival_dt) >= 0:
                    details = StopDetails(
                        arrival_dt,
                        vehicle_positions.get(trip.trip_id),
                    )
                    departure_times[route_id][direction_id][stop_id].append(details)

        # Sort by arrival time
        for route in departure_times:
            for direction in departure_times[route]:
                for stop in departure_times[route][direction]:
                    departure_times[route][direction][stop].sort(
                        key=lambda t: t.arrival_time
                    )

        return departure_times

    def _get_vehicle_positions(self):
        """Fetch vehicle position feed."""
        positions = {}
        feed_entities = _get_gtfs_feed_entities(
            url=self._vehicle_position_url,
            headers=self._headers,
            label="vehicle positions",
        )

        for entity in feed_entities:
            vehicle = entity.vehicle
            if not vehicle.trip.trip_id:
                continue
            positions[vehicle.trip.trip_id] = vehicle.position

        return positions

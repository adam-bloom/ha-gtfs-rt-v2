"""Constants for the GTFS Realtime integration."""

from datetime import timedelta

DOMAIN = "gtfs_rt"

# Attribute names
ATTR_STOP_ID = "stop_id"
ATTR_ROUTE = "route"
ATTR_DIRECTION_ID = "direction_id"
ATTR_DUE_IN = "due_in"
ATTR_DUE_AT = "due_at"
ATTR_NEXT_UP = "next_service"
ATTR_NEXT_DEPARTURES = "next_departures"

# Configuration keys
CONF_API_KEY = "api_key"
CONF_X_API_KEY = "x_api_key"
CONF_API_KEY_HEADER_NAME = "api_key_header"
CONF_STOP_ID = "stopid"
CONF_ROUTE = "route"
CONF_DIRECTION_ID = "directionid"
CONF_DEPARTURES = "departures"
CONF_TRIP_UPDATE_URL = "trip_update_url"
CONF_VEHICLE_POSITION_URL = "vehicle_position_url"
CONF_ROUTE_DELIMITER = "route_delimiter"
CONF_ICON = "icon"
CONF_NUM_DEPARTURES = "num_departures"
CONF_UPDATE_INTERVAL = "update_interval"

# Defaults
DEFAULT_ICON = "mdi:bus"
DEFAULT_DIRECTION = "0"
DEFAULT_API_KEY_HEADER_NAME = "Authorization"
DEFAULT_NUM_DEPARTURES = 3
DEFAULT_UPDATE_INTERVAL = 60

# Timing
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=DEFAULT_UPDATE_INTERVAL)
TIME_STR_FORMAT = "%H:%M"

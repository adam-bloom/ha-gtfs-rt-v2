"""Config flow for GTFS Realtime integration."""

import logging
from typing import Any

import requests
import voluptuous as vol
from google.transit import gtfs_realtime_pb2
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    OptionsFlowWithConfigEntry,
)
from homeassistant.const import CONF_NAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    IconSelector,
    IconSelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from .const import (
    CONF_API_KEY,
    CONF_API_KEY_HEADER_NAME,
    CONF_DEPARTURES,
    CONF_DIRECTION_ID,
    CONF_ICON,
    CONF_NUM_DEPARTURES,
    CONF_ROUTE,
    CONF_ROUTE_DELIMITER,
    CONF_STOP_ID,
    CONF_TRIP_UPDATE_URL,
    CONF_UPDATE_INTERVAL,
    CONF_VEHICLE_POSITION_URL,
    CONF_X_API_KEY,
    DEFAULT_API_KEY_HEADER_NAME,
    DEFAULT_DIRECTION,
    DEFAULT_ICON,
    DEFAULT_NUM_DEPARTURES,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _validate_feed_url(url, headers=None):
    """Validate a GTFS-RT feed URL by attempting to fetch and parse it."""
    response = requests.get(url, headers=headers, timeout=20)
    response.raise_for_status()
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(response.content)
    return True


class GtfsRtConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for GTFS Realtime."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._feed_data: dict[str, Any] = {}
        self._departures: list[dict[str, Any]] = []

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlowWithConfigEntry:
        """Get the options flow handler."""
        return GtfsRtOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the feed configuration step."""
        errors = {}

        if user_input is not None:
            # Build headers for validation
            headers = None
            api_key = user_input.get(CONF_API_KEY)
            x_api_key = user_input.get(CONF_X_API_KEY)
            api_key_header = user_input.get(
                CONF_API_KEY_HEADER_NAME, DEFAULT_API_KEY_HEADER_NAME
            )
            if api_key:
                headers = {api_key_header: api_key}
            elif x_api_key:
                headers = {"x-api-key": x_api_key}

            try:
                await self.hass.async_add_executor_job(
                    _validate_feed_url, user_input[CONF_TRIP_UPDATE_URL], headers
                )
            except (requests.RequestException, Exception):
                errors["base"] = "cannot_connect"
            else:
                # Store feed config and move to departures
                self._feed_data = {
                    CONF_TRIP_UPDATE_URL: user_input[CONF_TRIP_UPDATE_URL],
                }
                # Only store optional fields if provided
                for key in (
                    CONF_VEHICLE_POSITION_URL,
                    CONF_API_KEY,
                    CONF_X_API_KEY,
                    CONF_API_KEY_HEADER_NAME,
                    CONF_ROUTE_DELIMITER,
                ):
                    if user_input.get(key):
                        self._feed_data[key] = user_input[key]

                return await self.async_step_departures()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_TRIP_UPDATE_URL): str,
                    vol.Optional(CONF_VEHICLE_POSITION_URL): str,
                    vol.Optional(CONF_API_KEY): str,
                    vol.Optional(CONF_X_API_KEY): str,
                    vol.Optional(
                        CONF_API_KEY_HEADER_NAME,
                        default=DEFAULT_API_KEY_HEADER_NAME,
                    ): str,
                    vol.Optional(CONF_ROUTE_DELIMITER): str,
                }
            ),
            errors=errors,
        )

    async def async_step_departures(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle adding a departure."""
        if user_input is not None:
            departure = {
                CONF_NAME: user_input[CONF_NAME],
                CONF_STOP_ID: user_input[CONF_STOP_ID],
                CONF_ROUTE: user_input[CONF_ROUTE],
                CONF_DIRECTION_ID: user_input.get(CONF_DIRECTION_ID, DEFAULT_DIRECTION),
                CONF_ICON: user_input.get(CONF_ICON, DEFAULT_ICON),
            }
            self._departures.append(departure)

            if user_input.get("add_another", False):
                return await self.async_step_departures()

            # Create the config entry
            data = {**self._feed_data, CONF_DEPARTURES: self._departures}
            title = self._feed_data[CONF_TRIP_UPDATE_URL].split("//")[-1].split("/")[0]
            return self.async_create_entry(title=title, data=data)

        return self.async_show_form(
            step_id="departures",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME): str,
                    vol.Required(CONF_ROUTE): str,
                    vol.Required(CONF_STOP_ID): str,
                    vol.Optional(CONF_DIRECTION_ID, default=DEFAULT_DIRECTION): str,
                    vol.Optional(CONF_ICON, default=DEFAULT_ICON): IconSelector(IconSelectorConfig()),
                    vol.Optional("add_another", default=False): bool,
                }
            ),
        )

    async def async_step_import(
        self, import_data: dict[str, Any]
    ) -> FlowResult:
        """Handle import from YAML configuration."""
        # Check if already imported by matching trip_update_url
        trip_url = import_data.get(CONF_TRIP_UPDATE_URL)
        await self.async_set_unique_id(trip_url)
        self._abort_if_unique_id_configured()

        # Build config entry data from YAML format
        data = {
            CONF_TRIP_UPDATE_URL: trip_url,
        }
        for key in (
            CONF_VEHICLE_POSITION_URL,
            CONF_API_KEY,
            CONF_X_API_KEY,
            CONF_API_KEY_HEADER_NAME,
            CONF_ROUTE_DELIMITER,
        ):
            if import_data.get(key):
                data[key] = import_data[key]

        # Convert departures
        departures = []
        for dep in import_data.get(CONF_DEPARTURES, []):
            departures.append(
                {
                    CONF_NAME: dep[CONF_NAME],
                    CONF_STOP_ID: str(dep[CONF_STOP_ID]),
                    CONF_ROUTE: str(dep[CONF_ROUTE]),
                    CONF_DIRECTION_ID: str(dep.get(CONF_DIRECTION_ID, DEFAULT_DIRECTION)),
                    CONF_ICON: dep.get(CONF_ICON, DEFAULT_ICON),
                }
            )
        data[CONF_DEPARTURES] = departures

        title = trip_url.split("//")[-1].split("/")[0]
        return self.async_create_entry(title=title, data=data)


class GtfsRtOptionsFlow(OptionsFlowWithConfigEntry):
    """Handle options flow for GTFS Realtime."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        super().__init__(config_entry)
        self._departures: list[dict[str, Any]] = list(
            config_entry.data.get(CONF_DEPARTURES, [])
        )

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show the options menu."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["settings", "departures_list", "add_departure"],
        )

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage general settings."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="settings",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_UPDATE_INTERVAL,
                        default=self.options.get(
                            CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=30, max=600, step=10, mode=NumberSelectorMode.BOX
                        )
                    ),
                    vol.Optional(
                        CONF_NUM_DEPARTURES,
                        default=self.options.get(
                            CONF_NUM_DEPARTURES, DEFAULT_NUM_DEPARTURES
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=1, max=10, step=1, mode=NumberSelectorMode.BOX
                        )
                    ),
                }
            ),
        )

    async def async_step_departures_list(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show list of departures and allow edit/removal."""
        if user_input is not None:
            action = user_input.get("action")
            selected = user_input.get("departure")
            if selected is not None and 0 <= selected < len(self._departures):
                if action == "edit":
                    self._edit_index = selected
                    return await self.async_step_edit_departure()
                elif action == "remove":
                    removed = self._departures.pop(selected)
                    _LOGGER.info("Removed departure: %s", removed.get(CONF_NAME))
                    self._save_departures_and_reload()
                    return self.async_create_entry(data=self.options)

        if not self._departures:
            return self.async_abort(reason="no_departures")

        dep_options = {
            i: f"{dep[CONF_NAME]} (Route {dep[CONF_ROUTE]}, Stop {dep[CONF_STOP_ID]})"
            for i, dep in enumerate(self._departures)
        }

        return self.async_show_form(
            step_id="departures_list",
            description_placeholders={
                "departures": "\n".join(
                    f"- **{dep[CONF_NAME]}**: Route {dep[CONF_ROUTE]}, "
                    f"Stop {dep[CONF_STOP_ID]}, Dir {dep.get(CONF_DIRECTION_ID, DEFAULT_DIRECTION)}"
                    for dep in self._departures
                )
            },
            data_schema=vol.Schema(
                {
                    vol.Required("departure"): vol.In(dep_options),
                    vol.Required("action", default="edit"): vol.In(
                        {"edit": "Edit", "remove": "Remove"}
                    ),
                }
            ),
        )

    async def async_step_edit_departure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Edit an existing departure."""
        if user_input is not None:
            self._departures[self._edit_index] = {
                CONF_NAME: user_input[CONF_NAME],
                CONF_STOP_ID: str(user_input[CONF_STOP_ID]),
                CONF_ROUTE: str(user_input[CONF_ROUTE]),
                CONF_DIRECTION_ID: str(user_input.get(CONF_DIRECTION_ID, DEFAULT_DIRECTION)),
                CONF_ICON: user_input.get(CONF_ICON, DEFAULT_ICON),
            }
            self._save_departures_and_reload()
            return self.async_create_entry(data=self.options)

        dep = self._departures[self._edit_index]
        return self.async_show_form(
            step_id="edit_departure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NAME, description={"suggested_value": str(dep.get(CONF_NAME, ""))}
                    ): str,
                    vol.Required(
                        CONF_ROUTE, description={"suggested_value": str(dep.get(CONF_ROUTE, ""))}
                    ): str,
                    vol.Required(
                        CONF_STOP_ID, description={"suggested_value": str(dep.get(CONF_STOP_ID, ""))}
                    ): str,
                    vol.Required(
                        CONF_DIRECTION_ID,
                        description={"suggested_value": str(dep.get(CONF_DIRECTION_ID, DEFAULT_DIRECTION))},
                    ): str,
                    vol.Required(
                        CONF_ICON,
                        description={"suggested_value": dep.get(CONF_ICON, DEFAULT_ICON)},
                    ): IconSelector(IconSelectorConfig()),
                }
            ),
        )

    def _save_departures_and_reload(self):
        """Save departures to config entry and schedule reload."""
        new_data = {**self.config_entry.data, CONF_DEPARTURES: self._departures}
        self.hass.config_entries.async_update_entry(
            self.config_entry, data=new_data
        )
        self.hass.async_create_task(
            self.hass.config_entries.async_reload(self.config_entry.entry_id)
        )

    async def async_step_add_departure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Add a new departure."""
        if user_input is not None:
            departure = {
                CONF_NAME: user_input[CONF_NAME],
                CONF_STOP_ID: str(user_input[CONF_STOP_ID]),
                CONF_ROUTE: str(user_input[CONF_ROUTE]),
                CONF_DIRECTION_ID: str(user_input.get(CONF_DIRECTION_ID, DEFAULT_DIRECTION)),
                CONF_ICON: user_input.get(CONF_ICON, DEFAULT_ICON),
            }
            self._departures.append(departure)
            self._save_departures_and_reload()
            return self.async_create_entry(data=self.options)

        return self.async_show_form(
            step_id="add_departure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME): str,
                    vol.Required(CONF_ROUTE): str,
                    vol.Required(CONF_STOP_ID): str,
                    vol.Optional(CONF_DIRECTION_ID, default=DEFAULT_DIRECTION): str,
                    vol.Optional(CONF_ICON, default=DEFAULT_ICON): IconSelector(IconSelectorConfig()),
                }
            ),
        )

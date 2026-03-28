# Home Assistant GTFS Realtime (rt)

This integration provides real-time departure data for local transit systems that provide GTFS-RT feeds. Each sensor shows minutes until the next arrival, with attributes including the next several departures, vehicle positions, and more.

Based on the excellent work previously done by @zacs and @phardy.

## Installation (HACS) - Recommended
0. Have [HACS](https://hacs.xyz/) installed, this will allow you to easily update
1. Add `https://github.com/mark1foley/ha-gtfs-rt-v2` as a [custom repository](https://hacs.xyz/docs/faq/custom_repositories/) as Type: Integration
2. Click install under "GTFS Realtime", then restart your instance for the installation to take effect.

## Installation (Manual)
1. Download this repository as a ZIP (green button, top right) and unzip the archive
2. Copy `/custom_components/gtfs_rt` to your `<config_dir>/custom_components/` directory
   * You will need to create the `custom_components` folder if it does not exist
   * On Hassio the final location will be `/config/custom_components/gtfs_rt`
   * On Hassbian the final location will be `/home/homeassistant/.homeassistant/custom_components/gtfs_rt`

## Configuration

Configuration is done through the Home Assistant UI:

1. Go to **Settings > Devices & Services > Add Integration**
2. Search for **GTFS-Realtime**
3. Enter your feed details:
   - **Trip Update URL** (required) — the GTFS-RT trip updates feed URL
   - **Vehicle Position URL** (optional) — enables live vehicle tracking on the HA map
   - **API Key** / **X-API Key** (optional) — authentication for the feed
   - **API Key Header Name** (optional) — custom auth header name (default: `Authorization`)
   - **Route Delimiter** (optional) — splits route IDs at this character (useful if your provider embeds calendar IDs into route IDs)
4. Add one or more departures to monitor:
   - **Sensor Name** — the name shown in HA. Tip: HA generates map labels from the first letters of the first 3 words, so `1 0 7 Bus` shows as "107" on the map.
   - **Route ID** — the GTFS route ID (if using a route delimiter, the text before the delimiter)
   - **Stop ID** — the stop ID for the location you want ETAs for
   - **Direction ID** (optional, default `0`) — the direction of travel from the GTFS `trips.txt` file
   - **Icon** (optional, default `mdi:bus`) — the icon shown in HA

### Managing Departures

After initial setup, you can manage departures through the integration's options:

1. Go to **Settings > Devices & Services > GTFS-Realtime > Configure**
2. Choose from:
   - **General settings** — update interval (30–600 seconds) and number of departures to display (1–10)
   - **Manage departures** — view, edit, or remove existing departures
   - **Add a departure** — add a new route/stop sensor

### Migrating from YAML

If you previously used YAML configuration (`platform: gtfs_rt` under `sensor:`), your config will be automatically imported as a config entry on the next restart. After confirming everything works, remove the YAML block from your `configuration.yaml` and restart.

## Sensor Data

Each sensor provides:

| Attribute | Description |
|---|---|
| **State** | Minutes until next arrival (integer) |
| `stop_id` | Configured stop ID |
| `route` | Configured route ID |
| `direction_id` | Configured direction ID |
| `due_in` | Minutes until next arrival |
| `due_at` | Next arrival time (HH:MM) |
| `latitude` / `longitude` | Vehicle position (if vehicle position URL configured) |
| `next_service` | Second departure time (HH:MM) |
| `next_departures` | List of upcoming departures (see below) |

The `next_departures` attribute is a list of the next N arrivals (configurable, default 3), each containing:

```yaml
next_departures:
  - departure: '14:30'
    minutes: 5
    latitude: 39.686
    longitude: -104.964
  - departure: '14:45'
    minutes: 20
  - departure: '15:10'
    minutes: 45
```

### Dashboard Examples

**Markdown card showing multiple routes sorted by time:**

```yaml
type: markdown
title: Upcoming Departures
content: |
  {% set ns = namespace(deps=[]) %}
  {% for entity in [
    'sensor.route_1',
    'sensor.route_2',
  ] %}
    {% set name = state_attr(entity, 'friendly_name') %}
    {% for dep in state_attr(entity, 'next_departures') or [] %}
      {% set ns.deps = ns.deps + [{'name': name, 'departure': dep.departure, 'minutes': dep.minutes}] %}
    {% endfor %}
  {% endfor %}
  {% set sorted_deps = ns.deps | sort(attribute='minutes') %}
  | Route | Departs | Min |
  |-------|---------|-----|
  {% for dep in sorted_deps %}
  | {{ dep.name }} | {{ dep.departure }} | {{ dep.minutes }} |
  {% endfor %}
```

## Screenshot

![screenshot](GTFS-RT-V2.JPG)

## Finding Feeds

[The Mobility Database](https://database.mobilitydata.org/) is a good source for realtime GTFS feeds. You can filter the [csv](https://bit.ly/catalogs-csv) on `gtfs-rt` in the `data_type` column and then further by location to find feeds near you.

GTFS providers should also publish a zip file containing static data, including route and stop information. The same CSV file should contain a link to the static ZIP file. For example [Translink SEQ ZIP](https://gtfsrt.api.translink.com.au/GTFS/SEQ_GTFS.zip). The route and stop IDs you need are provided in this file.

## Troubleshooting

1. Enable debug logging:
```yaml
logger:
  default: info
  logs:
    custom_components.gtfs_rt: debug
```
2. Restart Home Assistant
3. Check the logs at **Developer Tools > Logs** or `/<config_dir>/home-assistant.log`
4. File an issue in this GitHub repository with your log output
   * You can paste your log file at [pastebin](https://pastebin.com/) and submit a link
   * Please include details about your setup (Pi, NUC, etc, Docker, HAOS)

A standalone `test.py` script is also provided for testing feeds outside of Home Assistant:

```
test.py -f <yaml file> -d INFO|DEBUG { -l <outfile log file> }
```

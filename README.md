# Veðurstofa Íslands – Home Assistant Integration

Custom Home Assistant integration for weather data from [Veðurstofa Íslands](https://vedur.is) (Icelandic Meteorological Office).

## Features

- **Weather entity** with current conditions, hourly and daily forecasts
- **Observation data** overlaid on forecasts for accurate current readings
- **Weather alerts** from the CAP broker with configurable language (Icelandic / English)
- **Individual sensors** for temperature, wind speed, gusts, humidity, pressure, and more
- Wind speed in **m/s** (native Icelandic reporting)
- Wind chill / feels-like temperature calculation
- Support for **any valid station** — pick from popular stations or enter a custom ID

## Installation

### HACS (recommended)

1. Add this repository as a custom repository in HACS
2. Search for "Veðurstofa Íslands" and install
3. Restart Home Assistant
4. Go to **Settings → Devices & Services → Add Integration → Veðurstofa Íslands**

### Manual

1. Copy the `custom_components/vedur` folder into your Home Assistant `custom_components` directory
2. Restart Home Assistant
3. Go to **Settings → Devices & Services → Add Integration → Veðurstofa Íslands**

## Setup

During setup you can either pick from a list of popular Icelandic stations or enter any valid station ID. Find station IDs at [vedur.is/vedur/stodvar](https://www.vedur.is/vedur/stodvar/).

You also choose the language for weather alerts (Icelandic or English).

## Data Sources

| Data | Source | Update interval |
|------|--------|-----------------|
| Current conditions | Observation API (`type=obs`) | 10 minutes |
| Forecasts | Forecast API (`type=forec`) | 10 minutes |
| Weather alerts | CAP broker API | 10 minutes |

**Note:** The forecast API only provides temperature, wind speed, wind direction, and weather description. Additional fields (humidity, pressure, wind gusts, precipitation, cloud cover) come from the observation endpoint. If a station has no observation data, those sensors will be unavailable.

## Sensors

Enabled by default: Temperature, Feels Like, Wind Speed, Wind Gust, Wind Direction, Precipitation, Cloud Cover, Humidity, Pressure, Active Alerts.

Disabled by default (enable in entity settings): Wind Bearing, Visibility, Condition, Weather Description.

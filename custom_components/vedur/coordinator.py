"""Data update coordinator for Veðurstofa Íslands."""
from __future__ import annotations

import asyncio
import logging
import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    FORECAST_URL,
    OBSERVATION_URL,
    ALERTS_URL,
    UPDATE_INTERVAL,
    WIND_DIRECTION_MAP,
    CONDITION_MAP,
    SEVERITY_MAP,
)

_LOGGER = logging.getLogger(__name__)

# Iceland is UTC year-round (no DST)
_TZ_UTC = timezone.utc

# Wind chill thresholds (JAG/TI formula)
_WIND_CHILL_MAX_TEMP = 10  # °C
_WIND_CHILL_MIN_WIND = 4.8  # km/h


def _wind_chill(temp_c: float | None, wind_mps: float | None) -> float | None:
    """Calculate wind chill using the JAG/TI formula.

    Valid for temps <= 10 °C and wind >= 4.8 km/h.
    """
    if temp_c is None or wind_mps is None:
        return None

    wind_kmh = wind_mps * 3.6
    if temp_c > _WIND_CHILL_MAX_TEMP or wind_kmh < _WIND_CHILL_MIN_WIND:
        return temp_c

    return round(
        13.12
        + 0.6215 * temp_c
        - 11.37 * math.pow(wind_kmh, 0.16)
        + 0.3965 * temp_c * math.pow(wind_kmh, 0.16),
        1,
    )


class VedurDataUpdateCoordinator(DataUpdateCoordinator):
    """Manage fetching Vedur weather data."""

    def __init__(
        self,
        hass: HomeAssistant,
        station_id: str,
        station_name: str,
        alert_language: str = "is",
    ) -> None:
        """Initialize the coordinator."""
        self.station_id = station_id
        self.station_name = station_name
        self.alert_language = alert_language

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{station_id}",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    async def _async_update_data(self) -> dict:
        """Fetch data from Vedur APIs."""
        session = async_get_clientsession(self.hass)

        # Phase 1: Forecast + observations (critical, 20s timeout)
        try:
            async with asyncio.timeout(20):
                data = await self._fetch_weather(session)
        except asyncio.TimeoutError as err:
            raise UpdateFailed(f"Timeout fetching weather data: {err}") from err
        except UpdateFailed:
            raise
        except Exception as err:
            raise UpdateFailed(f"Error fetching weather data: {err}") from err

        # Phase 2: Alerts (non-critical, separate timeout, never fails the update)
        try:
            async with asyncio.timeout(20):
                data["alerts"] = await self._fetch_alerts(session)
        except Exception as err:
            _LOGGER.debug("Could not fetch alerts: %s", err)
            data["alerts"] = self.data.get("alerts", []) if self.data else []

        return data

    async def _fetch_weather(self, session) -> dict:
        """Fetch forecast and observations concurrently."""
        forecast_url = FORECAST_URL.format(station_id=self.station_id)
        observation_url = OBSERVATION_URL.format(station_id=self.station_id)

        forecast_xml, observation_xml = await asyncio.gather(
            self._fetch_xml(session, forecast_url),
            self._fetch_xml(session, observation_url),
            return_exceptions=True,
        )

        # Forecast is required
        if isinstance(forecast_xml, Exception):
            raise UpdateFailed(f"Failed to fetch forecast: {forecast_xml}")

        data = self._parse_forecast(forecast_xml)

        # Overlay observation data if available (actual measurements > forecast)
        if isinstance(observation_xml, str):
            self._apply_observations(data, observation_xml)

        return data

    async def _fetch_xml(self, session, url: str) -> str:
        """Fetch an XML endpoint and return raw text."""
        async with session.get(url) as response:
            if response.status != 200:
                raise UpdateFailed(f"API returned {response.status} for {url}")
            return await response.text()

    # ------------------------------------------------------------------
    # Forecast parsing
    # ------------------------------------------------------------------

    def _parse_forecast(self, xml_text: str) -> dict:
        """Parse the forecast XML into a data dict."""
        root = self._parse_xml_root(xml_text)
        station = root.find(".//station")
        if station is None:
            raise UpdateFailed("No station data found in response")

        forecasts = station.findall(".//forecast")
        if not forecasts:
            raise UpdateFailed("No forecast data found")

        # First forecast entry = next forecast period (not current observation)
        current = forecasts[0]
        temp = self._float(current, "T")
        wind = self._float(current, "F")

        data = {
            "station_name": self.station_name,
            "station_id": self.station_id,
            "temperature": temp,
            "wind_speed": wind,
            "wind_gust": self._float(current, "FG"),
            "wind_direction": self._text(current, "D"),
            "wind_bearing": self._wind_bearing(current),
            "condition_text": self._text(current, "W"),
            "condition": self._map_condition(self._text(current, "W")),
            "forecast_time": self._text(current, "ftime"),
            "precipitation": self._float(current, "R"),
            "cloud_cover": self._float(current, "N"),
            "dew_point": self._float(current, "TD"),
            "humidity": self._float(current, "RH"),
            "pressure": self._float(current, "P"),
            "visibility": self._float(current, "V"),
            "feels_like": _wind_chill(temp, wind),
            "alerts": [],
        }

        hourly = self._parse_hourly(forecasts)
        data["forecast_hourly"] = hourly
        data["forecast_daily"] = self._aggregate_daily(hourly)

        return data

    def _parse_hourly(self, forecasts: list) -> list[dict]:
        """Parse forecast entries into hourly forecast list."""
        hourly = []
        for fc in forecasts:
            ftime = self._text(fc, "ftime")
            if not ftime:
                continue
            try:
                dt = datetime.strptime(ftime, "%Y-%m-%d %H:%M:%S").replace(
                    tzinfo=_TZ_UTC
                )
            except ValueError:
                continue

            temp = self._float(fc, "T")
            wind = self._float(fc, "F")

            entry: dict = {
                "datetime": dt.isoformat(),
                "temperature": temp,
                "condition": self._map_condition(self._text(fc, "W")),
                "wind_speed": wind,
                "wind_bearing": self._wind_bearing(fc),
                "apparent_temperature": _wind_chill(temp, wind),
            }

            # Only include optional fields if the API actually returns them
            for key, tag in (
                ("wind_gust", "FG"),
                ("precipitation", "R"),
                ("cloud_coverage", "N"),
                ("humidity", "RH"),
            ):
                val = self._float(fc, tag)
                if val is not None:
                    entry[key] = val

            hourly.append(entry)
        return hourly

    def _aggregate_daily(self, hourly: list[dict]) -> list[dict]:
        """Aggregate hourly forecasts into daily summaries."""
        if not hourly:
            return []

        by_date: dict[str, list[dict]] = defaultdict(list)
        for entry in hourly:
            try:
                dt = datetime.fromisoformat(entry["datetime"])
                by_date[dt.date().isoformat()].append(entry)
            except (ValueError, KeyError):
                continue

        daily = []
        for date_str in sorted(by_date):
            entries = by_date[date_str]
            temps = [e["temperature"] for e in entries if e["temperature"] is not None]
            winds = [e["wind_speed"] for e in entries if e["wind_speed"] is not None]
            gusts = [e["wind_gust"] for e in entries if e.get("wind_gust") is not None]
            precips = [e["precipitation"] for e in entries if e.get("precipitation") is not None]
            conditions = [e["condition"] for e in entries if e["condition"]]

            entry: dict = {
                "datetime": f"{date_str}T00:00:00+00:00",
                "temperature": max(temps) if temps else None,
                "templow": min(temps) if temps else None,
                "condition": max(set(conditions), key=conditions.count) if conditions else None,
            }

            if winds:
                entry["wind_speed"] = round(sum(winds) / len(winds), 1)
            if gusts:
                entry["wind_gust"] = max(gusts)
            if precips:
                entry["precipitation"] = round(sum(precips), 1)

            daily.append(entry)
        return daily

    # ------------------------------------------------------------------
    # Observation overlay
    # ------------------------------------------------------------------

    def _apply_observations(self, data: dict, xml_text: str) -> None:
        """Overlay observation values onto the data dict.

        Observations are actual measurements and more accurate than forecasts
        for current conditions.
        """
        try:
            root = self._parse_xml_root(xml_text)
        except UpdateFailed:
            return

        station = root.find(".//station")
        if station is None:
            return

        # Numeric observation fields
        obs_map = {
            "temperature": "T",
            "wind_speed": "F",
            "wind_gust": "FG",
            "humidity": "RH",
            "pressure": "P",
            "dew_point": "TD",
            "precipitation": "R",
            "cloud_cover": "N",
            "visibility": "V",
        }

        for key, tag in obs_map.items():
            val = self._float(station, tag)
            if val is not None:
                data[key] = val

        # Wind direction
        obs_dir = self._text(station, "D")
        if obs_dir:
            data["wind_direction"] = obs_dir
            bearing = WIND_DIRECTION_MAP.get(obs_dir.upper())
            if bearing is not None:
                data["wind_bearing"] = bearing

        # Weather condition from observation
        obs_weather = self._text(station, "W")
        if obs_weather:
            data["condition_text"] = obs_weather
            data["condition"] = self._map_condition(obs_weather)

        # Recalculate feels_like with observed values
        data["feels_like"] = _wind_chill(data.get("temperature"), data.get("wind_speed"))

        # Observation time
        obs_time = self._text(station, "time")
        if obs_time:
            data["observation_time"] = obs_time

    # ------------------------------------------------------------------
    # Alerts (CAP)
    # ------------------------------------------------------------------

    async def _fetch_alerts(self, session) -> list[dict]:
        """Fetch weather alerts from the CAP broker."""
        async with session.get(ALERTS_URL) as response:
            if response.status != 200:
                return []
            content = await response.text()

        links = self._parse_alert_feed(content)
        if not links:
            return []

        # Fetch individual alerts in parallel (max 10)
        tasks = [self._fetch_cap_alert(session, link) for link in links[:10]]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        alerts = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                _LOGGER.debug("Error fetching CAP alert %s: %s", links[i], result)
            elif result is not None:
                alerts.append(result)
        return alerts

    def _parse_alert_feed(self, content: str) -> list[str]:
        """Extract CAP XML links from the Atom/RSS feed."""
        links = []
        try:
            root = ElementTree.fromstring(content)
        except ElementTree.ParseError as err:
            _LOGGER.debug("Failed to parse alert feed: %s", err)
            return links

        atom_ns = "{http://www.w3.org/2005/Atom}"

        entries = (
            root.findall(f".//{atom_ns}entry")
            or root.findall(".//entry")
            or root.findall(".//item")
        )

        for entry in entries:
            link = self._extract_link(entry, atom_ns)
            if link:
                links.append(link)
        return links

    @staticmethod
    def _extract_link(entry: ElementTree.Element, atom_ns: str) -> str | None:
        """Extract the best link from a feed entry."""
        link_elems = entry.findall(f"{atom_ns}link") or entry.findall("link")
        fallback = None

        for elem in link_elems:
            href = elem.get("href", "")
            if href and ("xml" in elem.get("type", "") or href.endswith("/xml/")):
                return href
            if href and fallback is None:
                fallback = href

        # RSS <link> text node
        if fallback is None:
            link_elem = entry.find("link")
            if link_elem is not None and link_elem.text:
                fallback = link_elem.text.strip()
        return fallback

    async def _fetch_cap_alert(self, session, url: str) -> dict | None:
        """Fetch and parse a single CAP alert XML."""
        async with asyncio.timeout(10):
            async with session.get(url) as response:
                if response.status != 200:
                    return None
                content = await response.text()
        return self._parse_cap_xml(content, url)

    def _parse_cap_xml(self, content: str, source_url: str) -> dict | None:
        """Parse a CAP XML alert, selecting the preferred language."""
        try:
            root = ElementTree.fromstring(content)
        except ElementTree.ParseError as err:
            _LOGGER.debug("Failed to parse CAP XML: %s", err)
            return None

        cap_ns = "{urn:oasis:names:tc:emergency:cap:1.2}"
        alert_elem = root
        if root.tag not in (f"{cap_ns}alert", "alert"):
            alert_elem = root.find(f".//{cap_ns}alert") or root.find(".//alert")
        if alert_elem is None:
            return None

        info_blocks = alert_elem.findall(f"{cap_ns}info") or alert_elem.findall("info")
        if not info_blocks:
            return None

        info = self._select_info_block(info_blocks, cap_ns)
        if info is None:
            return None

        def txt(parent, tag):
            elem = parent.find(f"{cap_ns}{tag}") or parent.find(tag)
            return elem.text.strip() if elem is not None and elem.text else None

        raw_severity = (txt(info, "severity") or "").lower()

        alert = {
            "event": txt(info, "event"),
            "severity": txt(info, "severity"),
            "severity_color": SEVERITY_MAP.get(raw_severity, "unknown"),
            "onset": txt(info, "onset"),
            "expires": txt(info, "expires"),
            "headline": txt(info, "headline"),
            "description": txt(info, "description"),
            "urgency": txt(info, "urgency"),
            "certainty": txt(info, "certainty"),
            "link": source_url,
        }

        area_elem = info.find(f"{cap_ns}area") or info.find("area")
        if area_elem is not None:
            alert["areaDesc"] = txt(area_elem, "areaDesc")

        ident = alert_elem.find(f"{cap_ns}identifier") or alert_elem.find("identifier")
        if ident is not None and ident.text:
            alert["identifier"] = ident.text.strip()

        return alert

    def _select_info_block(
        self, info_blocks: list[ElementTree.Element], cap_ns: str
    ) -> ElementTree.Element | None:
        """Select the info block matching the preferred language."""
        fallback = None
        for info in info_blocks:
            lang_elem = info.find(f"{cap_ns}language") or info.find("language")
            lang = (
                lang_elem.text.strip().lower()
                if lang_elem is not None and lang_elem.text
                else ""
            )
            if lang.startswith(self.alert_language):
                return info
            if fallback is None:
                fallback = info
        return fallback

    # ------------------------------------------------------------------
    # XML helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_xml_root(xml_text: str) -> ElementTree.Element:
        """Parse XML text and return root element."""
        try:
            return ElementTree.fromstring(xml_text)
        except ElementTree.ParseError as err:
            raise UpdateFailed(f"Failed to parse XML: {err}") from err

    @staticmethod
    def _text(element: ElementTree.Element, tag: str) -> str | None:
        """Get text content of a child element."""
        child = element.find(tag)
        return child.text.strip() if child is not None and child.text else None

    @staticmethod
    def _float(element: ElementTree.Element, tag: str) -> float | None:
        """Get float value from a child element."""
        child = element.find(tag)
        if child is not None and child.text:
            try:
                return float(child.text.strip())
            except ValueError:
                return None
        return None

    def _wind_bearing(self, element: ElementTree.Element) -> float | None:
        """Convert wind direction text to bearing in degrees."""
        direction = self._text(element, "D")
        if direction:
            return WIND_DIRECTION_MAP.get(direction.upper())
        return None

    @staticmethod
    def _map_condition(text: str | None) -> str:
        """Map weather description to HA condition key."""
        if not text:
            return "cloudy"
        lower = text.lower()
        for key, value in CONDITION_MAP.items():
            if key in lower:
                return value
        return "cloudy"

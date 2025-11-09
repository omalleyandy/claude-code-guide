"""
AccuWeather API Client

Fetches weather forecasts for game locations.
Implements rate limiting, retry logic, and error handling.
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class AccuWeatherClient:
    """Client for fetching weather data from AccuWeather API."""

    BASE_URL = "http://dataservice.accuweather.com"

    def __init__(
        self,
        api_key: str | None = None,
        rate_limit_delay: float = 1.0,
        timeout: float = 30.0,
    ):
        """
        Initialize AccuWeather API client.

        Args:
            api_key: AccuWeather API key (defaults to ACCUWEATHER_API_KEY env var)
            rate_limit_delay: Delay between requests in seconds
            timeout: Request timeout in seconds
        """
        self.api_key = api_key or os.getenv("ACCUWEATHER_API_KEY")
        self.rate_limit_delay = rate_limit_delay
        self.timeout = timeout
        self.last_request_time: float = 0.0
        self._client: httpx.AsyncClient | None = None

        if not self.api_key:
            raise ValueError(
                "ACCUWEATHER_API_KEY must be set "
                "either as argument or environment variable"
            )

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def connect(self) -> None:
        """Initialize HTTP client."""
        logger.info("Initializing AccuWeather API client")
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=self.timeout,
            headers={
                "User-Agent": "BillyWaltersSportsAnalyzer/1.0",
                "Accept": "application/json",
            },
        )
        logger.info("AccuWeather client initialized")

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
        logger.info("Closed AccuWeather client")

    async def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        current_time = asyncio.get_event_loop().time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.rate_limit_delay:
            wait_time = self.rate_limit_delay - time_since_last
            logger.debug(f"Rate limiting: waiting {wait_time:.2f}s")
            await asyncio.sleep(wait_time)

        self.last_request_time = asyncio.get_event_loop().time()

    async def _make_request(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        max_retries: int = 3,
    ) -> dict[str, Any] | list[Any]:
        """
        Make HTTP request with retry logic.

        Args:
            endpoint: API endpoint
            params: Query parameters
            max_retries: Maximum retry attempts

        Returns:
            Response JSON data

        Raises:
            RuntimeError: If request fails after all retries
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Call connect() first.")

        await self._rate_limit()

        # Add API key to params
        if params is None:
            params = {}
        params["apikey"] = self.api_key

        for attempt in range(max_retries):
            try:
                logger.debug(
                    f"GET {endpoint} (attempt {attempt + 1}/{max_retries})"
                )

                response = await self._client.get(endpoint, params=params)
                response.raise_for_status()

                return response.json()

            except httpx.HTTPStatusError as e:
                logger.warning(
                    f"HTTP error {e.response.status_code}: {e.response.text}"
                )

                # Don't retry client errors (4xx)
                if 400 <= e.response.status_code < 500:
                    raise RuntimeError(
                        f"Client error {e.response.status_code}: "
                        f"{e.response.text}"
                    ) from e

                # Retry server errors (5xx)
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.info(f"Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    raise RuntimeError(
                        f"Request failed after {max_retries} attempts"
                    ) from e

            except httpx.RequestError as e:
                logger.warning(f"Request error: {e}")

                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.info(f"Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    raise RuntimeError(
                        f"Request failed after {max_retries} attempts: {e}"
                    ) from e

        raise RuntimeError("Unexpected error in _make_request")

    async def get_location_key(
        self, city: str, state: str, max_retries: int = 3
    ) -> str:
        """
        Get AccuWeather location key for a city.

        Args:
            city: City name
            state: State abbreviation
            max_retries: Maximum retry attempts

        Returns:
            Location key string

        Raises:
            RuntimeError: If location not found or request fails
        """
        logger.info(f"Getting location key for {city}, {state}")

        # Search for location
        query = f"{city}, {state}"
        data = await self._make_request(
            "/locations/v1/cities/US/search",
            params={"q": query},
            max_retries=max_retries,
        )

        if not data or not isinstance(data, list):
            raise RuntimeError(f"No location found for {query}")

        # Get first result
        location = data[0]
        location_key = location.get("Key")

        if not location_key:
            raise RuntimeError(f"No location key in response for {query}")

        logger.info(f"Location key for {city}, {state}: {location_key}")
        return location_key

    async def get_current_conditions(
        self, location_key: str, max_retries: int = 3
    ) -> dict[str, Any]:
        """
        Get current weather conditions for a location.

        Args:
            location_key: AccuWeather location key
            max_retries: Maximum retry attempts

        Returns:
            Current conditions dictionary

        Raises:
            RuntimeError: If request fails
        """
        logger.info(f"Getting current conditions for location {location_key}")

        data = await self._make_request(
            f"/currentconditions/v1/{location_key}",
            params={"details": "true"},
            max_retries=max_retries,
        )

        if not data or not isinstance(data, list):
            raise RuntimeError("Invalid response from current conditions API")

        conditions = data[0]
        logger.info(f"Fetched current conditions for {location_key}")

        return self._format_conditions(conditions)

    async def get_hourly_forecast(
        self,
        location_key: str,
        hours: int = 12,
        max_retries: int = 3,
    ) -> list[dict[str, Any]]:
        """
        Get hourly weather forecast for a location.

        Args:
            location_key: AccuWeather location key
            hours: Number of hours to forecast (1, 12, 24, 72, 120)
            max_retries: Maximum retry attempts

        Returns:
            List of hourly forecast dictionaries

        Raises:
            RuntimeError: If request fails
        """
        # Map hours to API endpoint
        if hours <= 12:
            endpoint = f"/forecasts/v1/hourly/12hour/{location_key}"
        elif hours <= 24:
            endpoint = f"/forecasts/v1/hourly/24hour/{location_key}"
        elif hours <= 72:
            endpoint = f"/forecasts/v1/hourly/72hour/{location_key}"
        else:
            endpoint = f"/forecasts/v1/hourly/120hour/{location_key}"

        logger.info(
            f"Getting {hours}h forecast for location {location_key}"
        )

        data = await self._make_request(
            endpoint, params={"details": "true"}, max_retries=max_retries
        )

        if not isinstance(data, list):
            raise RuntimeError("Invalid response from hourly forecast API")

        logger.info(f"Fetched {len(data)} hourly forecasts")

        # Format and return
        forecasts = [self._format_hourly(hour) for hour in data]
        return forecasts[:hours]  # Return only requested hours

    def _format_conditions(
        self, conditions: dict[str, Any]
    ) -> dict[str, Any]:
        """Format current conditions data."""
        temp = conditions.get("Temperature", {}).get("Imperial", {})
        wind = conditions.get("Wind", {})
        wind_speed = wind.get("Speed", {}).get("Imperial", {})

        return {
            "temperature_f": temp.get("Value"),
            "weather_text": conditions.get("WeatherText"),
            "has_precipitation": conditions.get("HasPrecipitation", False),
            "precipitation_type": conditions.get("PrecipitationType"),
            "wind_speed_mph": wind_speed.get("Value"),
            "wind_direction": wind.get("Direction", {}).get("English"),
            "humidity": conditions.get("RelativeHumidity"),
            "uv_index": conditions.get("UVIndex"),
            "visibility_mi": conditions.get("Visibility", {})
            .get("Imperial", {})
            .get("Value"),
            "timestamp": conditions.get("LocalObservationDateTime"),
            "source": "accuweather",
        }

    def _format_hourly(self, hourly: dict[str, Any]) -> dict[str, Any]:
        """Format hourly forecast data."""
        temp = hourly.get("Temperature", {})
        wind = hourly.get("Wind", {})
        wind_speed = wind.get("Speed", {})

        return {
            "forecast_time": hourly.get("DateTime"),
            "temperature_f": temp.get("Value"),
            "weather_text": hourly.get("IconPhrase"),
            "has_precipitation": hourly.get("HasPrecipitation", False),
            "precipitation_type": hourly.get("PrecipitationType"),
            "precipitation_probability": hourly.get(
                "PrecipitationProbability"
            ),
            "wind_speed_mph": wind_speed.get("Value"),
            "wind_direction": wind.get("Direction", {}).get("English"),
            "humidity": hourly.get("RelativeHumidity"),
            "uv_index": hourly.get("UVIndex"),
            "source": "accuweather",
        }

    async def get_game_forecast(
        self,
        city: str,
        state: str,
        game_time: datetime,
        max_retries: int = 3,
    ) -> dict[str, Any]:
        """
        Get weather forecast for a specific game time.

        Args:
            city: Stadium city
            state: Stadium state
            game_time: Game start time
            max_retries: Maximum retry attempts

        Returns:
            Weather forecast dictionary

        Raises:
            RuntimeError: If request fails
        """
        logger.info(
            f"Getting game forecast for {city}, {state} at {game_time}"
        )

        # Get location key
        location_key = await self.get_location_key(
            city, state, max_retries=max_retries
        )

        # Get hourly forecast
        hours_ahead = int((game_time - datetime.now()).total_seconds() / 3600)

        if hours_ahead < 0:
            # Game in the past - get current conditions
            logger.warning("Game time is in the past, getting current conditions")
            return await self.get_current_conditions(
                location_key, max_retries=max_retries
            )

        # Get hourly forecast
        forecasts = await self.get_hourly_forecast(
            location_key, hours=min(hours_ahead + 1, 120), max_retries=max_retries
        )

        # Find closest forecast to game time
        closest_forecast = min(
            forecasts,
            key=lambda f: abs(
                datetime.fromisoformat(
                    f["forecast_time"].replace("Z", "+00:00")
                )
                - game_time
            ),
        )

        logger.info(f"Found forecast for game time: {closest_forecast['forecast_time']}")
        return closest_forecast


# Example usage
async def main():
    """Example usage of AccuWeatherClient."""
    async with AccuWeatherClient() as client:
        # Get location key
        location_key = await client.get_location_key("Kansas City", "MO")
        print(f"\nLocation key for Kansas City, MO: {location_key}")

        # Get current conditions
        conditions = await client.get_current_conditions(location_key)
        print(f"\nCurrent conditions:")
        print(f"  Temperature: {conditions['temperature_f']}°F")
        print(f"  Weather: {conditions['weather_text']}")
        print(f"  Wind: {conditions['wind_speed_mph']} mph {conditions['wind_direction']}")
        print(f"  Humidity: {conditions['humidity']}%")

        # Get game forecast
        game_time = datetime.now().replace(hour=13, minute=0, second=0)
        forecast = await client.get_game_forecast(
            "Kansas City", "MO", game_time
        )
        print(f"\nGame forecast for {game_time}:")
        print(f"  Temperature: {forecast['temperature_f']}°F")
        print(f"  Weather: {forecast['weather_text']}")
        print(f"  Precipitation: {forecast['precipitation_probability']}%")


if __name__ == "__main__":
    asyncio.run(main())

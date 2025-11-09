"""
OpenWeather API Client

Fetches weather forecasts for game locations using OpenWeatherMap API.
Implements rate limiting, retry logic, and error handling.
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class OpenWeatherClient:
    """Client for fetching weather data from OpenWeatherMap API."""

    BASE_URL = "https://api.openweathermap.org/data/2.5"

    def __init__(
        self,
        api_key: str | None = None,
        rate_limit_delay: float = 1.0,
        timeout: float = 30.0,
    ):
        """
        Initialize OpenWeather API client.

        Args:
            api_key: OpenWeather API key (defaults to OPENWEATHER_API_KEY env var)
            rate_limit_delay: Delay between requests in seconds
            timeout: Request timeout in seconds
        """
        self.api_key = api_key or os.getenv("OPENWEATHER_API_KEY")
        self.rate_limit_delay = rate_limit_delay
        self.timeout = timeout
        self.last_request_time: float = 0.0
        self._client: httpx.AsyncClient | None = None

        if not self.api_key:
            raise ValueError(
                "OPENWEATHER_API_KEY must be set "
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
        logger.info("Initializing OpenWeather API client")
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=self.timeout,
            headers={
                "User-Agent": "BillyWaltersSportsAnalyzer/1.0",
                "Accept": "application/json",
            },
        )
        logger.info("OpenWeather client initialized")

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
        logger.info("Closed OpenWeather client")

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
    ) -> dict[str, Any]:
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
        params["appid"] = self.api_key
        params["units"] = "imperial"  # Fahrenheit, mph

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

    async def get_current_weather(
        self, city: str, state: str, max_retries: int = 3
    ) -> dict[str, Any]:
        """
        Get current weather for a city.

        Args:
            city: City name
            state: State abbreviation
            max_retries: Maximum retry attempts

        Returns:
            Current weather dictionary

        Raises:
            RuntimeError: If request fails
        """
        logger.info(f"Getting current weather for {city}, {state}")

        query = f"{city},{state},US"
        data = await self._make_request(
            "/weather", params={"q": query}, max_retries=max_retries
        )

        logger.info(f"Fetched current weather for {city}, {state}")
        return self._format_current_weather(data)

    async def get_forecast(
        self, city: str, state: str, max_retries: int = 3
    ) -> list[dict[str, Any]]:
        """
        Get 5-day / 3-hour forecast for a city.

        Args:
            city: City name
            state: State abbreviation
            max_retries: Maximum retry attempts

        Returns:
            List of forecast dictionaries (3-hour intervals)

        Raises:
            RuntimeError: If request fails
        """
        logger.info(f"Getting forecast for {city}, {state}")

        query = f"{city},{state},US"
        data = await self._make_request(
            "/forecast", params={"q": query}, max_retries=max_retries
        )

        forecast_list = data.get("list", [])
        logger.info(f"Fetched {len(forecast_list)} forecast periods")

        return [self._format_forecast(item) for item in forecast_list]

    def _format_current_weather(
        self, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Format current weather data."""
        main = data.get("main", {})
        wind = data.get("wind", {})
        weather = data.get("weather", [{}])[0]
        clouds = data.get("clouds", {})
        rain = data.get("rain", {})
        snow = data.get("snow", {})

        # Determine precipitation type
        precipitation_type = None
        if rain.get("1h", 0) > 0:
            precipitation_type = "rain"
        elif snow.get("1h", 0) > 0:
            precipitation_type = "snow"

        return {
            "temperature_f": main.get("temp"),
            "feels_like_f": main.get("feels_like"),
            "humidity": main.get("humidity"),
            "pressure": main.get("pressure"),
            "weather_text": weather.get("description"),
            "conditions": weather.get("main"),
            "wind_speed_mph": wind.get("speed"),
            "wind_direction_deg": wind.get("deg"),
            "wind_gust_mph": wind.get("gust"),
            "clouds_percent": clouds.get("all"),
            "precipitation_type": precipitation_type,
            "rain_1h": rain.get("1h", 0),
            "snow_1h": snow.get("1h", 0),
            "visibility_m": data.get("visibility"),
            "timestamp": datetime.fromtimestamp(
                data.get("dt", 0)
            ).isoformat(),
            "source": "openweather",
        }

    def _format_forecast(self, data: dict[str, Any]) -> dict[str, Any]:
        """Format forecast data."""
        main = data.get("main", {})
        wind = data.get("wind", {})
        weather = data.get("weather", [{}])[0]
        clouds = data.get("clouds", {})
        rain = data.get("rain", {})
        snow = data.get("snow", {})
        pop = data.get("pop", 0)  # Probability of precipitation

        # Determine precipitation type
        precipitation_type = None
        if rain.get("3h", 0) > 0:
            precipitation_type = "rain"
        elif snow.get("3h", 0) > 0:
            precipitation_type = "snow"

        return {
            "forecast_time": datetime.fromtimestamp(
                data.get("dt", 0)
            ).isoformat(),
            "temperature_f": main.get("temp"),
            "feels_like_f": main.get("feels_like"),
            "humidity": main.get("humidity"),
            "pressure": main.get("pressure"),
            "weather_text": weather.get("description"),
            "conditions": weather.get("main"),
            "wind_speed_mph": wind.get("speed"),
            "wind_direction_deg": wind.get("deg"),
            "wind_gust_mph": wind.get("gust"),
            "clouds_percent": clouds.get("all"),
            "precipitation_chance": pop * 100,  # Convert to percentage
            "precipitation_type": precipitation_type,
            "rain_3h": rain.get("3h", 0),
            "snow_3h": snow.get("3h", 0),
            "visibility_m": data.get("visibility"),
            "source": "openweather",
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

        # Check if game is in the past or very near future
        hours_ahead = (game_time - datetime.now()).total_seconds() / 3600

        if hours_ahead < 0:
            # Game in the past - get current weather
            logger.warning("Game time is in the past, getting current weather")
            return await self.get_current_weather(
                city, state, max_retries=max_retries
            )

        # Get forecast
        forecasts = await self.get_forecast(
            city, state, max_retries=max_retries
        )

        if not forecasts:
            raise RuntimeError("No forecast data available")

        # Find closest forecast to game time
        closest_forecast = min(
            forecasts,
            key=lambda f: abs(
                datetime.fromisoformat(f["forecast_time"]) - game_time
            ),
        )

        logger.info(
            f"Found forecast for game time: {closest_forecast['forecast_time']}"
        )
        return closest_forecast

    def wind_direction_text(self, degrees: float | None) -> str:
        """Convert wind direction degrees to cardinal direction."""
        if degrees is None:
            return "Unknown"

        directions = [
            "N",
            "NNE",
            "NE",
            "ENE",
            "E",
            "ESE",
            "SE",
            "SSE",
            "S",
            "SSW",
            "SW",
            "WSW",
            "W",
            "WNW",
            "NW",
            "NNW",
        ]
        index = int((degrees + 11.25) / 22.5) % 16
        return directions[index]


# Example usage
async def main():
    """Example usage of OpenWeatherClient."""
    async with OpenWeatherClient() as client:
        # Get current weather
        current = await client.get_current_weather("Kansas City", "MO")
        print(f"\nCurrent weather in Kansas City, MO:")
        print(f"  Temperature: {current['temperature_f']}°F")
        print(f"  Feels like: {current['feels_like_f']}°F")
        print(f"  Weather: {current['weather_text']}")
        print(f"  Wind: {current['wind_speed_mph']} mph")
        print(f"  Humidity: {current['humidity']}%")

        # Get game forecast
        game_time = datetime.now().replace(hour=13, minute=0, second=0)
        forecast = await client.get_game_forecast(
            "Kansas City", "MO", game_time
        )
        print(f"\nGame forecast for {game_time}:")
        print(f"  Temperature: {forecast['temperature_f']}°F")
        print(f"  Weather: {forecast['weather_text']}")
        print(f"  Precipitation chance: {forecast['precipitation_chance']}%")
        print(f"  Wind: {forecast['wind_speed_mph']} mph")

        # Convert wind direction
        wind_dir = client.wind_direction_text(
            forecast.get("wind_direction_deg")
        )
        print(f"  Wind direction: {wind_dir}")


if __name__ == "__main__":
    asyncio.run(main())

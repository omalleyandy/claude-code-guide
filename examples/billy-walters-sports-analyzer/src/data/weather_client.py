"""
Unified Weather Client

Combines AccuWeather and OpenWeather clients with fallback logic and validation.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any

from .accuweather_client import AccuWeatherClient
from .openweather_client import OpenWeatherClient

logger = logging.getLogger(__name__)


class WeatherClient:
    """
    Unified weather client with fallback support.

    Tries AccuWeather first, falls back to OpenWeather if needed.
    """

    def __init__(
        self,
        accuweather_api_key: str | None = None,
        openweather_api_key: str | None = None,
        prefer_accuweather: bool = True,
    ):
        """
        Initialize unified weather client.

        Args:
            accuweather_api_key: AccuWeather API key
            openweather_api_key: OpenWeather API key
            prefer_accuweather: If True, try AccuWeather first
        """
        self.prefer_accuweather = prefer_accuweather
        self._accuweather_client: AccuWeatherClient | None = None
        self._openweather_client: OpenWeatherClient | None = None

        # Initialize clients if API keys provided
        try:
            self._accuweather_client = AccuWeatherClient(
                api_key=accuweather_api_key
            )
            logger.info("AccuWeather client initialized")
        except ValueError:
            logger.warning("AccuWeather API key not available")

        try:
            self._openweather_client = OpenWeatherClient(
                api_key=openweather_api_key
            )
            logger.info("OpenWeather client initialized")
        except ValueError:
            logger.warning("OpenWeather API key not available")

        if not self._accuweather_client and not self._openweather_client:
            raise ValueError(
                "At least one weather API key must be provided "
                "(ACCUWEATHER_API_KEY or OPENWEATHER_API_KEY)"
            )

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def connect(self) -> None:
        """Connect all available clients."""
        tasks = []

        if self._accuweather_client:
            tasks.append(self._accuweather_client.connect())

        if self._openweather_client:
            tasks.append(self._openweather_client.connect())

        await asyncio.gather(*tasks)
        logger.info("Weather clients connected")

    async def close(self) -> None:
        """Close all clients."""
        tasks = []

        if self._accuweather_client:
            tasks.append(self._accuweather_client.close())

        if self._openweather_client:
            tasks.append(self._openweather_client.close())

        await asyncio.gather(*tasks)
        logger.info("Weather clients closed")

    async def get_game_forecast(
        self,
        city: str,
        state: str,
        game_time: datetime,
        max_retries: int = 3,
    ) -> dict[str, Any]:
        """
        Get weather forecast for a game with automatic fallback.

        Tries preferred service first, falls back to alternative if needed.

        Args:
            city: Stadium city
            state: Stadium state
            game_time: Game start time
            max_retries: Maximum retry attempts per service

        Returns:
            Weather forecast dictionary

        Raises:
            RuntimeError: If both services fail
        """
        logger.info(
            f"Getting game forecast for {city}, {state} at {game_time}"
        )

        # Determine order to try services
        if self.prefer_accuweather:
            primary = self._accuweather_client
            secondary = self._openweather_client
            primary_name = "AccuWeather"
            secondary_name = "OpenWeather"
        else:
            primary = self._openweather_client
            secondary = self._accuweather_client
            primary_name = "OpenWeather"
            secondary_name = "AccuWeather"

        # Try primary service
        if primary:
            try:
                logger.info(f"Trying {primary_name}...")
                forecast = await primary.get_game_forecast(
                    city, state, game_time, max_retries=max_retries
                )
                logger.info(f"Successfully fetched forecast from {primary_name}")
                return forecast
            except Exception as e:
                logger.warning(
                    f"{primary_name} failed: {e}, trying fallback"
                )

        # Try secondary service
        if secondary:
            try:
                logger.info(f"Trying {secondary_name}...")
                forecast = await secondary.get_game_forecast(
                    city, state, game_time, max_retries=max_retries
                )
                logger.info(
                    f"Successfully fetched forecast from {secondary_name}"
                )
                return forecast
            except Exception as e:
                logger.error(f"{secondary_name} failed: {e}")
                raise RuntimeError(
                    f"Both weather services failed. {primary_name}: {e}"
                ) from e

        # No services available
        raise RuntimeError("No weather services available")

    async def get_current_weather(
        self, city: str, state: str, max_retries: int = 3
    ) -> dict[str, Any]:
        """
        Get current weather with automatic fallback.

        Args:
            city: City name
            state: State abbreviation
            max_retries: Maximum retry attempts per service

        Returns:
            Current weather dictionary

        Raises:
            RuntimeError: If both services fail
        """
        logger.info(f"Getting current weather for {city}, {state}")

        # Try AccuWeather first
        if self._accuweather_client:
            try:
                logger.info("Trying AccuWeather...")
                location_key = await self._accuweather_client.get_location_key(
                    city, state, max_retries=max_retries
                )
                weather = (
                    await self._accuweather_client.get_current_conditions(
                        location_key, max_retries=max_retries
                    )
                )
                logger.info("Successfully fetched from AccuWeather")
                return weather
            except Exception as e:
                logger.warning(f"AccuWeather failed: {e}, trying OpenWeather")

        # Try OpenWeather as fallback
        if self._openweather_client:
            try:
                logger.info("Trying OpenWeather...")
                weather = await self._openweather_client.get_current_weather(
                    city, state, max_retries=max_retries
                )
                logger.info("Successfully fetched from OpenWeather")
                return weather
            except Exception as e:
                logger.error(f"OpenWeather failed: {e}")
                raise RuntimeError(
                    "Both weather services failed"
                ) from e

        raise RuntimeError("No weather services available")

    def normalize_weather_data(
        self, weather: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Normalize weather data from different sources to common format.

        Args:
            weather: Weather data from any source

        Returns:
            Normalized weather dictionary
        """
        source = weather.get("source")

        if source == "accuweather":
            return self._normalize_accuweather(weather)
        elif source == "openweather":
            return self._normalize_openweather(weather)
        else:
            logger.warning(f"Unknown weather source: {source}")
            return weather

    def _normalize_accuweather(
        self, weather: dict[str, Any]
    ) -> dict[str, Any]:
        """Normalize AccuWeather data."""
        return {
            "temperature_f": weather.get("temperature_f"),
            "weather_text": weather.get("weather_text"),
            "wind_speed_mph": weather.get("wind_speed_mph"),
            "wind_direction": weather.get("wind_direction"),
            "humidity": weather.get("humidity"),
            "precipitation_chance": weather.get(
                "precipitation_probability"
            ),
            "precipitation_type": weather.get("precipitation_type"),
            "forecast_time": weather.get("forecast_time")
            or weather.get("timestamp"),
            "source": "accuweather",
        }

    def _normalize_openweather(
        self, weather: dict[str, Any]
    ) -> dict[str, Any]:
        """Normalize OpenWeather data."""
        # Convert wind direction from degrees to text if needed
        wind_dir_deg = weather.get("wind_direction_deg")
        wind_direction = None
        if wind_dir_deg is not None and self._openweather_client:
            wind_direction = self._openweather_client.wind_direction_text(
                wind_dir_deg
            )

        return {
            "temperature_f": weather.get("temperature_f"),
            "weather_text": weather.get("weather_text"),
            "wind_speed_mph": weather.get("wind_speed_mph"),
            "wind_direction": wind_direction,
            "humidity": weather.get("humidity"),
            "precipitation_chance": weather.get("precipitation_chance"),
            "precipitation_type": weather.get("precipitation_type"),
            "forecast_time": weather.get("forecast_time")
            or weather.get("timestamp"),
            "source": "openweather",
        }


# Example usage
async def main():
    """Example usage of unified WeatherClient."""
    async with WeatherClient() as client:
        # Get game forecast with automatic fallback
        game_time = datetime.now().replace(hour=13, minute=0, second=0)
        forecast = await client.get_game_forecast(
            "Kansas City", "MO", game_time
        )

        # Normalize data
        normalized = client.normalize_weather_data(forecast)

        print(f"\nGame forecast for {game_time}:")
        print(f"  Source: {normalized['source']}")
        print(f"  Temperature: {normalized['temperature_f']}°F")
        print(f"  Weather: {normalized['weather_text']}")
        print(f"  Wind: {normalized['wind_speed_mph']} mph {normalized['wind_direction']}")
        print(f"  Humidity: {normalized['humidity']}%")
        print(f"  Precipitation: {normalized['precipitation_chance']}%")


if __name__ == "__main__":
    asyncio.run(main())

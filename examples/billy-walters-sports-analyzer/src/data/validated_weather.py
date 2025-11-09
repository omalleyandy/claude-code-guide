"""
Validated Weather Client

Wraps WeatherClient with data validation using the validation hooks.
"""

import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from .weather_client import WeatherClient

logger = logging.getLogger(__name__)


class ValidatedWeatherClient:
    """Weather client with integrated data validation."""

    def __init__(
        self,
        accuweather_api_key: str | None = None,
        openweather_api_key: str | None = None,
        prefer_accuweather: bool = True,
        validation_script_path: str | None = None,
    ):
        """
        Initialize validated weather client.

        Args:
            accuweather_api_key: AccuWeather API key
            openweather_api_key: OpenWeather API key
            prefer_accuweather: If True, try AccuWeather first
            validation_script_path: Path to validate_data.py script
        """
        self.client = WeatherClient(
            accuweather_api_key=accuweather_api_key,
            openweather_api_key=openweather_api_key,
            prefer_accuweather=prefer_accuweather,
        )

        # Default to .claude/hooks/validate_data.py
        if validation_script_path is None:
            self.validation_script_path = Path(".claude/hooks/validate_data.py")
        else:
            self.validation_script_path = Path(validation_script_path)

        if not self.validation_script_path.exists():
            logger.warning(
                f"Validation script not found: {self.validation_script_path}"
            )

    async def __aenter__(self):
        """Async context manager entry."""
        await self.client.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.client.close()

    def _validate_data(
        self, data_type: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Run validation script on data.

        Args:
            data_type: Type of data to validate (weather)
            data: Data to validate

        Returns:
            Validation result dict with 'valid' and 'errors' keys

        Raises:
            RuntimeError: If validation script execution fails
        """
        if not self.validation_script_path.exists():
            logger.warning("Validation script not found, skipping validation")
            return {"valid": True, "errors": [], "warnings": []}

        try:
            # Run validation script as subprocess
            result = subprocess.run(
                ["python", str(self.validation_script_path), data_type],
                input=json.dumps(data),
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                return json.loads(result.stdout)
            else:
                logger.error(f"Validation script error: {result.stderr}")
                raise RuntimeError(f"Validation failed: {result.stderr}")

        except subprocess.TimeoutExpired:
            logger.error("Validation script timed out")
            raise RuntimeError("Validation timeout")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse validation output: {e}")
            raise RuntimeError(f"Invalid validation output: {e}") from e
        except Exception as e:
            logger.error(f"Validation error: {e}", exc_info=True)
            raise RuntimeError(f"Validation error: {e}") from e

    async def get_and_validate_game_forecast(
        self,
        city: str,
        state: str,
        game_time: datetime,
        max_retries: int = 3,
        strict: bool = True,
    ) -> dict[str, Any]:
        """
        Get game forecast with validation.

        Args:
            city: Stadium city
            state: Stadium state
            game_time: Game start time
            max_retries: Maximum retry attempts
            strict: If True, raise on validation errors

        Returns:
            Validated weather forecast dictionary

        Raises:
            ValueError: If validation fails in strict mode
            RuntimeError: If fetch fails
        """
        logger.info(
            f"Fetching and validating game forecast for {city}, {state}"
        )

        # Fetch weather data
        weather = await self.client.get_game_forecast(
            city, state, game_time, max_retries=max_retries
        )

        # Normalize data
        normalized = self.client.normalize_weather_data(weather)

        # Validate
        validation_result = self._validate_data("weather", normalized)

        if not validation_result["valid"]:
            errors = validation_result.get("errors", [])
            error_msg = (
                f"Weather validation failed for {city}, {state}: "
                f"{', '.join(errors)}"
            )

            if strict:
                logger.error(error_msg)
                raise ValueError(error_msg)
            else:
                logger.warning(error_msg)

        # Log warnings
        warnings = validation_result.get("warnings", [])
        if warnings:
            logger.warning(
                f"Weather warnings for {city}, {state}: "
                f"{', '.join(warnings)}"
            )

        logger.info(
            f"Successfully fetched and validated forecast for {city}, {state}"
        )
        return normalized

    async def get_and_validate_current_weather(
        self,
        city: str,
        state: str,
        max_retries: int = 3,
        strict: bool = True,
    ) -> dict[str, Any]:
        """
        Get current weather with validation.

        Args:
            city: City name
            state: State abbreviation
            max_retries: Maximum retry attempts
            strict: If True, raise on validation errors

        Returns:
            Validated current weather dictionary

        Raises:
            ValueError: If validation fails in strict mode
            RuntimeError: If fetch fails
        """
        logger.info(f"Fetching and validating current weather for {city}, {state}")

        # Fetch weather data
        weather = await self.client.get_current_weather(
            city, state, max_retries=max_retries
        )

        # Normalize data
        normalized = self.client.normalize_weather_data(weather)

        # Validate
        validation_result = self._validate_data("weather", normalized)

        if not validation_result["valid"]:
            errors = validation_result.get("errors", [])
            error_msg = (
                f"Weather validation failed for {city}, {state}: "
                f"{', '.join(errors)}"
            )

            if strict:
                logger.error(error_msg)
                raise ValueError(error_msg)
            else:
                logger.warning(error_msg)

        # Log warnings
        warnings = validation_result.get("warnings", [])
        if warnings:
            logger.warning(
                f"Weather warnings for {city}, {state}: {', '.join(warnings)}"
            )

        return normalized


# Example usage
import asyncio


async def main():
    """Example usage of ValidatedWeatherClient."""
    async with ValidatedWeatherClient() as client:
        # Get and validate game forecast
        try:
            game_time = datetime.now().replace(hour=13, minute=0, second=0)
            forecast = await client.get_and_validate_game_forecast(
                "Kansas City", "MO", game_time, strict=True
            )

            print(f"\nValidated game forecast:")
            print(f"  Source: {forecast['source']}")
            print(f"  Temperature: {forecast['temperature_f']}°F")
            print(f"  Weather: {forecast['weather_text']}")
            print(f"  Wind: {forecast['wind_speed_mph']} mph")
            print(f"  Precipitation: {forecast['precipitation_chance']}%")

        except ValueError as e:
            print(f"\nValidation failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())

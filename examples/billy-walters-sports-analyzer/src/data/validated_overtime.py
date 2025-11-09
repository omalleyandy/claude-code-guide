"""
Validated Overtime API Client

Wraps OvertimeAPIClient with data validation using the validation hooks.
"""

import asyncio
import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from .overtime_client import OvertimeAPIClient

logger = logging.getLogger(__name__)


class ValidatedOvertimeClient:
    """Overtime API client with integrated data validation."""

    def __init__(
        self,
        customer_id: str | None = None,
        password: str | None = None,
        rate_limit_delay: float = 1.0,
        timeout: float = 30.0,
        validation_script_path: str | None = None,
    ):
        """
        Initialize validated Overtime client.

        Args:
            customer_id: Overtime customer ID
            password: Overtime password
            rate_limit_delay: Delay between requests in seconds
            timeout: Request timeout in seconds
            validation_script_path: Path to validate_data.py script
        """
        self.client = OvertimeAPIClient(
            customer_id=customer_id,
            password=password,
            rate_limit_delay=rate_limit_delay,
            timeout=timeout,
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
            data_type: Type of data to validate (game, odds, weather)
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

    async def fetch_and_validate_games(
        self,
        league: Literal["NFL", "NCAAF"],
        week: int | None = None,
        season: int | None = None,
        max_retries: int = 3,
        strict: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Fetch game data with validation.

        Args:
            league: League to fetch games for
            week: Week number (optional)
            season: Season year (optional)
            max_retries: Maximum retry attempts
            strict: If True, raise on validation errors; if False, log warnings

        Returns:
            List of validated game dictionaries

        Raises:
            ValueError: If validation fails in strict mode
            RuntimeError: If fetch or validation fails
        """
        # Fetch raw game data
        logger.info(f"Fetching {league} games from Overtime API")
        raw_games = await self.client.fetch_games(
            league, week=week, season=season, max_retries=max_retries
        )

        # Validate each game
        validated_games: list[dict[str, Any]] = []
        validation_errors: list[str] = []
        validation_warnings: list[str] = []

        for game in raw_games:
            try:
                # Validate game data
                validation_result = self._validate_data("game", game)

                if not validation_result["valid"]:
                    errors = validation_result.get("errors", [])
                    home_team = game.get("home_team_data", {}).get("name", "Unknown")
                    away_team = game.get("away_team_data", {}).get("name", "Unknown")
                    error_msg = (
                        f"Validation failed for {away_team} @ {home_team}: "
                        f"{', '.join(errors)}"
                    )
                    validation_errors.append(error_msg)

                    if strict:
                        logger.error(error_msg)
                        continue  # Skip invalid game
                    else:
                        logger.warning(error_msg)

                # Collect warnings
                warnings = validation_result.get("warnings", [])
                if warnings:
                    home_team = game.get("home_team_data", {}).get("name", "Unknown")
                    away_team = game.get("away_team_data", {}).get("name", "Unknown")
                    warning_msg = (
                        f"Warnings for {away_team} @ {home_team}: "
                        f"{', '.join(warnings)}"
                    )
                    validation_warnings.append(warning_msg)
                    logger.warning(warning_msg)

                # Add to validated games
                validated_games.append(game)

            except Exception as e:
                error_msg = f"Validation error for game: {e}"
                validation_errors.append(error_msg)
                logger.error(error_msg, exc_info=True)

                if strict:
                    continue
                else:
                    validated_games.append(game)

        # Log validation summary
        logger.info(
            f"Validation complete: {len(validated_games)}/{len(raw_games)} "
            f"games passed, {len(validation_errors)} errors, "
            f"{len(validation_warnings)} warnings"
        )

        if strict and validation_errors:
            raise ValueError(
                f"Validation failed with {len(validation_errors)} errors:\n"
                + "\n".join(validation_errors[:5])  # Show first 5 errors
            )

        return validated_games

    async def fetch_and_validate_game_details(
        self, game_id: str, max_retries: int = 3, strict: bool = True
    ) -> dict[str, Any]:
        """
        Fetch and validate detailed game information.

        Args:
            game_id: Game ID
            max_retries: Maximum retry attempts
            strict: If True, raise on validation errors

        Returns:
            Validated game details dictionary

        Raises:
            ValueError: If validation fails in strict mode
        """
        logger.info(f"Fetching and validating game {game_id}")

        # Fetch game details
        game = await self.client.fetch_game_details(
            game_id, max_retries=max_retries
        )

        # Validate
        validation_result = self._validate_data("game", game)

        if not validation_result["valid"]:
            errors = validation_result.get("errors", [])
            error_msg = f"Game validation failed: {', '.join(errors)}"

            if strict:
                raise ValueError(error_msg)
            else:
                logger.warning(error_msg)

        # Log warnings
        warnings = validation_result.get("warnings", [])
        if warnings:
            logger.warning(f"Warnings: {', '.join(warnings)}")

        return game

    async def fetch_nfl_games(
        self,
        week: int | None = None,
        season: int | None = None,
        strict: bool = True,
    ) -> list[dict[str, Any]]:
        """Fetch and validate NFL games."""
        return await self.fetch_and_validate_games(
            "NFL", week=week, season=season, strict=strict
        )

    async def fetch_ncaaf_games(
        self,
        week: int | None = None,
        season: int | None = None,
        strict: bool = True,
    ) -> list[dict[str, Any]]:
        """Fetch and validate NCAAF games."""
        return await self.fetch_and_validate_games(
            "NCAAF", week=week, season=season, strict=strict
        )


# Example usage
async def main():
    """Example usage of ValidatedOvertimeClient."""
    async with ValidatedOvertimeClient() as client:
        # Fetch and validate NFL games (strict mode)
        try:
            nfl_games = await client.fetch_nfl_games(strict=True)
            print(f"\nNFL Games (validated):")
            print(f"  Total games: {len(nfl_games)}")

            for game in nfl_games[:3]:
                home_team = game.get("home_team_data", {}).get("name")
                away_team = game.get("away_team_data", {}).get("name")
                print(f"\n  {away_team} @ {home_team}")
                print(f"    Status: {game.get('status')}")
                print(f"    Date: {game.get('game_date')}")

        except ValueError as e:
            print(f"\nValidation failed: {e}")

        # Fetch NCAAF games (non-strict mode)
        ncaaf_games = await client.fetch_ncaaf_games(strict=False)
        print(f"\n\nNCAAF Games (validated, warnings allowed):")
        print(f"  Total games: {len(ncaaf_games)}")


if __name__ == "__main__":
    asyncio.run(main())

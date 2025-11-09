"""
Validated Action Network Client

Wraps ActionNetworkClient with data validation using the validation hooks.
"""

import asyncio
import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from .action_network_client import ActionNetworkClient
from .models import ActionNetworkResponse, League

logger = logging.getLogger(__name__)


class ValidatedActionNetworkClient:
    """Action Network client with integrated data validation."""

    def __init__(
        self,
        username: str | None = None,
        password: str | None = None,
        headless: bool = True,
        rate_limit_delay: float = 2.0,
        validation_script_path: str | None = None,
    ):
        """
        Initialize validated Action Network client.

        Args:
            username: Action Network username
            password: Action Network password
            headless: Run browser in headless mode
            rate_limit_delay: Delay between requests in seconds
            validation_script_path: Path to validate_data.py script
        """
        self.client = ActionNetworkClient(
            username=username,
            password=password,
            headless=headless,
            rate_limit_delay=rate_limit_delay,
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
            data_type: Type of data to validate (odds, weather, game)
            data: Data to validate

        Returns:
            Validation result dict with 'valid' and 'errors' keys

        Raises:
            RuntimeError: If validation script execution fails
        """
        if not self.validation_script_path.exists():
            logger.warning(
                "Validation script not found, skipping validation"
            )
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
                raise RuntimeError(
                    f"Validation failed: {result.stderr}"
                )

        except subprocess.TimeoutExpired:
            logger.error("Validation script timed out")
            raise RuntimeError("Validation timeout")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse validation output: {e}")
            raise RuntimeError(f"Invalid validation output: {e}") from e
        except Exception as e:
            logger.error(f"Validation error: {e}", exc_info=True)
            raise RuntimeError(f"Validation error: {e}") from e

    async def fetch_and_validate_odds(
        self,
        league: Literal["NFL", "NCAAF"],
        max_retries: int = 3,
        strict: bool = True,
    ) -> ActionNetworkResponse:
        """
        Fetch odds data with validation.

        Args:
            league: League to fetch odds for
            max_retries: Maximum retry attempts
            strict: If True, raise on validation errors; if False, log warnings

        Returns:
            ActionNetworkResponse with validated games

        Raises:
            ValueError: If validation fails in strict mode
            RuntimeError: If fetch or validation fails
        """
        # Fetch raw odds data
        logger.info(f"Fetching {league} odds from Action Network")
        raw_games = await self.client.fetch_odds(
            league, max_retries=max_retries
        )

        # Validate each game
        validated_games: list[dict[str, Any]] = []
        validation_errors: list[str] = []
        validation_warnings: list[str] = []

        for game in raw_games:
            try:
                # Validate odds data
                validation_result = self._validate_data("odds", game)

                if not validation_result["valid"]:
                    errors = validation_result.get("errors", [])
                    error_msg = (
                        f"Validation failed for {game.get('away_team')} @ "
                        f"{game.get('home_team')}: {', '.join(errors)}"
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
                    warning_msg = (
                        f"Warnings for {game.get('away_team')} @ "
                        f"{game.get('home_team')}: {', '.join(warnings)}"
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

        # Create response model
        response = ActionNetworkResponse(
            league=League(league),
            games=validated_games,
            fetch_time=datetime.now(),
            total_games=len(validated_games),
        )

        return response

    async def fetch_nfl_odds(
        self, max_retries: int = 3, strict: bool = True
    ) -> ActionNetworkResponse:
        """Fetch and validate NFL odds."""
        return await self.fetch_and_validate_odds(
            "NFL", max_retries=max_retries, strict=strict
        )

    async def fetch_ncaaf_odds(
        self, max_retries: int = 3, strict: bool = True
    ) -> ActionNetworkResponse:
        """Fetch and validate NCAAF odds."""
        return await self.fetch_and_validate_odds(
            "NCAAF", max_retries=max_retries, strict=strict
        )


# Example usage
async def main():
    """Example usage of ValidatedActionNetworkClient."""
    async with ValidatedActionNetworkClient(headless=False) as client:
        # Fetch and validate NFL odds (strict mode)
        try:
            nfl_response = await client.fetch_nfl_odds(strict=True)
            print(f"\nNFL Odds (validated):")
            print(f"  Total games: {nfl_response.total_games}")
            print(f"  Fetch time: {nfl_response.fetch_time}")

            for game in nfl_response.games[:3]:
                print(f"\n  {game['away_team']} @ {game['home_team']}")
                print(f"    Spread: {game['spread']} ({game['spread_odds']})")
                print(f"    O/U: {game['over_under']} ({game['total_odds']})")

        except ValueError as e:
            print(f"\nValidation failed: {e}")

        # Fetch NCAAF odds (non-strict mode - allow warnings)
        ncaaf_response = await client.fetch_ncaaf_odds(strict=False)
        print(f"\n\nNCAAF Odds (validated, warnings allowed):")
        print(f"  Total games: {ncaaf_response.total_games}")


if __name__ == "__main__":
    asyncio.run(main())

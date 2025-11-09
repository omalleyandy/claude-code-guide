"""
Overtime API Client

Fetches NFL and NCAAF game data from Overtime API.
Implements rate limiting, retry logic, and error handling.
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Any, Literal

import httpx

logger = logging.getLogger(__name__)


class OvertimeAPIClient:
    """Client for fetching game data from Overtime API."""

    BASE_URL = "https://api.overtime.tv"

    def __init__(
        self,
        customer_id: str | None = None,
        password: str | None = None,
        rate_limit_delay: float = 1.0,
        timeout: float = 30.0,
    ):
        """
        Initialize Overtime API client.

        Args:
            customer_id: Overtime customer ID (defaults to OV_CUSTOMER_ID env var)
            password: Overtime password (defaults to OV_PASSWORD env var)
            rate_limit_delay: Delay between requests in seconds
            timeout: Request timeout in seconds
        """
        self.customer_id = customer_id or os.getenv("OV_CUSTOMER_ID")
        self.password = password or os.getenv("OV_PASSWORD")
        self.rate_limit_delay = rate_limit_delay
        self.timeout = timeout
        self.last_request_time: float = 0.0
        self._client: httpx.AsyncClient | None = None

        if not self.customer_id or not self.password:
            raise ValueError(
                "OV_CUSTOMER_ID and OV_PASSWORD must be set "
                "either as arguments or environment variables"
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
        logger.info("Initializing Overtime API client")
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=self.timeout,
            headers={
                "User-Agent": "BillyWaltersSportsAnalyzer/1.0",
                "Accept": "application/json",
            },
        )

        # Authenticate
        await self._authenticate()
        logger.info("Successfully authenticated with Overtime API")

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
        logger.info("Closed Overtime API client")

    async def _authenticate(self) -> None:
        """Authenticate with Overtime API."""
        if not self._client:
            raise RuntimeError("Client not initialized. Call connect() first.")

        try:
            response = await self._client.post(
                "/auth/login",
                json={
                    "customer_id": self.customer_id,
                    "password": self.password,
                },
            )
            response.raise_for_status()

            auth_data = response.json()
            token = auth_data.get("token")

            if not token:
                raise RuntimeError("No token in authentication response")

            # Set authorization header for future requests
            self._client.headers["Authorization"] = f"Bearer {token}"

            logger.info("Authentication successful")

        except httpx.HTTPStatusError as e:
            logger.error(f"Authentication failed: {e.response.status_code}")
            raise RuntimeError(f"Authentication failed: {e}") from e
        except Exception as e:
            logger.error(f"Authentication error: {e}", exc_info=True)
            raise RuntimeError(f"Authentication error: {e}") from e

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
        method: str,
        endpoint: str,
        max_retries: int = 3,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Make HTTP request with retry logic.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint
            max_retries: Maximum retry attempts
            **kwargs: Additional arguments for httpx request

        Returns:
            Response JSON data

        Raises:
            RuntimeError: If request fails after all retries
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Call connect() first.")

        await self._rate_limit()

        for attempt in range(max_retries):
            try:
                logger.debug(
                    f"{method} {endpoint} (attempt {attempt + 1}/{max_retries})"
                )

                response = await self._client.request(
                    method, endpoint, **kwargs
                )
                response.raise_for_status()

                return response.json()

            except httpx.HTTPStatusError as e:
                logger.warning(
                    f"HTTP error {e.response.status_code}: {e.response.text}"
                )

                # Don't retry client errors (4xx)
                if 400 <= e.response.status_code < 500:
                    raise RuntimeError(
                        f"Client error {e.response.status_code}: {e.response.text}"
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

        # Should never reach here
        raise RuntimeError("Unexpected error in _make_request")

    async def fetch_games(
        self,
        league: Literal["NFL", "NCAAF"],
        week: int | None = None,
        season: int | None = None,
        max_retries: int = 3,
    ) -> list[dict[str, Any]]:
        """
        Fetch game data for specified league.

        Args:
            league: League to fetch games for ("NFL" or "NCAAF")
            week: Week number (optional, defaults to current week)
            season: Season year (optional, defaults to current year)
            max_retries: Maximum retry attempts

        Returns:
            List of game dictionaries

        Raises:
            RuntimeError: If fetch fails
        """
        params: dict[str, Any] = {"league": league}

        if week is not None:
            params["week"] = week

        if season is not None:
            params["season"] = season
        else:
            params["season"] = datetime.now().year

        logger.info(
            f"Fetching {league} games for season {params['season']}"
            + (f" week {week}" if week else "")
        )

        data = await self._make_request(
            "GET", "/games", params=params, max_retries=max_retries
        )

        games = data.get("games", [])
        logger.info(f"Fetched {len(games)} games")

        # Enrich game data with additional fields
        enriched_games = []
        for game in games:
            enriched_game = self._enrich_game_data(game, league)
            enriched_games.append(enriched_game)

        return enriched_games

    def _enrich_game_data(
        self, game: dict[str, Any], league: str
    ) -> dict[str, Any]:
        """
        Enrich game data with additional computed fields.

        Args:
            game: Raw game data from API
            league: League name

        Returns:
            Enriched game dictionary
        """
        enriched = game.copy()

        # Add metadata
        enriched["league"] = league
        enriched["source"] = "overtime"
        enriched["fetch_time"] = datetime.now().isoformat()

        # Parse game date if needed
        if "game_date" in enriched and isinstance(
            enriched["game_date"], str
        ):
            try:
                enriched["game_date"] = datetime.fromisoformat(
                    enriched["game_date"].replace("Z", "+00:00")
                )
            except Exception:
                logger.warning(
                    f"Failed to parse game_date: {enriched['game_date']}"
                )

        # Add game status
        if "status" not in enriched:
            enriched["status"] = self._determine_game_status(enriched)

        # Extract team data
        enriched["home_team_data"] = enriched.get("home_team", {})
        enriched["away_team_data"] = enriched.get("away_team", {})

        return enriched

    def _determine_game_status(self, game: dict[str, Any]) -> str:
        """Determine game status from game data."""
        if game.get("final"):
            return "final"
        elif game.get("in_progress"):
            return "in_progress"
        elif game.get("postponed"):
            return "postponed"
        else:
            return "scheduled"

    async def fetch_game_details(
        self, game_id: str, max_retries: int = 3
    ) -> dict[str, Any]:
        """
        Fetch detailed information for a specific game.

        Args:
            game_id: Game ID
            max_retries: Maximum retry attempts

        Returns:
            Game details dictionary

        Raises:
            RuntimeError: If fetch fails
        """
        logger.info(f"Fetching details for game {game_id}")

        data = await self._make_request(
            "GET", f"/games/{game_id}", max_retries=max_retries
        )

        game = data.get("game", {})
        logger.info(f"Fetched details for {game_id}")

        return game

    async def fetch_team_stats(
        self,
        team_id: str,
        league: Literal["NFL", "NCAAF"],
        season: int | None = None,
        max_retries: int = 3,
    ) -> dict[str, Any]:
        """
        Fetch team statistics.

        Args:
            team_id: Team ID
            league: League name
            season: Season year (defaults to current year)
            max_retries: Maximum retry attempts

        Returns:
            Team stats dictionary

        Raises:
            RuntimeError: If fetch fails
        """
        params: dict[str, Any] = {"league": league}

        if season is not None:
            params["season"] = season
        else:
            params["season"] = datetime.now().year

        logger.info(f"Fetching stats for team {team_id}")

        data = await self._make_request(
            "GET",
            f"/teams/{team_id}/stats",
            params=params,
            max_retries=max_retries,
        )

        stats = data.get("stats", {})
        logger.info(f"Fetched stats for {team_id}")

        return stats

    async def fetch_nfl_games(
        self, week: int | None = None, season: int | None = None
    ) -> list[dict[str, Any]]:
        """Convenience method to fetch NFL games."""
        return await self.fetch_games("NFL", week=week, season=season)

    async def fetch_ncaaf_games(
        self, week: int | None = None, season: int | None = None
    ) -> list[dict[str, Any]]:
        """Convenience method to fetch NCAAF games."""
        return await self.fetch_games("NCAAF", week=week, season=season)


# Example usage
async def main():
    """Example usage of OvertimeAPIClient."""
    async with OvertimeAPIClient() as client:
        # Fetch current week NFL games
        nfl_games = await client.fetch_nfl_games()
        print(f"\nFetched {len(nfl_games)} NFL games")

        for game in nfl_games[:3]:
            print(f"\n{game.get('away_team_data', {}).get('name')} @ "
                  f"{game.get('home_team_data', {}).get('name')}")
            print(f"  Status: {game.get('status')}")
            print(f"  Date: {game.get('game_date')}")

        # Fetch NCAAF games
        ncaaf_games = await client.fetch_ncaaf_games()
        print(f"\n\nFetched {len(ncaaf_games)} NCAAF games")

        # Fetch specific game details
        if nfl_games:
            game_id = nfl_games[0].get("game_id")
            if game_id:
                details = await client.fetch_game_details(game_id)
                print(f"\n\nGame details for {game_id}:")
                print(f"  Home score: {details.get('home_score')}")
                print(f"  Away score: {details.get('away_score')}")


if __name__ == "__main__":
    asyncio.run(main())

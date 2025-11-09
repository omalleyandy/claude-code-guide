"""
Action Network Web Scraper Client

Fetches NFL and NCAAF odds data from Action Network using Playwright.
Implements rate limiting, retry logic, and data validation.
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Any, Literal

from playwright.async_api import Browser, Page, async_playwright

logger = logging.getLogger(__name__)


class ActionNetworkClient:
    """Client for scraping odds data from Action Network."""

    BASE_URL = "https://www.actionnetwork.com"
    LOGIN_URL = f"{BASE_URL}/login"

    # Selectors from user documentation
    SELECTORS = {
        "login_button": ".user-component__button.user-component__login.css-1wwjzac.epb8che0",
        "username_input": 'input[placeholder="Email"]',
        "password_input": 'input[placeholder="Password"]',
        "submit_button": 'button[type="submit"]',
        "sport_nfl": "//div[@class='css-p3ig27 emv4lho0']//div//span[@class='nav-link__title'][normalize-space()='NFL']",
        "sport_ncaaf": "//div[@class='css-p3ig27 emv4lho0']//div//span[@class='nav-link__title'][normalize-space()='NCAAF']",
        "odds_tab": "//a[contains(@class,'subNav__navLink')][normalize-space()='Odds']",
    }

    def __init__(
        self,
        username: str | None = None,
        password: str | None = None,
        headless: bool = True,
        rate_limit_delay: float = 2.0,
    ):
        """
        Initialize Action Network client.

        Args:
            username: Action Network username (defaults to ACTION_USERNAME env var)
            password: Action Network password (defaults to ACTION_PASSWORD env var)
            headless: Run browser in headless mode
            rate_limit_delay: Delay between requests in seconds
        """
        self.username = username or os.getenv("ACTION_USERNAME")
        self.password = password or os.getenv("ACTION_PASSWORD")
        self.headless = headless
        self.rate_limit_delay = rate_limit_delay
        self.last_request_time: float = 0.0
        self._browser: Browser | None = None
        self._page: Page | None = None

        if not self.username or not self.password:
            raise ValueError(
                "ACTION_USERNAME and ACTION_PASSWORD must be set "
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
        """Initialize browser and login to Action Network."""
        logger.info("Initializing Playwright browser")
        playwright = await async_playwright().start()
        self._browser = await playwright.chromium.launch(headless=self.headless)
        self._page = await self._browser.new_page()

        # Login to Action Network
        await self._login()
        logger.info("Successfully logged in to Action Network")

    async def close(self) -> None:
        """Close browser and cleanup resources."""
        if self._page:
            await self._page.close()
        if self._browser:
            await self._browser.close()
        logger.info("Closed Action Network client")

    async def _login(self) -> None:
        """Login to Action Network using provided credentials."""
        if not self._page:
            raise RuntimeError("Browser not initialized. Call connect() first.")

        page = self._page

        logger.info("Navigating to login page")
        await page.goto(self.LOGIN_URL, wait_until="networkidle")

        # Click login button to reveal login form
        try:
            await page.click(self.SELECTORS["login_button"], timeout=5000)
        except Exception:
            # Login form may already be visible
            logger.debug("Login button not found, form may already be visible")

        # Fill in credentials
        logger.info("Entering credentials")
        await page.fill(self.SELECTORS["username_input"], self.username)
        await page.fill(self.SELECTORS["password_input"], self.password)

        # Submit login form
        await page.click(self.SELECTORS["submit_button"])

        # Wait for navigation to complete
        await page.wait_for_load_state("networkidle")

        # Verify login success by checking for user-specific element
        try:
            await page.wait_for_selector(
                ".user-component__button", state="visible", timeout=10000
            )
            logger.info("Login successful")
        except Exception as e:
            raise RuntimeError(f"Login failed: {e}") from e

    async def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        current_time = asyncio.get_event_loop().time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.rate_limit_delay:
            wait_time = self.rate_limit_delay - time_since_last
            logger.debug(f"Rate limiting: waiting {wait_time:.2f}s")
            await asyncio.sleep(wait_time)

        self.last_request_time = asyncio.get_event_loop().time()

    async def fetch_odds(
        self,
        league: Literal["NFL", "NCAAF"],
        max_retries: int = 3,
    ) -> list[dict[str, Any]]:
        """
        Fetch odds data for specified league.

        Args:
            league: League to fetch odds for ("NFL" or "NCAAF")
            max_retries: Maximum number of retry attempts

        Returns:
            List of game odds dictionaries

        Raises:
            RuntimeError: If browser not initialized or fetch fails
        """
        if not self._page:
            raise RuntimeError("Browser not initialized. Call connect() first.")

        await self._rate_limit()

        for attempt in range(max_retries):
            try:
                logger.info(
                    f"Fetching {league} odds (attempt {attempt + 1}/{max_retries})"
                )
                return await self._fetch_odds_impl(league)
            except Exception as e:
                logger.warning(
                    f"Attempt {attempt + 1} failed: {e}", exc_info=True
                )
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.info(f"Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    raise RuntimeError(
                        f"Failed to fetch {league} odds after {max_retries} attempts"
                    ) from e

        return []  # Should never reach here

    async def _fetch_odds_impl(
        self, league: Literal["NFL", "NCAAF"]
    ) -> list[dict[str, Any]]:
        """Implementation of odds fetching."""
        if not self._page:
            raise RuntimeError("Browser not initialized")

        page = self._page

        # Navigate to league
        sport_selector = (
            self.SELECTORS["sport_nfl"]
            if league == "NFL"
            else self.SELECTORS["sport_ncaaf"]
        )
        logger.debug(f"Clicking {league} navigation")
        await page.click(sport_selector)
        await page.wait_for_load_state("networkidle")

        # Navigate to odds page
        logger.debug("Clicking Odds tab")
        await page.click(self.SELECTORS["odds_tab"])
        await page.wait_for_load_state("networkidle")

        # Extract odds data from table
        logger.debug("Extracting odds data from page")
        games = await self._extract_odds_from_page(page, league)

        logger.info(f"Successfully extracted {len(games)} games for {league}")
        return games

    async def _extract_odds_from_page(
        self, page: Page, league: Literal["NFL", "NCAAF"]
    ) -> list[dict[str, Any]]:
        """
        Extract odds data from the odds table.

        Args:
            page: Playwright page object
            league: League being scraped

        Returns:
            List of game dictionaries with odds data
        """
        games: list[dict[str, Any]] = []

        # Wait for odds table to load
        await page.wait_for_selector("table.odds-table", timeout=10000)

        # Extract game rows
        game_rows = await page.query_selector_all("tr.game-row")

        for row in game_rows:
            try:
                game_data = await self._extract_game_row(row, league)
                if game_data:
                    games.append(game_data)
            except Exception as e:
                logger.warning(f"Failed to extract game row: {e}")
                continue

        return games

    async def _extract_game_row(
        self, row, league: Literal["NFL", "NCAAF"]
    ) -> dict[str, Any] | None:
        """
        Extract odds data from a single game row.

        Args:
            row: Playwright element handle for game row
            league: League being scraped

        Returns:
            Game dictionary or None if extraction fails
        """
        try:
            # Extract team names
            teams = await row.query_selector_all(".team-name")
            if len(teams) < 2:
                return None

            away_team = await teams[0].inner_text()
            home_team = await teams[1].inner_text()

            # Extract game date/time
            game_time_elem = await row.query_selector(".game-time")
            game_time_text = (
                await game_time_elem.inner_text() if game_time_elem else ""
            )

            # Extract rotation numbers
            rotation_elems = await row.query_selector_all(".rotation-number")
            away_rotation = (
                await rotation_elems[0].inner_text()
                if len(rotation_elems) > 0
                else ""
            )
            home_rotation = (
                await rotation_elems[1].inner_text()
                if len(rotation_elems) > 1
                else ""
            )

            # Extract best odds (marked with bookmark icon)
            best_spread_elem = await row.query_selector(
                ".spread-cell .best-odds"
            )
            best_total_elem = await row.query_selector(".total-cell .best-odds")
            best_ml_elem = await row.query_selector(
                ".moneyline-cell .best-odds"
            )

            # Extract spread data
            spread_value = None
            spread_odds = None
            if best_spread_elem:
                spread_text = await best_spread_elem.inner_text()
                spread_parts = spread_text.strip().split()
                if len(spread_parts) >= 2:
                    spread_value = float(spread_parts[0])
                    spread_odds = int(spread_parts[1])

            # Extract total (over/under) data
            total_value = None
            total_odds = None
            if best_total_elem:
                total_text = await best_total_elem.inner_text()
                total_parts = total_text.strip().split()
                if len(total_parts) >= 2:
                    # Format: "O 47.5 -110" or "U 47.5 -110"
                    total_value = float(total_parts[1])
                    total_odds = int(total_parts[2])

            # Extract moneyline
            moneyline_home = None
            moneyline_away = None
            if best_ml_elem:
                ml_text = await best_ml_elem.inner_text()
                ml_parts = ml_text.strip().split()
                if len(ml_parts) >= 2:
                    moneyline_away = int(ml_parts[0])
                    moneyline_home = int(ml_parts[1])

            # Extract sportsbook name
            sportsbook_elem = await row.query_selector(".sportsbook-name")
            sportsbook = (
                await sportsbook_elem.inner_text() if sportsbook_elem else None
            )

            # Build game data dictionary
            game_data: dict[str, Any] = {
                "league": league,
                "away_team": away_team.strip(),
                "home_team": home_team.strip(),
                "game_time": game_time_text.strip(),
                "away_rotation": away_rotation.strip(),
                "home_rotation": home_rotation.strip(),
                "spread": spread_value,
                "spread_odds": spread_odds,
                "over_under": total_value,
                "total_odds": total_odds,
                "moneyline_home": moneyline_home,
                "moneyline_away": moneyline_away,
                "sportsbook": sportsbook,
                "timestamp": datetime.now().isoformat(),
                "source": "action_network",
            }

            return game_data

        except Exception as e:
            logger.warning(f"Error extracting game row: {e}", exc_info=True)
            return None

    async def fetch_nfl_odds(
        self, max_retries: int = 3
    ) -> list[dict[str, Any]]:
        """Convenience method to fetch NFL odds."""
        return await self.fetch_odds("NFL", max_retries=max_retries)

    async def fetch_ncaaf_odds(
        self, max_retries: int = 3
    ) -> list[dict[str, Any]]:
        """Convenience method to fetch NCAAF odds."""
        return await self.fetch_odds("NCAAF", max_retries=max_retries)


# Example usage
async def main():
    """Example usage of ActionNetworkClient."""
    async with ActionNetworkClient(headless=False) as client:
        # Fetch NFL odds
        nfl_odds = await client.fetch_nfl_odds()
        print(f"Fetched {len(nfl_odds)} NFL games")
        for game in nfl_odds[:3]:  # Print first 3 games
            print(f"\n{game['away_team']} @ {game['home_team']}")
            print(f"  Spread: {game['spread']} ({game['spread_odds']})")
            print(f"  O/U: {game['over_under']} ({game['total_odds']})")
            print(f"  ML: {game['moneyline_away']} / {game['moneyline_home']}")

        # Fetch NCAAF odds
        ncaaf_odds = await client.fetch_ncaaf_odds()
        print(f"\nFetched {len(ncaaf_odds)} NCAAF games")


if __name__ == "__main__":
    asyncio.run(main())

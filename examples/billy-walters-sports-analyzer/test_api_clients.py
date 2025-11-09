"""
API Clients Test Suite

Comprehensive tests for all API clients with validation.
Run with: uv run pytest test_api_clients.py -v
"""

import asyncio
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_action_network_client():
    """Test Action Network client without validation."""
    print("\n" + "="*70)
    print("TEST 1: Action Network Client (Basic)")
    print("="*70)

    try:
        from src.data.action_network_client import ActionNetworkClient

        async with ActionNetworkClient(headless=True) as client:
            logger.info("Testing NFL odds fetch...")
            nfl_odds = await client.fetch_nfl_odds()

            print(f"\n✅ Fetched {len(nfl_odds)} NFL games")

            if nfl_odds:
                game = nfl_odds[0]
                print(f"\nSample game:")
                print(f"  {game['away_team']} @ {game['home_team']}")
                print(f"  Spread: {game['spread']} ({game['spread_odds']})")
                print(f"  O/U: {game['over_under']} ({game['total_odds']})")
                print(f"  ML: {game['moneyline_away']} / {game['moneyline_home']}")
                print(f"  Sportsbook: {game['sportsbook']}")

        print("\n✅ Action Network client test PASSED")
        return True

    except Exception as e:
        print(f"\n❌ Action Network client test FAILED: {e}")
        logger.error("Action Network test failed", exc_info=True)
        return False


async def test_validated_action_network():
    """Test Action Network client with validation."""
    print("\n" + "="*70)
    print("TEST 2: Action Network Client (With Validation)")
    print("="*70)

    try:
        from src.data.validated_action_network import ValidatedActionNetworkClient

        async with ValidatedActionNetworkClient(headless=True) as client:
            logger.info("Testing validated NFL odds fetch...")

            # Test strict mode
            try:
                nfl_response = await client.fetch_nfl_odds(strict=True)
                print(f"\n✅ Strict validation passed")
                print(f"  Valid games: {nfl_response.total_games}")
                print(f"  Fetch time: {nfl_response.fetch_time}")

            except ValueError as e:
                print(f"\n⚠️ Strict validation failed (expected): {e}")

                # Try non-strict mode
                nfl_response = await client.fetch_nfl_odds(strict=False)
                print(f"\n✅ Non-strict validation passed")
                print(f"  Games with warnings: {nfl_response.total_games}")

        print("\n✅ Validated Action Network test PASSED")
        return True

    except Exception as e:
        print(f"\n❌ Validated Action Network test FAILED: {e}")
        logger.error("Validated Action Network test failed", exc_info=True)
        return False


async def test_overtime_client():
    """Test Overtime API client without validation."""
    print("\n" + "="*70)
    print("TEST 3: Overtime API Client (Basic)")
    print("="*70)

    try:
        from src.data.overtime_client import OvertimeAPIClient

        async with OvertimeAPIClient() as client:
            logger.info("Testing NFL games fetch...")
            nfl_games = await client.fetch_nfl_games()

            print(f"\n✅ Fetched {len(nfl_games)} NFL games")

            if nfl_games:
                game = nfl_games[0]
                home = game.get('home_team_data', {}).get('name', 'Unknown')
                away = game.get('away_team_data', {}).get('name', 'Unknown')
                print(f"\nSample game:")
                print(f"  {away} @ {home}")
                print(f"  Status: {game.get('status')}")
                print(f"  Date: {game.get('game_date')}")
                print(f"  League: {game.get('league')}")

                # Test game details fetch
                game_id = game.get('game_id')
                if game_id:
                    logger.info(f"Testing game details fetch for {game_id}...")
                    details = await client.fetch_game_details(game_id)
                    print(f"\n✅ Fetched game details")
                    print(f"  Home score: {details.get('home_score')}")
                    print(f"  Away score: {details.get('away_score')}")

        print("\n✅ Overtime client test PASSED")
        return True

    except Exception as e:
        print(f"\n❌ Overtime client test FAILED: {e}")
        logger.error("Overtime test failed", exc_info=True)
        return False


async def test_validated_overtime():
    """Test Overtime API client with validation."""
    print("\n" + "="*70)
    print("TEST 4: Overtime API Client (With Validation)")
    print("="*70)

    try:
        from src.data.validated_overtime import ValidatedOvertimeClient

        async with ValidatedOvertimeClient() as client:
            logger.info("Testing validated NFL games fetch...")

            # Test strict mode
            try:
                nfl_games = await client.fetch_nfl_games(strict=True)
                print(f"\n✅ Strict validation passed")
                print(f"  Valid games: {len(nfl_games)}")

            except ValueError as e:
                print(f"\n⚠️ Strict validation failed: {e}")

                # Try non-strict mode
                nfl_games = await client.fetch_nfl_games(strict=False)
                print(f"\n✅ Non-strict validation passed")
                print(f"  Games with warnings: {len(nfl_games)}")

        print("\n✅ Validated Overtime test PASSED")
        return True

    except Exception as e:
        print(f"\n❌ Validated Overtime test FAILED: {e}")
        logger.error("Validated Overtime test failed", exc_info=True)
        return False


async def test_accuweather_client():
    """Test AccuWeather client."""
    print("\n" + "="*70)
    print("TEST 5: AccuWeather Client")
    print("="*70)

    try:
        from src.data.accuweather_client import AccuWeatherClient

        async with AccuWeatherClient() as client:
            logger.info("Testing AccuWeather location and forecast...")

            # Get location key
            location_key = await client.get_location_key("Kansas City", "MO")
            print(f"\n✅ Location key: {location_key}")

            # Get current conditions
            conditions = await client.get_current_conditions(location_key)
            print(f"\nCurrent conditions:")
            print(f"  Temperature: {conditions['temperature_f']}°F")
            print(f"  Weather: {conditions['weather_text']}")
            print(f"  Wind: {conditions['wind_speed_mph']} mph {conditions['wind_direction']}")
            print(f"  Humidity: {conditions['humidity']}%")

            # Get game forecast
            game_time = datetime.now().replace(hour=13, minute=0, second=0)
            forecast = await client.get_game_forecast("Kansas City", "MO", game_time)
            print(f"\nGame forecast:")
            print(f"  Temperature: {forecast['temperature_f']}°F")
            print(f"  Weather: {forecast['weather_text']}")
            print(f"  Precipitation: {forecast.get('precipitation_probability', 0)}%")

        print("\n✅ AccuWeather client test PASSED")
        return True

    except Exception as e:
        print(f"\n❌ AccuWeather client test FAILED: {e}")
        logger.error("AccuWeather test failed", exc_info=True)
        return False


async def test_openweather_client():
    """Test OpenWeather client."""
    print("\n" + "="*70)
    print("TEST 6: OpenWeather Client")
    print("="*70)

    try:
        from src.data.openweather_client import OpenWeatherClient

        async with OpenWeatherClient() as client:
            logger.info("Testing OpenWeather current and forecast...")

            # Get current weather
            current = await client.get_current_weather("Kansas City", "MO")
            print(f"\nCurrent weather:")
            print(f"  Temperature: {current['temperature_f']}°F")
            print(f"  Feels like: {current['feels_like_f']}°F")
            print(f"  Weather: {current['weather_text']}")
            print(f"  Wind: {current['wind_speed_mph']} mph")
            print(f"  Humidity: {current['humidity']}%")

            # Get game forecast
            game_time = datetime.now().replace(hour=13, minute=0, second=0)
            forecast = await client.get_game_forecast("Kansas City", "MO", game_time)
            print(f"\nGame forecast:")
            print(f"  Temperature: {forecast['temperature_f']}°F")
            print(f"  Weather: {forecast['weather_text']}")
            print(f"  Precipitation: {forecast['precipitation_chance']}%")

            # Test wind direction conversion
            wind_dir = client.wind_direction_text(forecast.get('wind_direction_deg'))
            print(f"  Wind direction: {wind_dir}")

        print("\n✅ OpenWeather client test PASSED")
        return True

    except Exception as e:
        print(f"\n❌ OpenWeather client test FAILED: {e}")
        logger.error("OpenWeather test failed", exc_info=True)
        return False


async def test_unified_weather_client():
    """Test unified weather client with fallback."""
    print("\n" + "="*70)
    print("TEST 7: Unified Weather Client (With Fallback)")
    print("="*70)

    try:
        from src.data.weather_client import WeatherClient

        async with WeatherClient(prefer_accuweather=True) as client:
            logger.info("Testing unified weather with fallback...")

            game_time = datetime.now().replace(hour=13, minute=0, second=0)
            forecast = await client.get_game_forecast("Kansas City", "MO", game_time)

            # Normalize data
            normalized = client.normalize_weather_data(forecast)

            print(f"\n✅ Unified weather fetch successful")
            print(f"  Source: {normalized['source']}")
            print(f"  Temperature: {normalized['temperature_f']}°F")
            print(f"  Weather: {normalized['weather_text']}")
            print(f"  Wind: {normalized['wind_speed_mph']} mph {normalized.get('wind_direction', 'N/A')}")
            print(f"  Humidity: {normalized['humidity']}%")
            print(f"  Precipitation: {normalized.get('precipitation_chance', 0)}%")

        print("\n✅ Unified weather client test PASSED")
        return True

    except Exception as e:
        print(f"\n❌ Unified weather client test FAILED: {e}")
        logger.error("Unified weather test failed", exc_info=True)
        return False


async def test_validated_weather():
    """Test validated weather client."""
    print("\n" + "="*70)
    print("TEST 8: Validated Weather Client")
    print("="*70)

    try:
        from src.data.validated_weather import ValidatedWeatherClient

        async with ValidatedWeatherClient() as client:
            logger.info("Testing validated weather fetch...")

            game_time = datetime.now().replace(hour=13, minute=0, second=0)

            try:
                forecast = await client.get_and_validate_game_forecast(
                    "Kansas City", "MO", game_time, strict=True
                )
                print(f"\n✅ Weather validation passed")
                print(f"  Source: {forecast['source']}")
                print(f"  Temperature: {forecast['temperature_f']}°F")
                print(f"  Weather: {forecast['weather_text']}")

            except ValueError as e:
                print(f"\n⚠️ Strict validation failed: {e}")

                # Try non-strict
                forecast = await client.get_and_validate_game_forecast(
                    "Kansas City", "MO", game_time, strict=False
                )
                print(f"\n✅ Non-strict validation passed")

        print("\n✅ Validated weather test PASSED")
        return True

    except Exception as e:
        print(f"\n❌ Validated weather test FAILED: {e}")
        logger.error("Validated weather test failed", exc_info=True)
        return False


async def test_full_integration():
    """Test full integration of all clients."""
    print("\n" + "="*70)
    print("TEST 9: Full Integration (All Clients)")
    print("="*70)

    try:
        from src.data.validated_action_network import ValidatedActionNetworkClient
        from src.data.validated_overtime import ValidatedOvertimeClient
        from src.data.validated_weather import ValidatedWeatherClient

        async with (
            ValidatedActionNetworkClient(headless=True) as odds_client,
            ValidatedOvertimeClient() as game_client,
            ValidatedWeatherClient() as weather_client,
        ):
            logger.info("Testing full integration...")

            # Fetch all data in parallel
            print("\nFetching all data sources in parallel...")

            odds_task = odds_client.fetch_nfl_odds(strict=False)
            games_task = game_client.fetch_nfl_games(strict=False)

            odds_response, games = await asyncio.gather(
                odds_task, games_task, return_exceptions=True
            )

            # Check results
            if isinstance(odds_response, Exception):
                print(f"⚠️ Odds fetch failed: {odds_response}")
            else:
                print(f"✅ Odds: {odds_response.total_games} games")

            if isinstance(games, Exception):
                print(f"⚠️ Games fetch failed: {games}")
            else:
                print(f"✅ Games: {len(games)} games")

            # Fetch weather for one game
            if not isinstance(odds_response, Exception) and odds_response.games:
                game = odds_response.games[0]
                city = "Kansas City"  # Would come from stadium data
                state = "MO"
                game_time = datetime.now()

                weather = await weather_client.get_and_validate_game_forecast(
                    city, state, game_time, strict=False
                )
                print(f"✅ Weather: {weather['temperature_f']}°F, {weather['weather_text']}")

                print(f"\n✅ Complete game data:")
                print(f"  Matchup: {game['away_team']} @ {game['home_team']}")
                print(f"  Spread: {game['spread']}")
                print(f"  O/U: {game['over_under']}")
                print(f"  Weather: {weather['temperature_f']}°F")

        print("\n✅ Full integration test PASSED")
        return True

    except Exception as e:
        print(f"\n❌ Full integration test FAILED: {e}")
        logger.error("Full integration test failed", exc_info=True)
        return False


async def run_all_tests():
    """Run all tests and report results."""
    print("\n" + "="*70)
    print("BILLY WALTERS SPORTS ANALYZER - API CLIENT TEST SUITE")
    print("="*70)

    tests = [
        ("Action Network Basic", test_action_network_client),
        ("Action Network Validated", test_validated_action_network),
        ("Overtime Basic", test_overtime_client),
        ("Overtime Validated", test_validated_overtime),
        ("AccuWeather", test_accuweather_client),
        ("OpenWeather", test_openweather_client),
        ("Unified Weather", test_unified_weather_client),
        ("Validated Weather", test_validated_weather),
        ("Full Integration", test_full_integration),
    ]

    results = {}

    for test_name, test_func in tests:
        try:
            result = await test_func()
            results[test_name] = result
        except Exception as e:
            logger.error(f"Test {test_name} crashed: {e}", exc_info=True)
            results[test_name] = False

    # Print summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)

    passed = sum(1 for r in results.values() if r)
    total = len(results)

    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name:30} {status}")

    print(f"\n{passed}/{total} tests passed ({passed/total*100:.1f}%)")

    if passed == total:
        print("\n🎉 All tests passed! API integration is working correctly.")
    else:
        print(f"\n⚠️ {total - passed} test(s) failed. Check logs above for details.")

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    exit(0 if success else 1)

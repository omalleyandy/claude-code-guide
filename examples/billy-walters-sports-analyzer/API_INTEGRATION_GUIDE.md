# API Integration Guide

Complete guide for integrating Action Network, Overtime, and Weather APIs into the Billy Walters Sports Analyzer.

## Overview

This integration provides three data sources:
1. **Action Network** - Odds data (spreads, totals, moneylines)
2. **Overtime API** - Game data (scores, schedules, teams)
3. **Weather APIs** - Weather forecasts (AccuWeather + OpenWeather)

All clients include:
- ✅ Rate limiting and retry logic
- ✅ Async/await support
- ✅ Automatic validation
- ✅ Error handling with fallback
- ✅ Comprehensive logging

## Installation

### 1. Install Dependencies

```bash
# Install required packages
uv add playwright pydantic httpx

# Install Playwright browsers (for Action Network scraping)
uv run playwright install chromium
```

### 2. Set Environment Variables

Create or update your `.env` file:

```bash
# Action Network (odds data)
ACTION_USERNAME=your_email@example.com
ACTION_PASSWORD=your_password

# Overtime API (game data)
OV_CUSTOMER_ID=your_customer_id
OV_PASSWORD=your_password

# Weather APIs
ACCUWEATHER_API_KEY=your_accuweather_key
OPENWEATHER_API_KEY=your_openweather_key

# AI Services
ANTHROPIC_API_KEY=your_anthropic_key
```

### 3. Copy Files to Your Project

Copy these files to your `billy-walters-sports-analyzer` project:

```
src/data/
├── __init__.py
├── models.py                        # Pydantic data models
├── action_network_client.py         # Action Network scraper
├── validated_action_network.py      # Validated wrapper
├── overtime_client.py               # Overtime API client
├── validated_overtime.py            # Validated wrapper
├── accuweather_client.py            # AccuWeather client
├── openweather_client.py            # OpenWeather client
├── weather_client.py                # Unified weather client
└── validated_weather.py             # Validated wrapper
```

## Usage Examples

### Action Network (Odds Data)

#### Basic Usage

```python
import asyncio
from src.data.action_network_client import ActionNetworkClient

async def fetch_odds():
    async with ActionNetworkClient() as client:
        # Fetch NFL odds
        nfl_odds = await client.fetch_nfl_odds()

        for game in nfl_odds:
            print(f"{game['away_team']} @ {game['home_team']}")
            print(f"  Spread: {game['spread']} ({game['spread_odds']})")
            print(f"  O/U: {game['over_under']} ({game['total_odds']})")
            print(f"  ML: {game['moneyline_away']} / {game['moneyline_home']}")

asyncio.run(fetch_odds())
```

#### With Validation

```python
from src.data.validated_action_network import ValidatedActionNetworkClient

async def fetch_validated_odds():
    async with ValidatedActionNetworkClient() as client:
        # Fetch with strict validation
        nfl_response = await client.fetch_nfl_odds(strict=True)

        print(f"Valid games: {nfl_response.total_games}")
        print(f"Fetch time: {nfl_response.fetch_time}")

        # All games in response have passed validation
        for game in nfl_response.games:
            print(f"{game['away_team']} @ {game['home_team']}")

asyncio.run(fetch_validated_odds())
```

### Overtime API (Game Data)

#### Basic Usage

```python
from src.data.overtime_client import OvertimeAPIClient

async def fetch_games():
    async with OvertimeAPIClient() as client:
        # Fetch current week NFL games
        nfl_games = await client.fetch_nfl_games()

        for game in nfl_games:
            home = game['home_team_data']['name']
            away = game['away_team_data']['name']
            print(f"{away} @ {home} - {game['status']}")

        # Fetch specific game details
        game_id = nfl_games[0]['game_id']
        details = await client.fetch_game_details(game_id)
        print(f"\nScores: {details['away_score']} - {details['home_score']}")

asyncio.run(fetch_games())
```

#### With Validation

```python
from src.data.validated_overtime import ValidatedOvertimeClient

async def fetch_validated_games():
    async with ValidatedOvertimeClient() as client:
        # Fetch and validate NFL games
        nfl_games = await client.fetch_nfl_games(strict=True)

        print(f"Valid games: {len(nfl_games)}")

        for game in nfl_games:
            print(f"Game ID: {game['game_id']}")
            print(f"  Status: {game['status']}")

asyncio.run(fetch_validated_games())
```

### Weather APIs

#### Unified Weather Client

```python
from src.data.weather_client import WeatherClient
from datetime import datetime

async def fetch_weather():
    async with WeatherClient() as client:
        # Get game forecast (auto fallback between AccuWeather/OpenWeather)
        game_time = datetime.now().replace(hour=13, minute=0)

        forecast = await client.get_game_forecast(
            "Kansas City", "MO", game_time
        )

        # Normalize data from any source
        normalized = client.normalize_weather_data(forecast)

        print(f"Source: {normalized['source']}")
        print(f"Temperature: {normalized['temperature_f']}°F")
        print(f"Wind: {normalized['wind_speed_mph']} mph")
        print(f"Precipitation: {normalized['precipitation_chance']}%")

asyncio.run(fetch_weather())
```

#### With Validation

```python
from src.data.validated_weather import ValidatedWeatherClient

async def fetch_validated_weather():
    async with ValidatedWeatherClient() as client:
        game_time = datetime.now().replace(hour=13, minute=0)

        forecast = await client.get_and_validate_game_forecast(
            "Kansas City", "MO", game_time, strict=True
        )

        # Data has been validated and normalized
        print(f"Temperature: {forecast['temperature_f']}°F")
        print(f"Weather: {forecast['weather_text']}")

asyncio.run(fetch_validated_weather())
```

## Integration with Autonomous Agent

### Complete Example

```python
from src.data.validated_action_network import ValidatedActionNetworkClient
from src.data.validated_overtime import ValidatedOvertimeClient
from src.data.validated_weather import ValidatedWeatherClient
from walters_autonomous_agent import WaltersCognitiveAgent
from datetime import datetime

async def run_full_analysis():
    """Complete analysis using all data sources."""
    agent = WaltersCognitiveAgent()

    # Initialize clients
    async with (
        ValidatedActionNetworkClient() as odds_client,
        ValidatedOvertimeClient() as game_client,
        ValidatedWeatherClient() as weather_client,
    ):
        # Fetch NFL odds
        odds_response = await odds_client.fetch_nfl_odds()

        # Fetch NFL games
        games = await game_client.fetch_nfl_games()

        # Analyze each game
        for odds_data in odds_response.games:
            # Get corresponding game data
            game_id = odds_data.get('game_id')

            # Fetch weather if outdoor stadium
            city = "Kansas City"  # Get from stadium data
            state = "MO"
            game_time = datetime.now()  # Get from game data

            weather = await weather_client.get_and_validate_game_forecast(
                city, state, game_time
            )

            # Combine all data
            complete_data = {
                **odds_data,
                'weather': weather,
            }

            # Run agent analysis
            decision = await agent.make_autonomous_decision(complete_data)

            if decision['recommendation'] == 'bet':
                print(f"\n🎯 BET RECOMMENDATION")
                print(f"Game: {odds_data['away_team']} @ {odds_data['home_team']}")
                print(f"Bet: {decision['bet_type']}")
                print(f"Confidence: {decision['confidence']}")
                print(f"Reasoning: {decision['reasoning']}")
                print(f"Weather: {weather['temperature_f']}°F, {weather['weather_text']}")

asyncio.run(run_full_analysis())
```

## Configuration

### Rate Limiting

Adjust rate limits to avoid API throttling:

```python
# Action Network - 2 seconds between requests
client = ActionNetworkClient(rate_limit_delay=2.0)

# Overtime - 1 second between requests
client = OvertimeAPIClient(rate_limit_delay=1.0)

# Weather - 1 second between requests
client = WeatherClient()
```

### Retry Logic

Configure retry behavior:

```python
# Maximum 5 retry attempts with exponential backoff
odds = await client.fetch_nfl_odds(max_retries=5)

# Exponential backoff: 1s, 2s, 4s, 8s, 16s
```

### Validation Modes

Choose validation strictness:

```python
# Strict mode - raise on any validation error
response = await client.fetch_nfl_odds(strict=True)

# Non-strict mode - log warnings but continue
response = await client.fetch_nfl_odds(strict=False)
```

## Error Handling

### Comprehensive Error Handling

```python
from src.data.validated_action_network import ValidatedActionNetworkClient

async def safe_fetch_odds():
    try:
        async with ValidatedActionNetworkClient() as client:
            odds = await client.fetch_nfl_odds(strict=True)
            return odds

    except ValueError as e:
        print(f"Validation failed: {e}")
        # Handle validation errors

    except RuntimeError as e:
        print(f"API error: {e}")
        # Handle API errors

    except Exception as e:
        print(f"Unexpected error: {e}")
        # Handle other errors
```

### Weather Fallback

```python
# Weather client automatically falls back between services
async with WeatherClient(prefer_accuweather=True) as client:
    # Tries AccuWeather first, falls back to OpenWeather
    forecast = await client.get_game_forecast(city, state, game_time)
```

## Performance

### Execution Times

- **Action Network**: 5-10 seconds per league (with rate limiting)
- **Overtime API**: 1-2 seconds per request
- **Weather APIs**: 1-2 seconds per request
- **Validation**: ~100ms per game

### Optimization Tips

1. **Parallel Fetching**: Fetch odds, games, and weather concurrently
2. **Caching**: Cache results to minimize API calls
3. **Batch Processing**: Process multiple games together
4. **Rate Limit Tuning**: Adjust delays based on API limits

### Parallel Example

```python
import asyncio

async def fetch_all_data():
    """Fetch all data sources in parallel."""
    async with (
        ValidatedActionNetworkClient() as odds_client,
        ValidatedOvertimeClient() as game_client,
        ValidatedWeatherClient() as weather_client,
    ):
        # Fetch all concurrently
        odds_task = odds_client.fetch_nfl_odds()
        games_task = game_client.fetch_nfl_games()

        # Wait for both
        odds, games = await asyncio.gather(odds_task, games_task)

        return odds, games
```

## Monitoring

### Logging

All clients use Python logging:

```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

# Or configure per module
logging.getLogger('src.data.action_network_client').setLevel(logging.INFO)
```

### Validation Statistics

Check validation logs:

```bash
# View validation logs
cat .claude/logs/validation_*.jsonl

# Get validation statistics (last 24 hours)
python -c "
from .claude.hooks.validation_logger import ValidationLogger
logger = ValidationLogger()
stats = logger.get_failure_stats(hours=24)
print(f'Success rate: {stats[\"success_rate\"]:.1%}')
"
```

## Troubleshooting

### Action Network Issues

**Problem**: Login fails
```python
# Solution: Run in non-headless mode to debug
client = ActionNetworkClient(headless=False)
```

**Problem**: Selectors not working
```
# Solution: Update selectors in action_network_client.py SELECTORS dict
```

### Overtime API Issues

**Problem**: Authentication fails
```
# Check credentials in .env
echo $OV_CUSTOMER_ID
echo $OV_PASSWORD
```

### Weather API Issues

**Problem**: Both weather services fail
```python
# Use fallback mode
async with WeatherClient(prefer_accuweather=False) as client:
    # Tries OpenWeather first
    forecast = await client.get_game_forecast(city, state, time)
```

## Next Steps

1. ✅ Test all clients with your API credentials
2. ✅ Integrate with autonomous agent
3. ⬜ Build historical data storage
4. ⬜ Create automated monitoring
5. ⬜ Add more data sources (injuries, team stats)
6. ⬜ Implement caching layer
7. ⬜ Build dashboard for visualization

## Support

- Check logs in `.claude/logs/`
- Review validation errors in validation logs
- Enable debug logging for detailed output
- Test each client independently before integration

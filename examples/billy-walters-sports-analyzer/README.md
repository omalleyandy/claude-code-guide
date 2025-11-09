# Billy Walters Sports Analyzer - API Integration

Complete API integration for NFL and NCAAF sports analytics with odds, game data, and weather information.

## Overview

This package provides production-ready API clients for:

1. **Action Network** - Live odds data from multiple sportsbooks
2. **Overtime API** - Game schedules, scores, and team statistics
3. **Weather APIs** - AccuWeather and OpenWeather with automatic fallback

All clients include:
- ✅ Async/await support for high performance
- ✅ Rate limiting and exponential backoff
- ✅ Automatic data validation
- ✅ Comprehensive error handling
- ✅ Production-ready logging

## Quick Start

### 1. Installation

```bash
# Install dependencies
uv add playwright pydantic httpx

# Install Playwright browsers
uv run playwright install chromium
```

### 2. Configuration

Create `.env` file with your API credentials:

```bash
# Action Network
ACTION_USERNAME=your_email@example.com
ACTION_PASSWORD=your_password

# Overtime API
OV_CUSTOMER_ID=your_customer_id
OV_PASSWORD=your_password

# Weather APIs
ACCUWEATHER_API_KEY=your_key
OPENWEATHER_API_KEY=your_key
```

### 3. Basic Usage

```python
import asyncio
from src.data.validated_action_network import ValidatedActionNetworkClient

async def main():
    async with ValidatedActionNetworkClient() as client:
        # Fetch and validate NFL odds
        odds = await client.fetch_nfl_odds()

        for game in odds.games:
            print(f"{game['away_team']} @ {game['home_team']}")
            print(f"  Spread: {game['spread']}")

asyncio.run(main())
```

## Features

### Action Network Client

- Web scraping with Playwright
- Automatic login and session management
- Extracts spreads, totals, moneylines
- Supports multiple sportsbooks
- Rate limited to prevent bans

### Overtime API Client

- Game schedules and scores
- Team statistics
- Player data
- Historical data access
- RESTful API integration

### Weather Clients

- Dual-provider redundancy (AccuWeather + OpenWeather)
- Automatic fallback on failure
- Game-time forecasts
- Current conditions
- Normalized data format

### Validation System

All clients integrate with validation hooks:
- Validates odds ranges
- Checks data completeness
- NFL/NCAAF specific rules
- Configurable strict/non-strict modes

## Project Structure

```
src/data/
├── models.py                        # Pydantic data models
├── action_network_client.py         # Action Network scraper
├── validated_action_network.py      # With validation
├── overtime_client.py               # Overtime API client
├── validated_overtime.py            # With validation
├── accuweather_client.py            # AccuWeather API
├── openweather_client.py            # OpenWeather API
├── weather_client.py                # Unified weather client
└── validated_weather.py             # With validation

test_api_clients.py                  # Comprehensive test suite
API_INTEGRATION_GUIDE.md             # Detailed documentation
ACTION_NETWORK_SETUP.md              # Action Network setup guide
```

## Testing

Run the comprehensive test suite:

```bash
# Run all tests
uv run python test_api_clients.py

# Run with pytest
uv run pytest test_api_clients.py -v

# Run specific test
uv run pytest test_api_clients.py::test_action_network_client -v
```

Test suite includes:
1. Action Network basic and validated
2. Overtime API basic and validated
3. AccuWeather client
4. OpenWeather client
5. Unified weather client with fallback
6. Validated weather client
7. Full integration test

## Documentation

- **API_INTEGRATION_GUIDE.md** - Complete integration guide with examples
- **ACTION_NETWORK_SETUP.md** - Detailed Action Network setup
- **CLAUDE.md** - Project-specific development guidelines

## Integration with Autonomous Agent

```python
from src.data.validated_action_network import ValidatedActionNetworkClient
from src.data.validated_weather import ValidatedWeatherClient
from walters_autonomous_agent import WaltersCognitiveAgent

async def analyze_games():
    agent = WaltersCognitiveAgent()

    async with (
        ValidatedActionNetworkClient() as odds_client,
        ValidatedWeatherClient() as weather_client,
    ):
        # Get odds
        odds = await odds_client.fetch_nfl_odds()

        # Analyze each game
        for game in odds.games:
            # Get weather
            weather = await weather_client.get_and_validate_game_forecast(
                city, state, game_time
            )

            # Make decision
            decision = await agent.make_autonomous_decision({
                **game,
                'weather': weather
            })

            if decision['recommendation'] == 'bet':
                print(f"BET: {game['away_team']} @ {game['home_team']}")
```

## Performance

- **Action Network**: ~5-10s per league
- **Overtime API**: ~1-2s per request
- **Weather APIs**: ~1-2s per request
- **Validation**: ~100ms per game
- **Parallel fetching**: Use `asyncio.gather()` for concurrent requests

## Error Handling

All clients include comprehensive error handling:

```python
try:
    odds = await client.fetch_nfl_odds(strict=True)
except ValueError as e:
    # Validation error - data quality issue
    print(f"Validation failed: {e}")
except RuntimeError as e:
    # API error - network or authentication issue
    print(f"API error: {e}")
```

## Rate Limiting

Configurable rate limits to respect API constraints:

```python
# Action Network - 2 seconds between requests
client = ActionNetworkClient(rate_limit_delay=2.0)

# Overtime - 1 second between requests
client = OvertimeAPIClient(rate_limit_delay=1.0)
```

## Retry Logic

Automatic exponential backoff on failures:

```python
# Will retry up to 5 times: 1s, 2s, 4s, 8s, 16s
odds = await client.fetch_nfl_odds(max_retries=5)
```

## Logging

All clients use Python's logging module:

```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

# Or configure specific modules
logging.getLogger('src.data.action_network_client').setLevel(logging.INFO)
```

## Security

- All credentials in environment variables
- Never commit `.env` to version control
- `.env.example` provided as template
- API keys not logged
- Secure password handling

## Monitoring

View validation statistics:

```bash
# Check validation logs
cat .claude/logs/validation_*.jsonl

# Get statistics (requires validation_logger.py)
python -c "
from .claude.hooks.validation_logger import ValidationLogger
logger = ValidationLogger()
stats = logger.get_failure_stats(hours=24)
print(f'Success rate: {stats[\"success_rate\"]:.1%}')
"
```

## Troubleshooting

### Action Network

- **Login fails**: Run with `headless=False` to debug
- **Selectors changed**: Update `SELECTORS` dict in client
- **Rate limited**: Increase `rate_limit_delay`

### Overtime API

- **Auth fails**: Check `OV_CUSTOMER_ID` and `OV_PASSWORD` in `.env`
- **No data**: Verify season and week parameters
- **Timeout**: Increase `timeout` parameter

### Weather APIs

- **Both fail**: Check API keys and rate limits
- **Wrong location**: Verify city/state format
- **Old data**: Check `forecast_time` in response

## Next Steps

1. ✅ Test all clients with your credentials
2. ✅ Integrate with autonomous agent
3. ⬜ Build historical data storage (SQLite/PostgreSQL)
4. ⬜ Create automated monitoring and alerts
5. ⬜ Add more data sources (injuries, team stats)
6. ⬜ Implement caching layer
7. ⬜ Build visualization dashboard

## Support

For issues:
1. Check logs in `.claude/logs/`
2. Review validation errors
3. Enable debug logging
4. Test each client independently
5. Verify API credentials

## License

This is an educational/research tool. Follow responsible gambling principles and respect API terms of service.

## Author

Developed for the Billy Walters Sports Analyzer project following Billy Walters' analytical approach to sports betting.

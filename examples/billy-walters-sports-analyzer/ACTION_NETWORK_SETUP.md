# Action Network Client Setup Guide

## Installation

### 1. Install Dependencies

```bash
# Install Python packages
uv add playwright pydantic

# Install Playwright browsers
uv run playwright install chromium
```

### 2. Set Environment Variables

Add to your `.env` file:

```bash
ACTION_USERNAME=your_email@example.com
ACTION_PASSWORD=your_password
```

### 3. File Structure

Copy the following files to your project:

```
billy-walters-sports-analyzer/
├── src/
│   └── data/
│       ├── __init__.py
│       ├── models.py                        # Pydantic data models
│       ├── action_network_client.py         # Core scraper client
│       └── validated_action_network.py      # Validated wrapper
└── .claude/
    └── hooks/
        └── validate_data.py                 # Validation script
```

## Usage

### Basic Usage

```python
import asyncio
from src.data.action_network_client import ActionNetworkClient

async def main():
    # Create client with environment variables
    async with ActionNetworkClient() as client:
        # Fetch NFL odds
        nfl_odds = await client.fetch_nfl_odds()
        print(f"Fetched {len(nfl_odds)} NFL games")

        # Fetch NCAAF odds
        ncaaf_odds = await client.fetch_ncaaf_odds()
        print(f"Fetched {len(ncaaf_odds)} NCAAF games")

if __name__ == "__main__":
    asyncio.run(main())
```

### With Validation

```python
import asyncio
from src.data.validated_action_network import ValidatedActionNetworkClient

async def main():
    # Create validated client
    async with ValidatedActionNetworkClient() as client:
        # Fetch with strict validation
        try:
            nfl_response = await client.fetch_nfl_odds(strict=True)
            print(f"Valid games: {nfl_response.total_games}")

            for game in nfl_response.games:
                print(f"{game['away_team']} @ {game['home_team']}")
                print(f"  Spread: {game['spread']}")
                print(f"  O/U: {game['over_under']}")

        except ValueError as e:
            print(f"Validation failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Advanced Configuration

```python
# Custom configuration
client = ActionNetworkClient(
    username="custom_user@example.com",  # Override env var
    password="custom_password",           # Override env var
    headless=False,                       # Show browser for debugging
    rate_limit_delay=3.0,                 # Wait 3s between requests
)
```

## Features

### Rate Limiting
- Automatic rate limiting between requests (default: 2 seconds)
- Configurable delay via `rate_limit_delay` parameter
- Prevents API throttling and bans

### Retry Logic
- Automatic retries on failure (default: 3 attempts)
- Exponential backoff: 1s, 2s, 4s
- Configurable via `max_retries` parameter

### Error Handling
- Graceful handling of network errors
- Login failure detection
- Invalid data skipping with logging

### Data Validation
- Validates odds ranges (spread, total, moneyline)
- Checks for missing critical fields
- NFL/NCAAF specific validation rules
- Strict vs. non-strict modes

## Validation Modes

### Strict Mode (Recommended for Production)
```python
# Raises ValueError if any validation fails
response = await client.fetch_nfl_odds(strict=True)
```

### Non-Strict Mode (For Development)
```python
# Logs warnings but continues with invalid data
response = await client.fetch_nfl_odds(strict=False)
```

## Troubleshooting

### Login Failures
```python
# Run in non-headless mode to see browser
client = ActionNetworkClient(headless=False)
```

### Rate Limiting Issues
```python
# Increase delay between requests
client = ActionNetworkClient(rate_limit_delay=5.0)
```

### Selector Changes
If Action Network updates their HTML structure:

1. Inspect the page with browser DevTools
2. Update selectors in `ActionNetworkClient.SELECTORS`
3. Update extraction logic in `_extract_game_row()`

## Data Format

### Game Dictionary Structure
```python
{
    "league": "NFL",                      # or "NCAAF"
    "away_team": "Kansas City Chiefs",
    "home_team": "Philadelphia Eagles",
    "game_time": "Sun 1:00 PM",
    "away_rotation": "301",
    "home_rotation": "302",
    "spread": -2.5,                       # Home team spread
    "spread_odds": -110,                  # American odds
    "over_under": 47.5,
    "total_odds": -110,
    "moneyline_home": -140,
    "moneyline_away": 120,
    "sportsbook": "FanDuel",              # Best odds source
    "timestamp": "2025-11-09T12:00:00",
    "source": "action_network"
}
```

## Integration with Autonomous Agent

```python
from src.data.validated_action_network import ValidatedActionNetworkClient
from walters_autonomous_agent import WaltersCognitiveAgent

async def run_analysis():
    agent = WaltersCognitiveAgent()

    async with ValidatedActionNetworkClient() as odds_client:
        # Fetch current odds
        nfl_response = await odds_client.fetch_nfl_odds()

        # Run agent analysis on each game
        for game_data in nfl_response.games:
            decision = await agent.make_autonomous_decision(game_data)

            if decision['recommendation'] == 'bet':
                print(f"BET RECOMMENDATION: {decision['game_id']}")
                print(f"  Bet type: {decision['bet_type']}")
                print(f"  Confidence: {decision['confidence']}")
                print(f"  Reasoning: {decision['reasoning']}")
```

## Performance

- **Fetch time**: ~5-10 seconds per league (with rate limiting)
- **Memory usage**: ~50MB for browser instance
- **Network**: ~1-2MB per fetch
- **Validation overhead**: ~100ms per game

## Best Practices

1. **Always use async context manager** to ensure browser cleanup
2. **Enable validation** to catch data quality issues early
3. **Set appropriate rate limits** to avoid bans (recommend 2-3 seconds)
4. **Use headless mode in production** for better performance
5. **Log all errors** for monitoring and debugging
6. **Cache results** to minimize API calls during development

## Security

- **Never commit credentials** to version control
- **Use environment variables** for sensitive data
- **Add `.env` to `.gitignore`**
- **Rotate passwords regularly**
- **Monitor for unauthorized access**

## Next Steps

1. Test the client with your Action Network account
2. Verify data extraction accuracy
3. Integrate with your autonomous agent
4. Set up monitoring and alerting
5. Build historical odds tracking database

"""
Data models for sports analytics.

Pydantic models for Game, Team, Odds, Weather, and related data structures.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class League(str, Enum):
    """Supported sports leagues."""

    NFL = "NFL"
    NCAAF = "NCAAF"


class Conference(str, Enum):
    """NCAAF conferences."""

    ACC = "ACC"
    BIG_TEN = "Big Ten"
    BIG_12 = "Big 12"
    PAC_12 = "Pac-12"
    SEC = "SEC"
    AMERICAN = "American"
    MOUNTAIN_WEST = "Mountain West"
    CONFERENCE_USA = "Conference USA"
    MAC = "MAC"
    SUN_BELT = "Sun Belt"
    INDEPENDENT = "Independent"


class Team(BaseModel):
    """Team information."""

    name: str
    abbreviation: str
    league: League
    conference: Conference | None = None
    rotation_number: str | None = None

    @field_validator("abbreviation")
    @classmethod
    def validate_abbreviation(cls, v: str) -> str:
        """Validate team abbreviation format."""
        if not v or len(v) < 2:
            raise ValueError(f"Invalid team abbreviation: {v}")
        return v.upper()


class Stadium(BaseModel):
    """Stadium information."""

    name: str
    city: str
    state: str
    is_dome: bool = False
    surface_type: str | None = None  # grass, turf, etc.


class WeatherConditions(BaseModel):
    """Weather conditions for a game."""

    temperature_f: float | None = None
    wind_speed_mph: float | None = None
    wind_direction: str | None = None
    precipitation_chance: float | None = None  # 0-100
    precipitation_type: str | None = None  # rain, snow, etc.
    humidity: float | None = None  # 0-100
    conditions: str | None = None  # clear, cloudy, etc.
    forecast_time: datetime | None = None

    @field_validator("temperature_f")
    @classmethod
    def validate_temperature(cls, v: float | None) -> float | None:
        """Validate temperature is realistic."""
        if v is not None and not -50 <= v <= 150:
            raise ValueError(f"Unrealistic temperature: {v}F")
        return v

    @field_validator("wind_speed_mph")
    @classmethod
    def validate_wind_speed(cls, v: float | None) -> float | None:
        """Validate wind speed is realistic."""
        if v is not None and not 0 <= v <= 100:
            raise ValueError(f"Unrealistic wind speed: {v} mph")
        return v


class OddsMovement(BaseModel):
    """Odds data with movement tracking."""

    spread: float
    spread_odds: int = -110  # American odds format
    over_under: float
    total_odds: int = -110
    moneyline_home: int | None = None
    moneyline_away: int | None = None
    sportsbook: str
    timestamp: datetime
    opening_spread: float | None = None
    opening_total: float | None = None

    @field_validator("spread")
    @classmethod
    def validate_spread(cls, v: float) -> float:
        """Validate spread is realistic."""
        if not -50 <= v <= 50:
            raise ValueError(f"Unrealistic spread: {v}")
        return v

    @field_validator("over_under")
    @classmethod
    def validate_total(cls, v: float) -> float:
        """Validate total is realistic."""
        if not 20 <= v <= 100:
            raise ValueError(f"Unrealistic total: {v}")
        return v

    @field_validator("spread_odds", "total_odds")
    @classmethod
    def validate_american_odds(cls, v: int) -> int:
        """Validate American odds format."""
        if v == 0:
            raise ValueError("Odds cannot be zero")
        if not -10000 <= v <= 10000:
            raise ValueError(f"Unrealistic odds: {v}")
        return v

    def to_decimal_odds(self, american_odds: int) -> float:
        """Convert American odds to decimal format."""
        if american_odds > 0:
            return (american_odds / 100) + 1
        else:
            return (100 / abs(american_odds)) + 1

    @property
    def spread_decimal(self) -> float:
        """Get spread odds in decimal format."""
        return self.to_decimal_odds(self.spread_odds)

    @property
    def total_decimal(self) -> float:
        """Get total odds in decimal format."""
        return self.to_decimal_odds(self.total_odds)


class Game(BaseModel):
    """Complete game information."""

    game_id: str
    league: League
    home_team: Team
    away_team: Team
    game_date: datetime
    week: int
    stadium: Stadium | None = None
    home_score: int | None = None
    away_score: int | None = None
    odds: OddsMovement | None = None
    weather: WeatherConditions | None = None
    status: str = "scheduled"  # scheduled, in_progress, final, postponed
    is_playoff: bool = False
    is_bowl_game: bool = False

    @field_validator("week")
    @classmethod
    def validate_week(cls, v: int, info) -> int:
        """Validate week number based on league."""
        league = info.data.get("league")
        if league == League.NFL:
            if not 1 <= v <= 22:
                raise ValueError(
                    f"Invalid NFL week: {v} (must be 1-18 regular, 19-22 playoffs)"
                )
        elif league == League.NCAAF:
            if not 0 <= v <= 16:
                raise ValueError(
                    f"Invalid NCAAF week: {v} (0=preseason, 1-15 regular, 16=bowls)"
                )
        return v

    @field_validator("home_score", "away_score")
    @classmethod
    def validate_score(cls, v: int | None) -> int | None:
        """Validate score is realistic."""
        if v is not None and not 0 <= v <= 150:
            raise ValueError(f"Unrealistic score: {v}")
        return v

    @property
    def point_differential(self) -> int | None:
        """Calculate point differential (home - away)."""
        if self.home_score is not None and self.away_score is not None:
            return self.home_score - self.away_score
        return None

    @property
    def total_points(self) -> int | None:
        """Calculate total points scored."""
        if self.home_score is not None and self.away_score is not None:
            return self.home_score + self.away_score
        return None

    def covered_spread(self) -> bool | None:
        """Check if home team covered the spread."""
        if self.point_differential is None or self.odds is None:
            return None
        return self.point_differential + self.odds.spread > 0

    def hit_over(self) -> bool | None:
        """Check if total went over."""
        if self.total_points is None or self.odds is None:
            return None
        return self.total_points > self.odds.over_under


class ActionNetworkResponse(BaseModel):
    """Response from Action Network scraper."""

    league: League
    games: list[dict[str, Any]]
    fetch_time: datetime
    total_games: int

    @field_validator("games")
    @classmethod
    def validate_games(cls, v: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Validate games list is not empty."""
        if not v:
            raise ValueError("Games list cannot be empty")
        return v

    @property
    def game_count(self) -> int:
        """Get number of games."""
        return len(self.games)

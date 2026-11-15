from typing import Final


# Geographic calculations
EARTH_RADIUS_KM: Final[float] = 6371.0088
KM_PER_NAUTICAL_MILE: Final[float] = 1.852
KNOTS_TO_KMH: Final[float] = 1.852


# Flight categories
# Initial application-specific thresholds in hours.
# These are heuristics, not universal aviation definitions.
FLIGHT_DURATION_THRESHOLDS: Final[dict[str, float]] = {
    "short_haul": 3.0,
    "medium_haul": 6.0,
    "long_haul": 12.0,
}


# Recommendation scoring weights
# All weights should add up to 1.0.
DEFAULT_SCORING_WEIGHTS: Final[dict[str, float]] = {
    "aircraft_match": 0.25,
    "duration_match": 0.20,
    "airport_match": 0.15,
    "airline_realism": 0.15,
    "weather_match": 0.10,
    "route_variety": 0.10,
    "scenario_match": 0.05,
}


# Scoring
MAX_RECOMMENDATION_SCORE: Final[float] = 100.0
MIN_RECOMMENDATION_SCORE: Final[float] = 0.0


# Route calculations
# Used for initial estimates only.
# Actual flight planning requires route and wind data.
DEFAULT_ROUTE_DISTANCE_FACTOR: Final[float] = 1.05


# Recommendation diversity
MAX_SAME_DEPARTURE_AIRPORT: Final[int] = 3
MAX_SAME_AIRCRAFT_TYPE: Final[int] = 3

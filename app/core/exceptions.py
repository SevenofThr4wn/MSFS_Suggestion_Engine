class FlightRecommendationError(Exception):
    """Base exception for the recommendation system."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class AircraftNotFoundError(FlightRecommendationError):
    """Raised when the requested aircraft does not exist."""


class AirportNotFoundError(FlightRecommendationError):
    """Raised when the requested airport does not exist."""


class RouteNotFoundError(FlightRecommendationError):
    """Raised when a requested route cannot be found."""


class NoRecommendationsError(FlightRecommendationError):
    """Raised when no candidates satisfy the constraints."""


class AircraftCompatibilityError(FlightRecommendationError):
    """Raised when an aircraft fails compatibility checks."""


class RouteValidationError(FlightRecommendationError):
    """Raised when a route fails validation."""


class ScenarioGenerationError(FlightRecommendationError):
    """Raised when a scenario cannot be generated."""


class ExternalServiceError(FlightRecommendationError):
    """Raised when an external data provider fails."""

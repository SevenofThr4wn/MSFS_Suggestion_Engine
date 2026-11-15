from enum import StrEnum


class AircraftCategory(StrEnum):
    NARROW_BODY = "narrow_body"
    WIDE_BODY = "wide_body"
    REGIONAL_JET = "regional_jet"
    TURBOPROP = "turboprop"
    GENERAL_AVIATION = "general_aviation"
    BUSINESS_JET = "business_jet"
    CARGO = "cargo"
    MILITARY = "military"


class FlightCategory(StrEnum):
    SHORT_HAUL = "short_haul"
    MEDIUM_HAUL = "medium_haul"
    LONG_HAUL = "long_haul"
    ULTRA_LONG_HAUL = "ultra_long_haul"


class FlightPhase(StrEnum):
    PREFLIGHT = "preflight"
    PUSHBACK = "pushback"
    TAXI = "taxi"
    TAKEOFF = "takeoff"
    INITIAL_CLIMB = "initial_climb"
    CLIMB = "climb"
    CRUISE = "cruise"
    DESCENT = "descent"
    APPROACH = "approach"
    LANDING = "landing"
    POSTFLIGHT = "postflight"


class WeatherCondition(StrEnum):
    CLEAR = "clear"
    CLOUDY = "cloudy"
    RAIN = "rain"
    SNOW = "snow"
    THUNDERSTORM = "thunderstorm"
    FOG = "fog"
    WINDY = "windy"
    ICING = "icing"


class FlightDifficulty(StrEnum):
    EASY = "easy"
    MODERATE = "moderate"
    CHALLENGING = "challenging"
    ADVANCED = "advanced"
    EXTREME = "extreme"


class ScenarioType(StrEnum):
    NORMAL = "normal"
    TECHNICAL_FAILURE = "technical_failure"
    ENGINE_FAILURE = "engine_failure"
    MEDICAL_EMERGENCY = "medical_emergency"
    WEATHER_DIVERSION = "weather_diversion"
    FUEL_EMERGENCY = "fuel_emergency"
    PRESSURIZATION_FAILURE = "pressurization_failure"
    HYDRAULIC_FAILURE = "hydraulic_failure"


class EmergencySeverity(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class RecommendationStatus(StrEnum):
    PENDING = "pending"
    VALID = "valid"
    REJECTED = "rejected"
    RANKED = "ranked"

class SuitabilityStatus(StrEnum):
    PASS = "preliminary_pass"
    FAIL = "rejected"
    UNKNOWN = "indeterminate"

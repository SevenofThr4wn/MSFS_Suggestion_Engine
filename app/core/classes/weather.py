from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class WeatherContext:
    """
    Weather observations for an airport.

    Contains available METAR information and any
    warnings associated with that observation.
    """

    icao: str
    available: bool
    category: str | None = None
    wind_speed_kt: float | None = None
    visibility_mi: float | None = None
    observation_time: str | None = None
    raw: str | None = None
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        """Serialize the weather context."""
        return asdict(self)


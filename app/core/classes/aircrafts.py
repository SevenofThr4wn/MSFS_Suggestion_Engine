from dataclasses import dataclass


@dataclass
class AircraftTelemetry:
    latitude: float = 0.0
    longitude: float = 0.0
    altitude_ft: float = 0.0
    ground_speed_kts: float = 0.0
    heading_deg: float = 0.0
    on_ground: bool = True
    parking_brake: bool = True
    engines_running: bool = False
    atc_id: str = ""
    atc_airline: str = ""
    aircraft_title: str = ""

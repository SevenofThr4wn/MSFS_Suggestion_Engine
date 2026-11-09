from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.models.flight_log import FlightLog

class HistoryEngine:
    def __init__(self, session: Session):
        self.session = session

    def evaluate_many(self, routes: list[dict]) -> list[tuple[float, list[str]]]:
        if not routes:
            return []
        airport_codes = {r['departure_icao'] for r in routes} | {r['arrival_icao'] for r in routes}
        logs = self.session.scalars(select(FlightLog).where(FlightLog.departure_icao.in_(airport_codes))).all()
        pair_counts = {}
        aircraft_counts = {}
        for log in logs:
            k = (log.departure_icao, log.arrival_icao)
            pair_counts[k] = pair_counts.get(k, 0) + 1
            aircraft_counts[log.aircraft_id] = aircraft_counts.get(log.aircraft_id, 0) + 1
        result = []
        for r in routes:
            repeats = pair_counts.get((r['departure_icao'], r['arrival_icao']), 0)
            uses = aircraft_counts.get(r['aircraft_id'], 0)
            novelty = max(0.0, 100 - min(repeats * 30, 75) - min(uses * 2, 20))
            notes = [f'Previously flown route {repeats} time(s)', f'Aircraft logged on {uses} flight(s)']
            result.append((round(novelty, 2), notes))
        return result

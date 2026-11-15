import ctypes
import json
import math
import re
import threading
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Set, Tuple

from app.core.classes.aircrafts import AircraftTelemetry
from app.core.classes.airports import StandInfo

try:
    from SimConnect import SimConnect, AircraftRequests, AircraftEvents
    SIMCONNECT_AVAILABLE = True
except ImportError:
    SIMCONNECT_AVAILABLE = False


class AirportProfiler:
    """Handles geographical, regulatory (Schengen/Customs), and airline mappings."""

    SCHENGEN_PREFIXES: Set[str] = {
        "LF", "LS", "ED", "ET", "LO", "EB", "EH", "EL", "LE", "GC",
        "LP", "LI", "LG", "LM", "EK", "EN", "ES", "EF", "EE", "EV",
        "EY", "EP", "LK", "LZ", "LH", "LJ", "LD", "BI", "LR", "LB"
    }
    SCHENGEN_EXCLUDED_ICAOS: Set[str] = {"EKVG", "LXGB", "ENSB"}

    VIRTUAL_TO_REAL_AIRLINE: Dict[str, str] = {
        "BAW": "BAW", "BAV": "BAW", "SHT": "BAW",
        "DLH": "DLH", "DLV": "DLH", "CLH": "DLH",
        "AFR": "AFR", "AFV": "AFR", "HOP": "AFR",
        "KLM": "KLM", "KLV": "KLM", "KLC": "KLM",
        "UAL": "UAL", "AAL": "AAL", "DAL": "DAL",
        "RYR": "RYR", "RYS": "RYR", "EZY": "EZY", "EZS": "EZY", "EJU": "EZY",
        "QFA": "QFA", "QFAV": "QFA", "VOZ": "VOZ", "JST": "JST",
    }

    ALLIANCES: Dict[str, Set[str]] = {
        "STAR": {"DLH", "SWR", "AUA", "SAS", "UAL", "ACA", "ANA", "SIA", "THY", "TAP", "LOT", "ANZ"},
        "SKYTEAM": {"AFR", "KLM", "DAL", "AZA", "ITY", "AEA", "KAL", "AMX", "SVA", "VIR"},
        "ONEWORLD": {"BAW", "AAL", "IBE", "FIN", "QTR", "QFA", "JAL", "CPA", "RJA", "MAS"},
    }

    @classmethod
    def normalize_airline(cls, code: str) -> str:
        clean = re.sub(r"[^A-Z0-9]", "", str(code or "").strip().upper())[:3]
        return cls.VIRTUAL_TO_REAL_AIRLINE.get(clean, clean)

    @classmethod
    def get_alliance(cls, airline_icao: str) -> Optional[str]:
        norm = cls.normalize_airline(airline_icao)
        for alliance, members in cls.ALLIANCES.items():
            if norm in members:
                return alliance
        return None

    @classmethod
    def is_schengen(cls, icao: str) -> bool:
        ic = str(icao or "").strip().upper()
        if len(ic) != 4 or ic in cls.SCHENGEN_EXCLUDED_ICAOS:
            return False
        return ic[:2] in cls.SCHENGEN_PREFIXES

    @classmethod
    def classify_flight_customs(cls, origin_icao: str, dest_icao: str) -> str:
        orig = str(origin_icao or "").strip().upper()
        dest = str(dest_icao or "").strip().upper()
        if len(orig) != 4 or len(dest) != 4:
            return "UNKNOWN"
        if orig[:2] == dest[:2]:
            return "DOMESTIC"
        if cls.is_schengen(orig) and cls.is_schengen(dest):
            return "SCHENGEN"
        return "NON_SCHENGEN"

    @staticmethod
    def infer_stand_terminal(airport_icao: str, stand_name: str) -> str:
        ic = str(airport_icao or "").strip().upper()
        st = str(stand_name or "").strip().upper()
        num_match = re.search(r"(\d+)", st)
        num = int(num_match.group(1)) if num_match else -1

        if ic == "EGKK":
            if st.startswith(("1", "2", "3")) and num < 40:
                return "South Terminal"
            if num >= 45 or st.startswith(("5", "10", "11")):
                return "North Terminal"
        elif ic == "LSZH":
            if st.startswith("A"):
                return "Terminal A (Schengen)"
            if st.startswith(("B", "D")):
                return "Terminal B/D"
            if st.startswith("E"):
                return "Dock E (Non-Schengen)"
        elif ic == "OMDB":
            if st.startswith(("A", "B", "C")):
                return "Terminal 3"
            if st.startswith("D"):
                return "Terminal 1"
            if st.startswith("F"):
                return "Terminal 2"
        elif ic == "YSSY":
            if num in range(1, 38) or st.startswith(("A", "B", "C")):
                return "T1 International"
            if num in range(39, 65):
                return "T2/T3 Domestic"

        prefix_match = re.match(r"^([A-Z]+)", st)
        if prefix_match:
            return f"Concourse {prefix_match.group(1)}"
        return "Main Terminal"




class SimBriefClient:

    API_URL = "https://www.simbrief.com/api/xml.fetcher.php"

    @classmethod
    def fetch_ofp(cls, username: str = "", userid: str = "", timeout: float = 10.0) -> Dict[str, Any]:
        if not username and not userid:
            raise ValueError("Either SimBrief username or userid must be provided.")

        param = f"username={urllib.parse.quote(username)}" if username else f"userid={urllib.parse.quote(str(userid))}"
        url = f"{cls.API_URL}?{param}&json=1"

        req = urllib.request.Request(url, headers={"User-Agent": "FlightOpsBackend/2.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw_bytes = resp.read()
            text = raw_bytes.decode("utf-8", errors="replace")
            return cls.parse_and_validate_ofp(text)

    @classmethod
    def parse_and_validate_ofp(cls, raw_input: str) -> Dict[str, Any]:
        text = str(raw_input or "").strip()
        if not text:
            raise ValueError("Empty SimBrief payload.")

        data: Dict[str, Any] = {}
        if text.startswith("{"):
            data = json.loads(text)
        elif text.startswith("<"):
            data = cls._xml_to_dict(ET.fromstring(text))
        else:
            raise ValueError("Unsupported SimBrief payload format (expected JSON or XML).")

        # Extract core fields
        origin = data.get("origin", {})
        dest = data.get("destination", {})
        general = data.get("general", {})
        aircraft = data.get("aircraft", {})
        atc = data.get("atc", {})

        orig_icao = str(origin.get("icao_code", "")).strip().upper()
        dest_icao = str(dest.get("icao_code", "")).strip().upper()

        if len(orig_icao) != 4 or len(dest_icao) != 4:
            fpl_text = str(atc.get("flightplan_text", ""))
            fpl_orig, fpl_dest = cls._extract_icaos_from_fpl(fpl_text)
            orig_icao = orig_icao if len(orig_icao) == 4 else fpl_orig
            dest_icao = dest_icao if len(dest_icao) == 4 else fpl_dest

        if len(orig_icao) != 4 or len(dest_icao) != 4:
            raise ValueError(f"Invalid route ICAOs extracted: Origin='{orig_icao}', Dest='{dest_icao}'")

        airline_icao = AirportProfiler.normalize_airline(general.get("icao_airline", ""))
        flight_num = str(general.get("flight_number", "")).strip()

        return {
            "ofp_id": str(data.get("params", {}).get("request_id", "")),
            "time_generated": str(data.get("params", {}).get("time_generated", "")),
            "airline_icao": airline_icao,
            "flight_number": flight_num,
            "callsign": f"{airline_icao}{flight_num}" if airline_icao and flight_num else str(atc.get("callsign", "")),
            "origin_icao": orig_icao,
            "origin_name": str(origin.get("name", "")),
            "origin_rwy": str(origin.get("plan_rwy", "")),
            "dest_icao": dest_icao,
            "dest_name": str(dest.get("name", "")),
            "dest_rwy": str(dest.get("plan_rwy", "")),
            "alternate_icao": str(data.get("alternate", {}).get("icao_code", "")).strip().upper(),
            "aircraft_icao": str(aircraft.get("icaocode", "")).strip().upper(),
            "aircraft_reg": str(aircraft.get("reg", "")).strip().upper(),
            "route": str(general.get("route", "")).strip(),
            "cruise_alt": str(general.get("initial_altitude", "")).strip(),
            "cost_index": str(general.get("costindex", "")).strip(),
            "pax_count": int(general.get("passengers", 0) or 0),
            "cargo_kg": float(data.get("weights", {}).get("cargo", 0) or 0),
            "block_fuel_kg": float(data.get("fuel", {}).get("plan_ramp", 0) or 0),
            "customs_type": AirportProfiler.classify_flight_customs(orig_icao, dest_icao),
        }

    @staticmethod
    def _extract_icaos_from_fpl(fpl_text: str) -> Tuple[str, str]:
        orig_match = re.search(r"-([A-Z]{4})\d{4}\b", fpl_text)
        dest_match = re.search(r"\n-([A-Z]{4})\d{4}", fpl_text)
        orig = orig_match.group(1) if orig_match else ""
        dest = dest_match.group(1) if dest_match else ""
        return orig, dest

    @classmethod
    def _xml_to_dict(cls, elem: ET.Element) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for child in elem:
            if len(child) == 0:
                result[child.tag] = child.text or ""
            else:
                result[child.tag] = cls._xml_to_dict(child)
        return result


class GateAllocator:
    """Handles MARS stand conflict detection, wingspan checks, and scoring."""

    EARTH_RADIUS_M = 6371000.0

    @classmethod
    def haversine_m(cls, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
        return 2.0 * cls.EARTH_RADIUS_M * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    @classmethod
    def are_mars_related(cls, stand_a: StandInfo, stand_b: StandInfo) -> bool:
        if stand_a.name == stand_b.name:
            return True

        if stand_a.mars_group and stand_a.mars_group == stand_b.mars_group:
            return True

        dist = cls.haversine_m(stand_a.latitude, stand_a.longitude, stand_b.latitude, stand_b.longitude)
        if dist < 28.0:
            return True

        base_a = re.sub(r"[LRCAB]$", "", stand_a.name.upper())
        base_b = re.sub(r"[LRCAB]$", "", stand_b.name.upper())
        if base_a and base_a == base_b and dist < 55.0:
            return True

        return False

    @classmethod
    def update_occupancy(cls, stands: List[StandInfo], traffic_positions: List[Tuple[float, float]], threshold_m: float = 25.0):
        for stand in stands:
            stand.occupied = False
            for t_lat, t_lon in traffic_positions:
                if cls.haversine_m(stand.latitude, stand.longitude, t_lat, t_lon) <= threshold_m:
                    stand.occupied = True
                    break

        occupied_stands = [s for s in stands if s.occupied]
        for stand in stands:
            if stand.occupied:
                continue
            for occ in occupied_stands:
                if cls.are_mars_related(stand, occ):
                    stand.occupied = True
                    break

    @classmethod
    def select_best_stand(
        cls,
        stands: List[StandInfo],
        airline_icao: str,
        aircraft_wingspan_m: float,
        customs_type: str = "UNKNOWN",
        is_cargo: bool = False,
        is_ga: bool = False,
        prefer_jetway: bool = True,
    ) -> Optional[Tuple[StandInfo, float]]:
        norm_airline = AirportProfiler.normalize_airline(airline_icao)
        alliance = AirportProfiler.get_alliance(norm_airline)

        scored_candidates: List[Tuple[StandInfo, float]] = []

        for stand in stands:
            if stand.occupied:
                continue

            if stand.wingspan_m < (aircraft_wingspan_m - 0.3):
                continue

            if is_cargo and not (stand.is_cargo or stand.is_military):
                continue
            if is_ga and not stand.is_ga:
                continue
            if not is_cargo and not is_ga and (stand.is_cargo or stand.is_ga or stand.is_military):
                continue

            score = 100.0

            stand_airlines = {AirportProfiler.normalize_airline(a) for a in stand.airlines}
            if norm_airline and norm_airline in stand_airlines:
                score += 60.0
            elif alliance and any(AirportProfiler.get_alliance(a) == alliance for a in stand_airlines):
                score += 25.0
            elif not stand_airlines:
                score += 10.0  # Common-use gate

            if stand.is_schengen is not None and customs_type in ("SCHENGEN", "NON_SCHENGEN"):
                want_schengen = (customs_type == "SCHENGEN")
                if stand.is_schengen == want_schengen:
                    score += 35.0
                else:
                    score -= 50.0

            if prefer_jetway and stand.has_jetway:
                score += 20.0
            elif not prefer_jetway and not stand.has_jetway:
                score += 10.0

            excess_span = stand.wingspan_m - aircraft_wingspan_m
            score -= min(excess_span * 0.5, 15.0)

            scored_candidates.append((stand, round(score, 2)))

        if not scored_candidates:
            return None

        scored_candidates.sort(key=lambda item: item[1], reverse=True)
        return scored_candidates[0]


class SimConnectManager:

    MSFS_PROCESS_NAMES = {"flightsimulator.exe", "flightsimulator2024.exe"}

    def __init__(self, poll_interval: float = 0.5):
        self.poll_interval = poll_interval
        self.connected = False
        self.telemetry = AircraftTelemetry()

        self._sm: Optional[Any] = None
        self._aq: Optional[Any] = None
        self._ae: Optional[Any] = None

        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        self._lvar_queue: List[Tuple[str, float]] = []
        self._event_queue: List[Tuple[str, int]] = []
        self._reconnect_delay = 3.0

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name="SimConnectWorker", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3.0)
        self._disconnect()

    def queue_lvar(self, name: str, value: float):
        if not name:
            return
        with self._lock:
            self._lvar_queue.append((str(name), float(value)))

    def queue_event(self, name: str, data: int = 0):
        if not name:
            return
        with self._lock:
            self._event_queue.append((str(name), int(data)))

    def get_telemetry(self) -> AircraftTelemetry:
        with self._lock:
            return AircraftTelemetry(**self.telemetry.__dict__)

    @classmethod
    def is_msfs_running(cls) -> bool:
        """Checks via Windows Toolhelp32 snapshot if MSFS 2020 or 2024 is active."""
        if not hasattr(ctypes, "windll"):
            return False

        TH32CS_SNAPPROCESS = 0x00000002

        class PROCESSENTRY32(ctypes.Structure):
            _fields_ = [
                ("dwSize", ctypes.c_ulong),
                ("cntUsage", ctypes.c_ulong),
                ("th32ProcessID", ctypes.c_ulong),
                ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
                ("th32ModuleID", ctypes.c_ulong),
                ("cntThreads", ctypes.c_ulong),
                ("th32ParentProcessID", ctypes.c_ulong),
                ("pcPriClassBase", ctypes.c_long),
                ("dwFlags", ctypes.c_ulong),
                ("szExeFile", ctypes.c_char * 260),
            ]

        kernel32 = ctypes.windll.kernel32
        snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if snap == -1:
            return False

        try:
            entry = PROCESSENTRY32()
            entry.dwSize = ctypes.sizeof(PROCESSENTRY32)
            if not kernel32.Process32First(snap, ctypes.byref(entry)):
                return False

            while True:
                exe = entry.szExeFile.decode("utf-8", errors="ignore").lower()
                if exe in cls.MSFS_PROCESS_NAMES:
                    return True
                if not kernel32.Process32Next(snap, ctypes.byref(entry)):
                    break
        finally:
            kernel32.CloseHandle(snap)

        return False

    def _connect(self) -> bool:
        if not SIMCONNECT_AVAILABLE or not self.is_msfs_running():
            return False
        try:
            self._sm = SimConnect()
            self._aq = AircraftRequests(self._sm, _time=200)
            self._ae = AircraftEvents(self._sm)
            self.connected = True
            self._reconnect_delay = 3.0
            return True
        except Exception:
            self._disconnect()
            return False

    def _disconnect(self):
        self.connected = False
        if self._sm:
            try:
                self._sm.exit()
            except Exception:
                pass
        self._sm = None
        self._aq = None
        self._ae = None

    def _poll_telemetry(self):
        if not self._aq:
            return
        try:
            lat = self._aq.get("PLANE_LATITUDE")
            lon = self._aq.get("PLANE_LONGITUDE")
            alt = self._aq.get("PLANE_ALTITUDE")
            gs = self._aq.get("GROUND_VELOCITY")
            hdg = self._aq.get("PLANE_HEADING_DEGREES_TRUE")
            on_gnd = self._aq.get("SIM_ON_GROUND")
            brk = self._aq.get("BRAKE_PARKING_POSITION")

            with self._lock:
                if lat is not None:
                    self.telemetry.latitude = float(lat)
                if lon is not None:
                    self.telemetry.longitude = float(lon)
                if alt is not None:
                    self.telemetry.altitude_ft = float(alt)
                if gs is not None:
                    self.telemetry.ground_speed_kts = float(gs)
                if hdg is not None:
                    self.telemetry.heading_deg = float(hdg)
                if on_gnd is not None:
                    self.telemetry.on_ground = bool(int(on_gnd))
                if brk is not None:
                    self.telemetry.parking_brake = bool(int(brk))
        except Exception:
            self._disconnect()

    def _flush_queues(self):
        if not self._aq or not self._ae:
            return

        with self._lock:
            lvars = list(self._lvar_queue)
            events = list(self._event_queue)
            self._lvar_queue.clear()
            self._event_queue.clear()

        for name, val in lvars:
            try:
                self._aq.set(name, val)
            except Exception:
                pass

        for name, data in events:
            try:
                event_fn = self._ae.find(name)
                if event_fn:
                    event_fn(data)
            except Exception:
                pass

    def _run_loop(self):
        while not self._stop_event.is_set():
            if not self.connected:
                if not self._connect():
                    self._stop_event.wait(self._reconnect_delay)
                    self._reconnect_delay = min(self._reconnect_delay * 1.5, 15.0)
                    continue

            if not self.is_msfs_running():
                self._disconnect()
                continue

            self._poll_telemetry()
            self._flush_queues()
            self._stop_event.wait(self.poll_interval)


# ==============================================================================
# 6. UNIFIED FLIGHT OPS COORDINATOR (EXAMPLE USAGE)
# ==============================================================================

class FlightOpsEngine:
    """Orchestrates SimConnect, SimBrief OFPs, Airport Profiling, and Stand Assignment."""

    def __init__(self):
        self.simconnect = SimConnectManager()
        self.current_ofp: Optional[Dict[str, Any]] = None

    def start(self):
        self.simconnect.start()

    def stop(self):
        self.simconnect.stop()

    def load_simbrief_plan(self, username: str) -> Dict[str, Any]:
        self.current_ofp = SimBriefClient.fetch_ofp(username=username)
        return self.current_ofp

    def assign_arrival_gate(
        self,
        airport_stands: List[StandInfo],
        active_traffic_coords: List[Tuple[float, float]],
        aircraft_wingspan_m: float = 35.8,
        prefer_jetway: bool = True,
    ) -> Optional[Dict[str, Any]]:
        if not self.current_ofp:
            raise RuntimeError("No SimBrief OFP loaded.")

        dest_icao = self.current_ofp["dest_icao"]
        airline = self.current_ofp["airline_icao"]
        customs = self.current_ofp["customs_type"]

        # Enrich terminal info if missing
        for st in airport_stands:
            if not st.terminal:
                st.terminal = AirportProfiler.infer_stand_terminal(dest_icao, st.name)

        # Update stand occupancy including MARS overlaps
        GateAllocator.update_occupancy(airport_stands, active_traffic_coords)

        # Score and pick optimal stand
        result = GateAllocator.select_best_stand(
            stands=airport_stands,
            airline_icao=airline,
            aircraft_wingspan_m=aircraft_wingspan_m,
            customs_type=customs,
            prefer_jetway=prefer_jetway,
        )

        if not result:
            return None

        best_stand, score = result
        return {
            "airport": dest_icao,
            "assigned_stand": best_stand.name,
            "terminal": best_stand.terminal,
            "has_jetway": best_stand.has_jetway,
            "customs_zone": customs,
            "match_score": score,
            "coordinates": (best_stand.latitude, best_stand.longitude),
        }
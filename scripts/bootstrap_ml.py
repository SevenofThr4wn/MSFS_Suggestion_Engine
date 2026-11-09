from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd

from app.ml.family_predictor import load_family_model
from app.ml.family_trainer import train_family_model
from app.ml.hybrid_predictor import predict_hybrid_aircraft
from app.ml.predictor import load_model
from app.ml.trainer import train_aircraft_model
from app.schemas.ml import AircraftPredictionRequest
from scripts.build_ml_dataset import build_dataset


BASE_URL = (
    "https://raw.githubusercontent.com/"
    "jpatokal/openflights/master/data"
)

SOURCE_FILES = (
    "airports.dat",
    "airlines.dat",
    "planes.dat",
    "routes.dat",
)


def download_sources(
    directory: Path,
    force: bool = False,
) -> None:
    directory.mkdir(parents=True, exist_ok=True)

    for filename in SOURCE_FILES:
        destination = directory / filename

        if (
            destination.is_file()
            and destination.stat().st_size > 0
            and not force
        ):
            print(f"Existing: {filename}")
            continue

        url = f"{BASE_URL}/{filename}"

        request = Request(
            url,
            headers={
                "User-Agent": "FlightEngine-ML/1.0",
            },
        )

        print(f"Downloading: {filename}")

        temporary = destination.with_name(
            destination.name + ".download"
        )

        try:
            with urlopen(request, timeout=45) as response:
                with temporary.open("wb") as output:
                    while chunk := response.read(1024 * 1024):
                        output.write(chunk)

            if temporary.stat().st_size < 30:
                raise ValueError(
                    f"Downloaded source is empty: {filename}"
                )

            temporary.replace(destination)

        finally:
            temporary.unlink(missing_ok=True)


def validate_dataset(path: Path) -> pd.DataFrame:
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError(
            f"ML dataset is missing or empty: {path}"
        )

    data = pd.read_csv(path)

    required = {
        "airline_icao",
        "departure_icao",
        "arrival_icao",
        "distance_nm",
        "aircraft_icao",
        "source",
        "source_reference",
    }

    missing = required - set(data.columns)

    if missing:
        raise ValueError(
            f"Missing dataset columns: {sorted(missing)}"
        )

    if data.empty:
        raise ValueError(
            "The dataset builder produced zero training rows."
        )

    print(f"Training rows: {len(data):,}")
    print(
        f"Aircraft types: "
        f"{data['aircraft_icao'].nunique():,}"
    )
    print(
        f"Airlines: "
        f"{data['airline_icao'].nunique():,}"
    )

    return data


def smoke_test(data: pd.DataFrame) -> None:
    sample = data.iloc[0]

    request = AircraftPredictionRequest(
        airline_icao=str(sample["airline_icao"]),
        departure_icao=str(sample["departure_icao"]),
        arrival_icao=str(sample["arrival_icao"]),
        distance_nm=float(sample["distance_nm"]),
    )

    load_model.cache_clear()
    load_family_model.cache_clear()

    prediction = predict_hybrid_aircraft(request)

    print("\nHybrid prediction test")
    print(
        f"Route: {request.departure_icao} "
        f"-> {request.arrival_icao}"
    )
    print(f"Airline: {request.airline_icao}")
    print(
        "Predicted family:",
        prediction.predicted_family_id,
    )
    print(
        "Predicted aircraft:",
        prediction.predicted_aircraft_icao,
    )
    print("Agreement:", prediction.model_agreement)
    print("Reliability:", prediction.reliability)


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--skip-download",
        action="store_true",
    )

    parser.add_argument(
        "--force-download",
        action="store_true",
    )

    args = parser.parse_args()

    source = Path("data/openflights")
    dataset = Path("data/ml/aircraft_assignments.csv")

    aircraft_model = Path(
        "models/aircraft_assignment.joblib"
    ).resolve()

    family_model = Path(
        "models/aircraft_family.joblib"
    ).resolve()

    if not args.skip_download:
        download_sources(
            source,
            force=args.force_download,
        )

    print("\nBuilding ML dataset")

    build_dataset(
        source_directory=source,
        output_path=dataset,
    )

    data = validate_dataset(dataset)

    print("\nTraining aircraft-type model")

    aircraft_evaluation = train_aircraft_model(
        dataset_path=dataset,
        output_path=aircraft_model,
    )

    print("\nTraining aircraft-family model")

    family_evaluation = train_family_model(
        dataset_path=dataset,
        output_path=family_model,
    )

    os.environ["FLIGHTENGINE_ML_MODEL_PATH"] = str(
        aircraft_model
    )

    os.environ["FLIGHTENGINE_ML_FAMILY_MODEL_PATH"] = str(
        family_model
    )

    print("\nAircraft model evaluation")
    print(aircraft_evaluation)

    print("\nFamily model evaluation")
    print(family_evaluation)

    smoke_test(data)

    print("\nML training completed.")
    print(f"Aircraft model: {aircraft_model}")
    print(f"Family model: {family_model}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(
            f"ML training failed: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.ml.family_trainer import train_family_model


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train FlightEngine aircraft-family model."
    )

    parser.add_argument(
        "--data",
        type=Path,
        default=Path("data/ml/aircraft_assignments.csv"),
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("models/aircraft_family.joblib"),
    )

    args = parser.parse_args()

    evaluation = train_family_model(
        dataset_path=args.data,
        output_path=args.output,
    )

    print("\nAircraft family model trained successfully.")
    print(json.dumps(evaluation, indent=2))


if __name__ == "__main__":
    main()

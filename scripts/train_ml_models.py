from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.ml.trainer import train_aircraft_model


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train FlightEngine aircraft assignment model."
    )

    parser.add_argument(
        "--data",
        type=Path,
        default=Path(
            "data/ml/aircraft_assignments.csv"
        ),
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "models/aircraft_assignment.joblib"
        ),
    )

    args = parser.parse_args()

    evaluation = train_aircraft_model(
        dataset_path=args.data,
        output_path=args.output,
    )

    print("Aircraft model trained successfully.")
    print(json.dumps(evaluation, indent=2))


if __name__ == "__main__":
    main()

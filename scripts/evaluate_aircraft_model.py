from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.ml.evaluation import evaluate_aircraft_model


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate FlightEngine aircraft ML model."
    )

    parser.add_argument(
        "--data",
        type=Path,
        default=Path("data/ml/aircraft_assignments.csv"),
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/ml"),
    )

    args = parser.parse_args()

    report = evaluate_aircraft_model(
        dataset_path=args.data,
        output_directory=args.output,
    )

    print("\nFlightEngine ML Evaluation")
    print("=" * 48)
    print(
        json.dumps(
            report["summary"],
            indent=2,
        )
    )

    print(f"\nReports saved to: {args.output.resolve()}")


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.ml.evaluation import evaluate_aircraft_model


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate FlightEngine Hybrid ML V2."
    )

    parser.add_argument(
        "--combined",
        type=Path,
        default=Path(
            "data/ml/aircraft_assignments_v2.csv"
        ),
    )

    parser.add_argument(
        "--detailed",
        type=Path,
        default=Path(
            "data/ml/bts_assignments_detailed.csv"
        ),
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/ml/v2"),
    )

    args = parser.parse_args()

    report = evaluate_aircraft_model(
        dataset_path=args.combined,
        detailed_path=args.detailed,
        output_directory=args.output,
    )

    print(
        json.dumps(
            report,
            indent=2,
        )
    )

    print(f"\nReports saved to: {args.output}")


if __name__ == "__main__":
    main()

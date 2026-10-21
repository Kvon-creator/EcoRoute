"""Audit the extracted first VED week without training or inventing labels."""

from collections import Counter
import csv
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "data" / "VED"


def main() -> None:
    sample = ROOT / "extracted" / "VED_171101_week.csv"
    counts = Counter()
    vehicles, fuel_vehicles, fuel_trips = set(), set(), set()
    minimum, maximum = math.inf, -math.inf
    fields = ("Fuel Rate[L/hr]", "MAF[g/sec]", "Vehicle Speed[km/h]",
              "Latitude[deg]", "Longitude[deg]")
    rows = 0
    with sample.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        columns = reader.fieldnames
        for row in reader:
            rows += 1
            vehicles.add(row["VehId"])
            for field in fields:
                try:
                    value = float(row[field])
                except (ValueError, TypeError):
                    continue
                if not math.isfinite(value):
                    continue
                counts[field] += 1
                if field == "Fuel Rate[L/hr]":
                    fuel_vehicles.add(row["VehId"])
                    fuel_trips.add((row["VehId"], row["Trip"]))
                    minimum, maximum = min(minimum, value), max(maximum, value)
                    if value < 0:
                        counts["negative_fuel_rates"] += 1
                    if value == 0:
                        counts["zero_fuel_rates"] += 1
    result = {
        "sample_file": sample.relative_to(ROOT).as_posix(),
        "source_commit": "6baa4963782d515a67d32a5490bd5d11f5d9bf0d",
        "rows": rows, "columns": columns, "vehicles": len(vehicles),
        "finite_value_counts": dict(counts),
        "vehicles_with_finite_fuel_rate": len(fuel_vehicles),
        "vehicle_trip_pairs_with_finite_fuel_rate": len(fuel_trips),
        "fuel_rate_range_liters_per_hour": [minimum, maximum] if fuel_vehicles else None,
        "scope": "First weekly CSV only, not the full dataset. Finite fuel readings are not independently validated ground truth.",
    }
    output = json.dumps(result, indent=2, allow_nan=False) + "\n"
    (ROOT / "sample_inspection.json").write_text(output, encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()

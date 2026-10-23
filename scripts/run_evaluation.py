"""Evaluate 10-20 supplied node pairs once prepared artifacts are available."""

import argparse
import csv
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.dashboard import load_prepared_graph
from src.evaluation import evaluate_pairs
from src.study_area import DEFAULT_GRAPH_PATH


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pairs", type=Path, required=True,
                        help="CSV with origin,destination node-ID columns, 10-20 rows")
    parser.add_argument("--output", type=Path, default=ROOT / "data/processed/route_evaluation.csv")
    args = parser.parse_args()
    try:
        graph, metadata = load_prepared_graph(
            ROOT / DEFAULT_GRAPH_PATH,
            ROOT / "data/processed/fuel_metadata.json",
        )
        ids = {str(node): node for node in graph.nodes}
        if len(ids) != len(graph.nodes):
            raise ValueError("Graph node IDs cannot be mapped unambiguously from CSV.")
        with args.pairs.open(newline="", encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            if not {"origin", "destination"}.issubset(reader.fieldnames or []):
                raise ValueError("Pair CSV needs origin and destination columns.")
            raw_pairs = list(reader)
        if not 10 <= len(raw_pairs) <= 20:
            raise ValueError("Supply 10-20 origin/destination pairs.")
        pairs = []
        for row in raw_pairs:
            if not row.get("origin") or not row.get("destination"):
                raise ValueError("Every pair must specify both node IDs.")
            # Unknown IDs are retained so evaluation reports a failed pair.
            pairs.append((ids.get(row["origin"], row["origin"]),
                          ids.get(row["destination"], row["destination"])))
        rows = evaluate_pairs(graph, pairs)
        for row in rows:
            row.update(model_id=metadata["model_id"], vehicle_profile=metadata["vehicle_profile"],
                       prediction_source=metadata["prediction_source"], graph_sha256=metadata["graph_sha256"])
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        parser.exit(1, f"Evaluation unavailable: {exc}\n")
    successful = sum(row["status"] == "ok" for row in rows)
    print(f"Saved {len(rows)} pairs to {args.output}; {successful} succeeded, {len(rows)-successful} failed.")
    print("Optimizing and evaluating with the same prediction model does not validate real-world fuel savings.")


if __name__ == "__main__":
    main()

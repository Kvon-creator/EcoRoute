"""Build explicitly simulated fuel artifacts for EcoRoute. No VED labels used."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import sys

import joblib
import numpy as np
import osmnx as ox
import sklearn
from sklearn.compose import TransformedTargetRegressor
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.dashboard import load_prepared_graph
from src.evaluation import evaluate_pairs

SEED = 365
MODEL_ID = 'fairview-synthetic-van-hgb-v1'
FEATURES = ['speed_kph', 'grade']
PARAMETERS = dict(mass_kg=3000.0, rolling_coefficient=0.012,
                  drag_area_m2=1.1, air_density_kg_m3=1.2,
                  drivetrain_efficiency=0.25, fuel_energy_j_per_liter=34_200_000.0,
                  idle_liters_per_hour=0.9, gravity_m_s2=9.80665)
SPEEDS = dict(motorway=80, motorway_link=30, trunk=70, trunk_link=30,
              primary=60, primary_link=30, secondary=50, secondary_link=30,
              tertiary=40, tertiary_link=30, residential=30, living_street=15,
              service=20, unclassified=35)


def digest(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def simulated_rate(features, parameters=None):
    """Steady-speed, non-regenerative hypothetical gasoline van; returns L/km.

    Grade is signed rise/run. Downhill braking dissipates excess energy.
    Idle allowance is added at all speeds, including downhill (no fuel cutoff).
    """
    p = PARAMETERS if parameters is None else parameters
    x = np.asarray(features, dtype=float)
    if x.ndim != 2 or x.shape[1] != 2 or not np.isfinite(x).all():
        raise ValueError('Expected finite speed_kph,grade rows.')
    speed, grade = x.T
    if np.any((speed < 15) | (speed > 90) | (abs(grade) > 0.25)):
        raise ValueError('Simulation domain is 15-90 km/h and grades -0.25 to 0.25.')
    angle = np.arctan(grade)
    force = (p['mass_kg'] * p['gravity_m_s2'] *
             (p['rolling_coefficient'] * np.cos(angle) + np.sin(angle)) +
             0.5 * p['air_density_kg_m3'] * p['drag_area_m2'] * (speed / 3.6)**2)
    return (np.maximum(force, 0) * 1000 /
            (p['drivetrain_efficiency'] * p['fuel_energy_j_per_liter']) +
            p['idle_liters_per_hour'] / speed)


def assumed_speed(highway):
    kinds = highway if isinstance(highway, list) else [highway]
    # Multiple classifications use the conservative minimum; unknown defaults 30.
    return float(min(SPEEDS.get(str(kind), 30) for kind in kinds))


def predict_rates(model, features):
    # Validate domain with the simulator before calling the surrogate.
    simulated_rate(features)
    values = np.asarray(model.predict(features), dtype=float)
    if not np.isfinite(values).all() or np.any(values < 0):
        raise ValueError('Model returned invalid simulated fuel rates.')
    return values


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def write_csv(path, rows):
    with path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    root = args.root.resolve()
    processed = root / 'data/processed'
    graph_path = processed / 'fairview.graphml'
    original = processed / 'fairview_gis_only.graphml'
    model_path = root / 'models' / (MODEL_ID + '.joblib')
    model_path.parent.mkdir(parents=True, exist_ok=True)
    if not original.exists():
        # Never back up fuel-modified data as if it were the original GIS input.
        candidate = ox.load_graphml(graph_path)
        if any('fuel_liters' in d for _, _, d in candidate.edges(data=True)):
            raise ValueError('Fuel costs already exist; supply a clean GIS-only source first.')
        shutil.copy2(graph_path, original)
    source_hash = digest(original)
    graph = ox.load_graphml(original)
    edges = sorted(graph.edges(keys=True, data=True), key=lambda e: e[:3])
    features = np.array([[assumed_speed(d.get('highway', 'unknown')), float(d['grade'])]
                         for _, _, _, d in edges])
    simulated_rate(features)  # Reject extrapolation and invalid grades.
    for _, _, _, d in edges:
        if not np.isfinite(float(d['length'])) or float(d['length']) <= 0:
            raise ValueError('Edge lengths must be finite and positive.')

    rng = np.random.default_rng(SEED)
    train = np.column_stack([rng.uniform(15, 90, 8000), rng.uniform(-0.25, 0.25, 8000)])
    test = np.column_stack([rng.uniform(15, 90, 2000), rng.uniform(-0.25, 0.25, 2000)])
    train_y, test_y = simulated_rate(train), simulated_rate(test)
    model = TransformedTargetRegressor(
        regressor=HistGradientBoostingRegressor(max_iter=250, max_leaf_nodes=31,
                    learning_rate=0.08, random_state=SEED),
        func=np.log, inverse_func=np.exp)
    model.fit(train, train_y)
    pred = predict_rates(model, test)
    baseline = np.full(len(test), train_y.mean())
    rates = predict_rates(model, features)
    oracle = simulated_rate(features)
    joblib.dump(dict(model=model, feature_names=FEATURES, target='liters_per_km',
                     model_id=MODEL_ID, prediction_source='simulation-trained',
                     parameters=PARAMETERS, domain=dict(speed_kph=[15,90], grade=[-0.25,0.25])),
                model_path, compress=3)
    # Confirm the exported model is usable independently.
    np.testing.assert_allclose(predict_rates(joblib.load(model_path)['model'], features), rates)
    prediction_rows = []
    for (u, v, key, d), x, rate, reference in zip(edges, features, rates, oracle):
        liters = float(rate * float(d['length']) / 1000)
        d.update(fuel_liters=liters, speed_kph=float(x[0]),
                 speed_source='assumed-road-class-not-observed',
                 fuel_prediction_source='simulation-trained', fuel_model_id=MODEL_ID)
        prediction_rows.append(dict(u=u, v=v, key=key, length_m=float(d['length']),
            grade=float(x[1]), speed_kph=float(x[0]), predicted_liters_per_km=float(rate),
            fuel_liters=liters, simulator_liters=float(reference * float(d['length'])/1000),
            prediction_source='simulation-trained'))
    graph.graph['fuel_prediction_source'] = 'simulation-trained'
    graph.graph['fuel_model_id'] = MODEL_ID
    ox.save_graphml(graph, graph_path)
    metadata = dict(graph_sha256=digest(graph_path), model_id=MODEL_ID,
        vehicle_profile='hypothetical-3000kg-gasoline-delivery-van-v1', fuel_unit='liters',
        prediction_source='simulation-trained', source_gis_graph_sha256=source_hash,
        model_sha256=digest(model_path), model_path=str(model_path.relative_to(root)).replace('\\','/'),
        feature_names=FEATURES, model_target='liters_per_km', seed=SEED,
        vehicle_parameters=PARAMETERS, assumed_speed_kph_by_road_class=SPEEDS,
        unknown_road_speed_kph=30, speed_source='assumed-not-observed',
        limitations=['Not calibrated or validated against measured fuel.',
            'VED is not used for training or validation.',
            'Steady speed; no acceleration, stops, congestion, fuel cutoff, or regeneration.',
            'Endpoint grade is treated as constant per edge; steep-road speeds may be infeasible.',
            'Held-out metrics measure agreement with the same synthetic generator only.',
            'Route savings are internal simulated comparisons, not measured savings.'])
    write_json(processed / 'fuel_metadata.json', metadata)
    loaded, _ = load_prepared_graph(graph_path, processed / 'fuel_metadata.json')
    write_csv(processed / 'simulated_edge_predictions.csv', prediction_rows)
    heldout = [dict(speed_kph=float(x[0]), grade=float(x[1]),
                    simulator_liters_per_km=float(y), predicted_liters_per_km=float(z))
               for x,y,z in zip(test, test_y, pred)]
    write_csv(processed / 'simulation_holdout_predictions.csv', heldout)
    # Pair selection is independent of fuel savings; keep all outcomes.
    pair_rng = np.random.default_rng(SEED + 1)
    nodes = sorted(loaded.nodes)
    pairs = [tuple(int(n) for n in pair_rng.choice(nodes, 2, replace=False)) for _ in range(20)]
    write_csv(processed / 'simulation_evaluation_pairs.csv',
              [dict(origin=u, destination=v) for u,v in pairs])
    results = evaluate_pairs(loaded, pairs)
    for row in results:
        row.update(model_id=MODEL_ID, prediction_source='simulation-trained', graph_sha256=metadata['graph_sha256'])
    write_csv(processed / 'simulation_route_evaluation.csv', results)
    success = [row for row in results if row['status']=='ok']
    report = dict(model_id=MODEL_ID, seed=SEED, training_rows=len(train), heldout_rows=len(test),
        features=FEATURES, sklearn_version=sklearn.__version__, numpy_version=np.__version__,
        joblib_version=joblib.__version__, source_gis_graph_sha256=source_hash,
        graph_sha256=metadata['graph_sha256'], nodes=len(loaded), edges=len(edges),
        simulated_holdout_mae_liters_per_km=float(mean_absolute_error(test_y,pred)),
        simulated_holdout_rmse_liters_per_km=float(np.sqrt(mean_squared_error(test_y,pred))),
        mean_baseline_rmse_liters_per_km=float(np.sqrt(mean_squared_error(test_y,baseline))),
        graph_edge_mae_liters_per_km=float(mean_absolute_error(oracle,rates)),
        pair_selection='20 seeded random distinct-node pairs, no filtering by outcome',
        route_pairs=len(results), successful_pairs=len(success),
        identical_routes=sum(row['identical_routes'] for row in success),
        mean_simulated_savings_percent=float(np.mean([row['predicted_savings_percent'] for row in success])) if success else None,
        limitations=metadata['limitations'])
    write_json(processed / 'simulation_report.json', report)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

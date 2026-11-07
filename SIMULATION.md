# Fairview simulated fuel artifacts

This is an executed simulation fallback, not measured Fairview fuel data or a model trained on VED. It enables the existing EcoRoute dashboard without changing its routing or UI code. The checkpoint PDF has not been updated with these results.

## Files and reproduction

From the EcoRoute repository root with its existing Python 3.12 environment:

```powershell
.\.venv\Scripts\python.exe -m scripts.simulate_fuel
.\.venv\Scripts\python.exe -m scripts.run_evaluation --pairs data/processed/simulation_evaluation_pairs.csv
.\.venv\Scripts\python.exe -m streamlit run app.py
```

The generator requires an existing GIS graph at `data/processed/fairview.graphml`. On first use it preserves its exact bytes as `data/processed/fairview_gis_only.graphml`. Subsequent runs use that backup, never the already-predicted graph. The original GIS report/checksum applies to this backup. To restore GIS-only mode, copy the backup over `fairview.graphml` and remove `fuel_metadata.json`; the GIS preview will then be available. Do not run the GIS-only inspector against the fuel-modified graph expecting its old checksum.

- `data/processed/fairview.graphml`: all 1,652 directed edges have positive `length` in meters, signed `grade`, assumed `speed_kph`, and predicted `fuel_liters` per segment.
- `data/processed/fuel_metadata.json`: required graph checksum, model ID, hypothetical vehicle profile, liters, and `prediction_source: simulation-trained`, plus model checksum, assumptions, and limitations.
- `models/fairview-synthetic-van-hgb-v1.joblib`: dictionary containing fitted scikit-learn `model`, ordered `feature_names`, target units, simulation parameters, and supported feature domain.
- `data/processed/simulated_edge_predictions.csv`: exact `(u,v,key)` IDs, input features, predicted rates/segment liters, and simulator reference liters.
- `data/processed/simulation_holdout_predictions.csv`: all 2,000 held-out synthetic predictions and reference rates.
- `data/processed/simulation_evaluation_pairs.csv`, `simulation_route_evaluation.csv`, `simulation_report.json`: reproducible pairs, all route outcomes, and metrics.

Independent model use:

```python
import joblib
import numpy as np
bundle = joblib.load('models/fairview-synthetic-van-hgb-v1.joblib')
# Ordered features: speed in km/h, signed grade as rise/run (0.05 = 5%).
rate_liters_per_km = bundle['model'].predict(np.array([[40.0, 0.05]]))[0]
segment_liters = rate_liters_per_km * 250.0 / 1000.0
```

Use inputs only within 15-90 km/h and -0.25 to 0.25 grade. The generator validates this domain before inference. The dashboard consumes the prepared graph, not the Joblib file directly. Its current simulation warning remains in place. The small demo artifacts and Joblib model are allowlisted in Git; large raw datasets remain ignored. GraphML and Joblib files preserve exact bytes through `.gitattributes` so checksum validation survives a fresh checkout. No new dependencies are required.

## Simulation assumptions

The hypothetical loaded gasoline van uses 3,000 kg mass, rolling coefficient 0.012, drag area 1.1 m2, air density 1.2 kg/m3, drivetrain efficiency 0.25, fuel energy 34.2 MJ/L, and continuous idle allowance 0.9 L/hour. These are illustrative assumptions, not specifications established for a real delivery vehicle.

At constant speed `v` in m/s and `theta = arctan(grade)`:

```
F = mass*g*(rolling_coefficient*cos(theta) + sin(theta))
    + 0.5*air_density*drag_area*v**2
L/km = max(F, 0)*1000/(efficiency*fuel_energy_J_per_L) + idle_L_per_hour/speed_kph
segment_L = predicted_L_per_km * length_m/1000
```

Downhill excess energy is dissipated; no regeneration or fuel cutoff is modeled. Speeds are assumed by OSM road class, not measured or extracted speed limits: motorway 80, trunk 70, primary 60, secondary 50, tertiary 40, unclassified 35, residential 30, service 20, living street 15 km/h; links and unknown classes 30. Multiple classifications take the minimum. No traffic, acceleration, stopping, engine power limits, payload variation, weather, or full elevation profiles are represented. A constant assumed speed on a steep hill may be physically infeasible.

Road-load concepts are supported by the [FASTSim vehicle modeling documentation](https://natlabrockies.github.io/fastsim/modeling-vehicles/). This implementation is a separate simplified teaching model; FASTSim is not installed, executed, or used to supply labels or parameters.

## Training and observed results

Seed 365 generates 8,000 training and 2,000 separate held-out uniform speed/grade cases over the stated domain. A HistGradientBoostingRegressor learns log(L/km), with exponentiation producing positive rates. Training uses no real graph fuel labels and no VED data. The split assesses interpolation of the synthetic generator, not independent physical accuracy. The graph provides real geometry/length/grade inputs, with assumed speeds.

Executed results: held-out MAE 0.001051 L/km; RMSE 0.001658 L/km; constant-training-mean baseline RMSE 0.296120 L/km. Graph-edge agreement with the simulator: MAE 0.001224 L/km. Runtime versions: scikit-learn 1.9.1, NumPy 2.5.4, Joblib 1.6.0. Use compatible versions when loading the saved estimator; regenerate it when changing environments.

Twenty distinct-endpoint node pairs are sampled independently of fuel outcome with seed 366. All 20 succeed; 18 select identical routes and two differ. Arithmetic mean predicted savings across all pairs is 1.4090%. These are internal simulated comparisons, not measured savings, evidence of local vehicle accuracy, or an achieved 5-15% real-world target. No positive-savings filtering is applied. The CSV retains every pair. The model and simulator share assumptions, so their agreement cannot validate those assumptions. Team review and any required instructor approval of the simulation scope remain separate from creating these artifacts.

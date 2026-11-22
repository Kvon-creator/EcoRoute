# CP3 evaluation and response to Checkpoint 2 feedback

## Main finding

Fuel-aware routing can improve the result inside this simulation, but machine
learning does not improve on calculating the same simple formula directly.
The direct calculation is exact for its own assumptions and was about 125
times faster than the saved ML model in a warm batch of 1,652 edge predictions
on this machine. This is not a general claim that ML is unnecessary for fuel
prediction. A costly simulator or suitable measured training data could change
the tradeoff; neither exists in this proof of concept.

The dashboard now recommends direct simulation and preserves the saved CP2 ML
option. The saved graph, model, metadata, and CP2 result files are unchanged.
All estimates remain explicitly simulated, with no measured-fuel claims.

## Why this model, and what alternatives were tested?

The original model is histogram gradient boosting on log fuel rate. Trees can
represent the nonlinear effect of grade and speed, including the change where
downhill traction demand becomes zero. The log target keeps predictions positive.
Those are reasonable design motivations, not evidence that the original model
was the best choice. Alternatives were not established in CP2; they are tested
now rather than described as work that had already happened.

This study compares:

- A constant training-mean rate: the simplest baseline. Because its rate is
  constant, it chooses shortest distance.
- A regularized linear model fitted to log rates, with feature scaling fitted
  only on training cases: a simpler learned alternative.
- A random forest on log rates: 120 trees, maximum depth 16, at least two samples
  per leaf, seed 365, one worker.
- The exact saved CP2 boosting model: 250 iterations, learning rate 0.08,
  at most 31 leaves, seed 365. It is not silently retrained or replaced.
- Direct simulation: the same equation that generated the labels.

All learned alternatives use the same 8,000 training cases as CP2. Two new,
independent seeded streams provide 2,000 validation cases (seed 2365) and
2,000 test cases (seed 3365). Candidate configurations are fixed in advance.
Validation RMSE selects the candidate; the new test set is not used to select it.
This measures synthetic interpolation only, not transfer to real vehicles.

| Method | New test RMSE (L/km) | Median prediction time for 1,652 edges |
|---|---:|---:|
| constant_mean | 0.297268 | 0.011 ms |
| linear_log | 0.128132 | 0.407 ms |
| random_forest_log | 0.001864 | 29.226 ms |
| existing_hgb | 0.001717 | 9.554 ms |
| direct_simulator | 0.000000 | 0.076 ms |

Random forest narrowly wins validation (0.001682 versus 0.001699 L/km for
boosting), but boosting has a lower error on the separate new test set. We do
not retune or switch that selection after seeing the test result. Neither ML
model beats the direct calculation. Timings are median values from 21 warm
prediction calls, excluding training, file loading, and routing. They depend
on the machine. No parameter sweep or statistical significance is claimed.

Design references: [scikit-learn's gradient boosting documentation](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingRegressor.html)
and [guidance on preventing evaluation leakage](https://scikit-learn.org/stable/common_pitfalls.html).

## Are the routing decisions reliable?

We froze 200 unique directed origin/destination pairs: the original 20 plus
180 additional seeded random pairs (seed 20261122), without selecting for
savings, distance, or terrain. All results and failures are retained. This is
a reproducible sample from this small network, not a representative sample of
real demand. Distance, ascent, descent, and steep-road exposure are saved for
every route in `nominal_routes.csv`. `route_cohorts.csv` compares same-route
and different-route groups; associations do not establish causes.

Every route choice is scored using DIRECT SIMULATOR edge liters, including
the route chosen by ML. This prevents ML from evaluating itself. Regret is
the percentage of extra simulated fuel used compared with the direct
simulator's optimal route for that same trip and parameter setting.

At the original settings:

- All 200 pairs are reachable. Direct simulation differs from shortest distance
  on 59 pairs; 54 pairs save at least 1% of simulated fuel.
- Direct simulation averages 2.5656% savings over shortest distance, including
  all zero-savings cases. This does not replace the original CP2 20-trip result.
- The saved ML model matches the direct route on 198/200 pairs and averages
  2.5646% simulator-scored savings. Its mean regret is 0.001025%, with maximum
  0.10538%. One ML-selected route is slightly worse than shortest distance.
- The validation-selected random forest matches all 200 direct routes in this
  sample. That agreement does not establish agreement on untested trips.
- The linear alternative is worse than shortest distance on 15 trips. Low
  complexity alone does not guarantee reliable route choices.

Exact edge sequences, rather than just rounded totals, determine path agreement.
Equal-cost routes may have different sequences; fuel regret is reported as well.
All percentages are arithmetic means over successful trips, not fuel-weighted
fleet savings. No real-world accuracy, delivery schedule, or emissions claim is made.

## What distinguished the two original trips?

The two CP2 trips where ML differed from shortest distance also match direct
simulation. Their longer alternatives avoid some climbing:

| Original endpoints | Shortest vs alternative distance | Shortest vs alternative climb | Direct-simulator fuel, shortest vs alternative |
|---|---|---|---|
| 6596571591 to 4067941648 | 6.700 vs 6.955 km | 81.13 vs 48.40 m | 0.59464 vs 0.50745 L |
| 169518388 to 169713313 | 7.645 vs 8.400 km | 198.78 vs 138.45 m | 1.12182 vs 0.96527 L |

The first alternative adds about 255 m of distance but avoids about 33 m of
climbing. The second adds about 755 m and avoids about 60 m of climbing; its
share of distance on grades of at least 10% also falls, from 8.13% to 5.36%.
This supports an explanation involving available less-hilly alternatives.
Topology, speed assumptions, and the full formula also matter; we did not
isolate climbing as the sole cause. These simulator fuel totals differ from
CP2 ML-predicted totals because the scoring method is now independent of ML.

On the expanded sample, different-route trips have longer shortest paths on
average (7.62 vs 5.84 km) and more climbing (122.16 vs 93.31 m). A road network
with fewer alternatives will often return the same path even on hilly trips.

## Sensitivity to assumptions

We ran all 27 combinations of mass 2,000/3,000/4,000 kg, speed multipliers
0.8/1.0/1.2, and drivetrain efficiency 0.20/0.25/0.30. These are illustrative
stress-test ranges, not confidence bounds or calibrated vehicle specifications.
The 200 frozen pairs are reused, producing 5,400 comparisons with no failures.
Speed is bounded to the documented 15-90 km/h domain; two edges hit the lower
bound when speeds are reduced. No out-of-domain prediction is silently used.

The direct simulator recalculates edge costs AND reoptimizes routes for every
combination. Separately, the ORIGINAL NOMINAL ML routes are scored under the
new conditions. This is a frozen-deployment robustness check, not a claim that
the ML model accepts weight or efficiency inputs. It does not: it was trained
for the original vehicle. We do not fabricate mass-aware predictions or retrain
against the same evaluation outcomes.

Across scenarios, mean direct savings range from 1.61% to 3.22%; between zero
and 15 of the 200 direct routes change relative to the nominal direct route.
The worst frozen-ML per-trip regret reaches 6.63%, and in one scenario 12 of
its routes are worse than shortest distance. Small nominal error alone therefore
does not guarantee reliable behavior after assumptions change.

Holding the other settings nominal, mean direct savings are 1.92%, 2.57%, and
2.99% at 2,000, 3,000, and 4,000 kg. At speed multipliers 0.8, 1.0, and 1.2
they are 2.64%, 2.57%, and 2.40%. At efficiency 0.20, 0.25, and 0.30 they are
2.74%, 2.57%, and 2.41%. These patterns belong to this simplified model; they
are not physical laws about all vehicles. The fixed idle allowance also means
efficiency is not simply a common multiplier on every edge's full cost.

## GIS checks and interface improvements

Automated GIS checks confirm one strongly connected component and consistency
between signed grades, endpoint elevations, and lengths. Sixty directed edges
have absolute grade at least 15%; `steep_roads_review.csv` identifies them for
inspection. These can include both directions of the same physical road.
Only 146 edges have posted-speed tags (35 mph or 45 mph). Their converted
limits and assumed speeds are listed separately in `posted_speed_review.csv`; the current simulation
continues to use clearly labeled road-class assumptions. A legal maximum is not
an observed travel speed. Automated consistency is not field validation.
Full turn restrictions and detailed elevation profiles remain limitations.

Users can now search road names or enter latitude/longitude instead of knowing
node IDs. Coordinates connect to the nearest saved NODE within 300 m and must
lie inside the node bounding box. This does not find the nearest point on an
edge, a building entrance, or guarantee municipal-boundary coverage. The app
shows the connection distance; that approach distance is excluded from route
totals. Distant/outside points are rejected. Map clicks and address geocoding
are not implemented. There is no geocoding API dependency.

The new Evaluation evidence tab displays the saved comparisons and sensitivity
results, checks the graph checksum, and offers the complete sensitivity CSV.

## Reconciled evaluation counts

Use these exact labels in the next report and video:

| Checkpoint | Count | What is counted |
|---|---:|---|
| CP2 | 8,000 | Synthetic speed/grade training cases |
| CP2 | 2,000 | Held-out synthetic fuel-prediction cases |
| CP2 | 20 | Route pairs; 18 identical, two different |
| CP3 | 2,000 | New model-selection validation cases |
| CP3 | 2,000 | Separate new prediction-test cases |
| CP3 | 200 | Total route pairs, including the original 20 |
| CP3 | 27 | Vehicle/speed/efficiency scenarios |
| CP3 | 5,400 | Pair-scenario route comparisons, not unique trips |

The user confirmed that the submitted video's intended counts match the script
and written report. We have not independently verified a conflicting spoken
number or timestamp and therefore do not invent one. The correction is to
separate prediction examples, route pairs, and repeated scenario evaluations
everywhere. `evaluation_counts.json` is the machine-readable record.
The original CP2 1.41% result used ML's own predicted costs; the new nominal
200-pair results use direct-simulator scoring. Both cohort AND scoring method
must be named when quoting a result.

## Reproduce and inspect

```powershell
.\.venv\Scripts\python.exe -m scripts.evaluate_cp3
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m streamlit run app.py
```

The evaluator runs offline from the prepared graph and model, verifies their
checksums, and writes `data/processed/cp3/`. It does not overwrite the CP2 graph,
model, or reports. Alternative models are compared in memory, not deployed or
silently substituted. Summary provenance records input hashes, seeds, and
Python/library versions. Machine-dependent timing numbers may vary on rerun.
The small CP3 result files are allowlisted in Git; raw VED and USGS downloads
remain ignored. Codex assisted with these evaluations and interface changes.

## Work that still needs independent evidence

Real vehicle calibration remains unavailable. The flagged steep roads, speed
assumptions, and turn restrictions need GIS/field review; software checks cannot
establish their real-world correctness. The team should review this evidence,
address instructor feedback, and demonstrate only work each member actually
completed. Simulation was accepted for this proof of concept in the feedback;
that acceptance does not validate its physical assumptions.

## Verification of the implementation

The full automated suite passed 70 tests, including new cases for simulator-based
regret, exact parallel-edge selection, unreachable trips, negative/zero savings,
coordinate rejection, and switching between saved ML and direct calculations.
An additional smoke check runs the dashboard from a clean local copy containing
only source code, prepared graph/metadata, and CP3 evidence. It uses the existing
Python environment; this is not a claim of testing a clean dependency install
or an independent GitHub clone. No raw VED telemetry or USGS raster is needed
to run the prepared demonstration.

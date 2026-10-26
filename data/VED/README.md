# Vehicle Energy Dataset (VED)

Downloaded from the researchers' repository: https://github.com/gsoh/VED

Pinned revision: `6baa4963782d515a67d32a5490bd5d11f5d9bf0d`.
Original documentation and Apache-2.0 license are retained in `source/`.
`manifest.json` records exact URLs, sizes, Git blob hashes and SHA-256 hashes.

Citation: Geunseob Oh, David J. LeBlanc, and Huei Peng, "Vehicle Energy Dataset
(VED), A Large-scale Dataset for Vehicle Energy Consumption Research," IEEE
Transactions on Intelligent Transportation Systems, 2020.
https://doi.org/10.1109/TITS.2020.3035596

## Local files

- `raw/VED_DynamicData_Part1.7z` and `raw/VED_DynamicData_Part2.7z`: complete
  published telemetry archives, 176,386,679 bytes combined. Both passed Git blob
  verification and `7z t` integrity checks. Together they contain 54 weekly CSV
  files totaling 3,203,555,729 bytes uncompressed.
- `raw/VED_Static_Data_ICE&HEV.xlsx` and `raw/VED_Static_Data_PHEV&EV.xlsx`:
  original vehicle-information spreadsheets; downloaded and hash verified.
- `extracted/VED_*_week.csv`: all 54 weekly telemetry files are extracted
  locally; raw downloads and extracted CSVs are ignored by Git.
- `sample_inspection.json`: first-week column and missing-value audit.

Raw downloads and extracted telemetry are ignored by Git. Keep the source
documentation, license, manifest, and inspection summary tracked. No original
EcoRoute datasets have been replaced.

## Reproduce

Run from the repository root, using the existing Python 3.12 environment:

```powershell
.\.venv\Scripts\python.exe scripts/fetch_ved.py
7z t data/VED/raw/VED_DynamicData_Part1.7z
7z t data/VED/raw/VED_DynamicData_Part2.7z
7z x data/VED/raw/VED_DynamicData_Part1.7z -odata/VED/extracted VED_171101_week.csv -aos
.\.venv\Scripts\python.exe scripts/inspect_ved_sample.py
```

The fetcher uses Python's standard library, reuses matching local files, and
refuses to replace mismatched source files. Extraction requires 7-Zip (`7z` on
PATH); it was available in this environment. To extract all weeks later, omit
the CSV filename and extract each archive into `data/VED/extracted/`. Allow
about 3.2 GB for the expanded data. No model dependencies were added for this
download.

## What the sample establishes

The first week contains 489,414 rows from 258 vehicle IDs. Its `Fuel Rate[L/hr]`
column has 16,073 finite values, covering six vehicle IDs and 22 vehicle/trip
pairs. Of those values, 13,958 are zero; 2,115 are positive. The finite range is
0 to 10.9137144089 liters/hour. Other available fields include timestamps,
latitude, longitude, speed, and MAF. See the machine-readable summary for exact
column names and counts.

These counts apply only to the first week. Neither the rest of the telemetry
nor the spreadsheet contents have been audited. Missing fuel rates are not
zero. Zero rates require interpretation using vehicle type and driving state;
do not discard or reinterpret them without evidence.

## Remaining work before training

This is Ann Arbor personal-vehicle telemetry, not Fairview measurements or
delivery-truck data. Bryce should join vehicle types, identify a usable fuel
label subset, inspect timestamp intervals/gaps, and integrate valid rates over
time to obtain liters. Split by vehicle/trip to avoid leakage. MAF-derived
fuel estimates would require documented conversion assumptions and separate
labeling; they are not direct fuel measurements.

The published columns do not include road grade. A hill-sensitive model needs
additional defensible elevation/map matching or another compatible labeled
source. OBD inputs such as RPM and MAF are unavailable from a static Fairview
road graph and should not become required inference inputs. Training outside
Fairview does not establish local accuracy.

No training, fuel predictions, road-network downloads, or elevation downloads
were performed in this data-acquisition step.

## Fuel-label audit (first-week preliminary)

### Scope and method

This preliminary audit covers only `extracted/VED_171101_week.csv` (the week
beginning 2017-11-01) and the two downloaded static vehicle spreadsheets. It
does not cover the other 53 telemetry weeks. I counted finite fuel-rate values,
grouped them by vehicle and trip, compared fuel readings with vehicle speed,
checked timestamps within trips, and matched fuel-reporting vehicle IDs to the
static vehicle records. These are descriptive checks, not validation of sensor
accuracy or model performance.

### Findings

- The week has 489,414 telemetry rows. Of these, 16,073 have a finite
  `Fuel Rate[L/hr]`; the other 473,341 entries are non-finite (`NaN`). The
  finite values occur in 22 vehicle/trip pairs from six vehicles.
- All six vehicles are listed as PHEV cars in the static spreadsheet. This
  identifies the vehicle class, but does not establish that these vehicles
  represent Fairview delivery vehicles.
- Of the 16,073 finite fuel-rate readings, 2,115 are positive and 13,958 are
  zero. Positive readings occur in only five of the 22 vehicle/trip pairs and
  three of the six vehicles. All 2,115 positive readings coincide with
  nonzero vehicle speed. Of the zero readings, 12,627 coincide with nonzero
  speed and 1,331 with zero speed. Therefore, zero cannot safely be treated as
  missing data or as confirmed zero consumption without checking the VED
  documentation and signal semantics.
- Among consecutive timestamps in these 22 fuel-reporting trips, the median
  interval is 0.7 seconds and the 95th percentile is 1.1 seconds. There are
  504 intervals longer than two seconds; two exceed 30 seconds, and the
  longest is 2,341.7 seconds. Rates are therefore frequent in much of this
  sample, but gaps need an explicit handling rule before integrating rate over
  time. A long gap must not be treated as continuous fuel use without evidence.
- `Fuel Rate[L/hr]` is a rate, not a per-row or per-road-segment quantity.
  Producing segment fuel labels would require a defensible time integration,
  timestamp-gap handling, and GPS-to-road matching. This week-level check has
  not performed those steps or verified how the dataset's fuel-rate signal is
  generated.

### Recommendation and remaining checks

Do not use this first-week summary alone to train or claim a validated
Fairview fuel model. The sparse coverage, many zero readings during motion,
concentration in five trips with positive values, and mismatch between Ann
Arbor PHEV cars and Fairview delivery routes are material limitations. This
does not prove that all VED data is unusable; the full-dataset review below
extends this preliminary first-week check.

### What the VED paper says about fuel rate

The [VED paper, Sections II-B and II-C](https://arxiv.org/abs/1905.02081)
clarifies that `Fuel Rate` is an OEM-reported fuel-consumption estimate read
through OBD-II when the vehicle supplies it; it is not described as a direct
fuel-flow-meter measurement. For vehicles without that signal, the authors
estimate fuel-consumption rate from MAF, fuel trims, and an assumed
stoichiometric air-fuel ratio, or estimate MAF from engine signals. That
fallback is an estimated quantity, not an independent measured label. This
audit counts only the CSV `Fuel Rate[L/hr]` column and has not substituted the
paper's MAF-based estimates.

The paper also describes Fuel Rate as a time-series signal (nominal sampling
time 5 seconds in its signal table). In the extracted files, finite
Fuel Rate timestamps are irregular: across the dataset their median spacing is
0.6 seconds and 95th-percentile spacing is 1.1 seconds. Repeated/carried
values or logging behavior may explain this difference, but this audit has not
established the logger's exact timestamp/hold semantics. Do not infer that
each CSV row is an independent sensor measurement.

## Review of the remaining 53 weeks

### Scope and findings

All 53 remaining extracted weekly CSVs were scanned row by row. Together they
contain 21,947,394 rows. Of these, 880,024 (about 4.0%) have a finite
`Fuel Rate[L/hr]`; 134,433 are positive and 745,591 are zero. The other
21,067,370 are non-finite (`NaN`). Positive readings occur in 372
vehicle/trip pairs. Including the first week, the 54 files contain 896,097
finite readings across 1,357 vehicle/trip pairs, with positive readings in
377 pairs.

The remaining weeks add data but do not make fuel coverage broad across the
fleet: only 13 distinct vehicle IDs have any finite fuel rate in the full
dataset. The static spreadsheets identify 12 as PHEV and one (vehicle 119) as
an ICE 6.7 L turbo-diesel vehicle; approximately 99.8% of all finite readings
are from PHEVs. No finite fuel-rate readings occur for the other listed
vehicles. All 53 weeks have some finite fuel-rate readings, but one week
(`VED_181107_week.csv`) has no positive readings.

Zeros remain ambiguous at full-dataset scale. Of all 759,549 zero-rate
readings across the 54 weeks, 678,440 coincide with nonzero speed and 81,109
with zero speed. There are also 4,705 positive-rate readings at zero speed.
These patterns may reflect engine-on/off and hybrid operating states, signal
behavior, or other conditions; they do not by themselves establish which
values are valid fuel measurements.

For consecutive finite fuel-rate timestamps grouped by week, vehicle, and
trip, the full dataset has 894,740 intervals. There are 22,608 intervals
longer than two seconds, 48 longer than 30 seconds, and the longest is
3,277.2 seconds (about 54.6 minutes). In the 53 newly reviewed weeks alone,
22,104 intervals exceed two seconds, 46 exceed 30 seconds, and the longest
gap is also 3,277.2 seconds. Any rate integration would need a documented
policy for these gaps and trip boundaries.

The largest finite rate is 83.6 L/hr (vehicle 119, a 6.7 L turbo-diesel,
recorded at 68 km/h). Across the full dataset, 127 readings are at least
20 L/hr and 16 are at least 50 L/hr. These high values need validation against
the signal documentation and vehicle behavior; they should not be silently
clipped or discarded. The static spreadsheets contain 384 unique vehicle
IDs, while the source README describes a total fleet of 383; this one-vehicle
count discrepancy should also be reconciled.

### Exploratory trip-rate integration

As a diagnostic only, the finite rate readings were sorted within each
week/vehicle/trip and trapezoid-integrated between consecutive finite
timestamps, converting milliseconds and liters/hour to seconds and liters.
No values were filled across missing readings, no trip endpoints were
extrapolated, and no GPS points were matched to road segments. With an
arbitrary maximum interval of 5 seconds, 889,096 of 894,740 intervals (99.4%)
were included and the resulting sum was 112.3 L. Allowing intervals up to
30 seconds gives 112.34 L; bridging every gap, including intervals over
30 seconds, gives 139.34 L. Thus a small number of very long gaps account for
about 27 L of the all-gap estimate.

These are not validated trip-fuel totals: the 5-second cutoff is a diagnostic
choice, not a confirmed VED rule; the OEM-reported signal and repeated values
may have logging/hold semantics not resolved here; and zero readings are
included despite their ambiguity. The calculation only demonstrates that a
naive integration depends materially on gap handling. It does not create
training labels.

### Recommendation and remaining work

The paper clarifies that the field is an OEM-reported estimate when available,
but the full scan and exploratory integration do not establish sensor
accuracy, explain zero/high readings, or produce validated per-trip or
per-road-segment fuel. The data is from Ann Arbor and is dominated by PHEVs;
even the one diesel vehicle does not establish accuracy for Fairview delivery
routes. VED may support a carefully scoped study of the observed vehicles, but
it is not currently a validated Fairview segment-label source.

Before training, the team would still need to establish signal/logging
semantics, decide defensible zero and gap policies, validate trip totals, and
map-match usable telemetry to roads. Any evaluation split must be grouped by
vehicle or trip. Keep VED results labeled as Ann Arbor vehicle data; they do
not establish Fairview delivery-truck accuracy. If these checks do not support
defensible labels, ask the team whether the documented simulation-trained
fallback is acceptable. No labels were generated and no model was trained in
this review.

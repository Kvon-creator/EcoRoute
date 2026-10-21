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
- `extracted/VED_171101_week.csv`: only the first week has been extracted.
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

This is Ann Arbor personal-vehicle telemetry, not Asheville measurements or
delivery-truck data. Bryce should join vehicle types, identify a usable fuel
label subset, inspect timestamp intervals/gaps, and integrate valid rates over
time to obtain liters. Split by vehicle/trip to avoid leakage. MAF-derived
fuel estimates would require documented conversion assumptions and separate
labeling; they are not direct fuel measurements.

The published columns do not include road grade. A hill-sensitive model needs
additional defensible elevation/map matching or another compatible labeled
source. OBD inputs such as RPM and MAF are unavailable from a static Asheville
road graph and should not become required inference inputs. Training outside
Asheville does not establish local accuracy.

No training, fuel predictions, road-network downloads, or elevation downloads
were performed in this data-acquisition step.

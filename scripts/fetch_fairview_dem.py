"""Download the USGS raster already referenced by EcoRoute and verify its MD5.

Run from the project root: python -m scripts.fetch_fairview_dem
The large raster stays ignored; source metadata and SHA-256 are recorded.
"""

import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
NAME = "USGS_13_n36w083_20171114.tif"
URL = f"https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/13/TIFF/historical/n36w083/{NAME}"
TARGET = ROOT / "data/USGS/raw" / NAME
MANIFEST = ROOT / "data/USGS/fairview_dem_source.json"


def digest(path, algorithm):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, algorithm).hexdigest()


def main():
    with urlopen(Request(URL, method="HEAD"), timeout=30) as response:
        headers = response.headers
        size = int(headers["Content-Length"])
        source_md5 = base64.b64decode(headers["x-amz-meta-md5chksum"], validate=True).hex()
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    if not TARGET.exists():
        partial = TARGET.with_suffix(".tif.part")
        print(f"Downloading {NAME}: {size:,} bytes", flush=True)
        with urlopen(URL, timeout=60) as response, partial.open("wb") as stream:
            while block := response.read(1024 * 1024):
                stream.write(block)
        if partial.stat().st_size != size or digest(partial, "md5") != source_md5:
            raise ValueError("Downloaded raster failed source size/MD5 verification; partial file retained.")
        partial.replace(TARGET)
    if TARGET.stat().st_size != size or digest(TARGET, "md5") != source_md5:
        raise ValueError("Existing raster does not match source size/MD5; it was not overwritten.")
    metadata_url = URL.removesuffix(".tif") + ".xml"
    with urlopen(metadata_url, timeout=30) as response:
        metadata_bytes = response.read()
    xml = ET.fromstring(metadata_bytes)
    if xml.findtext(".//altunits") != "meters":
        raise ValueError("USGS metadata does not confirm elevations in meters.")
    metadata_target = ROOT / "data/USGS/fairview_dem_metadata.xml"
    metadata_target.write_bytes(metadata_bytes)
    manifest = {
        "source_url": URL, "local_path": TARGET.relative_to(ROOT).as_posix(),
        "size_bytes": size, "source_md5": source_md5,
        "sha256": digest(TARGET, "sha256"), "source_etag": headers.get("ETag"),
        "source_last_modified": headers.get("Last-Modified"),
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "metadata_url": metadata_url,
        "metadata_path": metadata_target.relative_to(ROOT).as_posix(),
        "metadata_sha256": hashlib.sha256(metadata_bytes).hexdigest(),
        "elevation_unit": xml.findtext(".//altunits"),
        "vertical_datum": xml.findtext(".//altdatum"),
        "publication_date": xml.findtext(".//pubdate"),
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Verified raster. Source manifest: {MANIFEST}", flush=True)


if __name__ == "__main__":
    main()

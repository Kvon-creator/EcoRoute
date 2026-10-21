"""Fetch the original VED release, verifying Git blob IDs and recording SHA-256.

Run from any directory with Python 3.12. Uses only the standard library.
Existing matching files are reused; existing mismatched files are not replaced.
"""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen


COMMIT = "6baa4963782d515a67d32a5490bd5d11f5d9bf0d"
ROOT = Path(__file__).resolve().parents[1] / "data" / "VED"
FILES = (
    ("Data/VED_DynamicData_Part1.7z", 82723769, "047f71f8e9d7282d14bb3b94a2113b663e3c2b15"),
    ("Data/VED_DynamicData_Part2.7z", 93662910, "100798b2149fcd0d6f7ab555361001def7e36f91"),
    ("Data/VED_Static_Data_ICE&HEV.xlsx", 21193, "337898103e1239aa3c1a46200d823e5d20a42039"),
    ("Data/VED_Static_Data_PHEV&EV.xlsx", 9763, "04228e4037204cff6010ee1e425a1aa9cc8e6bb7"),
    ("LICENSE", 11346, "b15b72576c09c4ab38f96790a46e573cc57d71d9"),
    ("README.md", 3044, "780198a62846431e460cd423ab52b75e1ad70dda"),
)


def hashes(path: Path, size: int) -> tuple[str, str]:
    blob = hashlib.sha1(f"blob {size}\0".encode())
    sha256 = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            blob.update(block)
            sha256.update(block)
    return blob.hexdigest(), sha256.hexdigest()


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    records = []
    for source, size, expected_blob in FILES:
        name = Path(source).name
        target = ROOT / ("raw" if source.startswith("Data/") else "source") / name
        target.parent.mkdir(parents=True, exist_ok=True)
        url = f"https://raw.githubusercontent.com/gsoh/VED/{COMMIT}/{quote(source, safe='/')}"
        if not target.exists():
            partial = target.with_suffix(target.suffix + ".part")
            print(f"Downloading {name} ({size:,} bytes)...", flush=True)
            request = Request(url, headers={"User-Agent": "EcoRoute-data-fetch/1.0"})
            try:
                with urlopen(request, timeout=60) as response, partial.open("wb") as stream:
                    for block in iter(lambda: response.read(1024 * 1024), b""):
                        stream.write(block)
                if partial.stat().st_size != size or hashes(partial, size)[0] != expected_blob:
                    raise ValueError(f"Source size or Git blob hash mismatch: {name}")
                partial.replace(target)
            finally:
                partial.unlink(missing_ok=True)
        blob, sha256 = hashes(target, size)
        if target.stat().st_size != size or blob != expected_blob:
            raise ValueError(f"Existing file does not match source: {target}")
        print(f"Verified {name}", flush=True)
        records.append({
            "source_path": source, "local_path": target.relative_to(ROOT).as_posix(),
            "url": url, "size_bytes": size, "git_blob_sha1": blob, "sha256": sha256,
        })
    manifest = {
        "repository": "https://github.com/gsoh/VED", "commit": COMMIT,
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "license": "Apache-2.0; original license retained in source/LICENSE",
        "files": records,
    }
    (ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

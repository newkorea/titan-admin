#!/usr/bin/env python3
import argparse
import os
import sys
import tarfile
import tempfile
import shutil
from pathlib import Path

try:
    import requests
except Exception:
    print("ERROR -> requests not installed in this venv. Install and retry.")
    sys.exit(2)

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / 'data'
DEST_PATH = DATA_DIR / 'GeoLite2-ASN.mmdb'

DOWNLOAD_URL_TGZ = (
    "https://download.maxmind.com/app/geoip_download?"
    "edition_id=GeoLite2-ASN&license_key={license_key}&suffix=tar.gz"
)


def fetch_mmdb(license_key: str, dest_path: Path) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    url = DOWNLOAD_URL_TGZ.format(license_key=license_key)
    print(f"INFO -> Downloading GeoLite2-ASN from: {url}")
    with tempfile.TemporaryDirectory() as tmpdir:
        tgz_path = Path(tmpdir) / 'geolite2-asn.tgz'
        with requests.get(url, stream=True, timeout=60) as r:
            if r.status_code != 200:
                print(f"ERROR -> Download failed: HTTP {r.status_code} {r.text[:200]}")
                sys.exit(1)
            with open(tgz_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        # Extract and locate mmdb
        with tarfile.open(tgz_path, 'r:gz') as tf:
            tf.extractall(tmpdir)
        # Search for GeoLite2-ASN.mmdb
        mmdb_path = None
        for root, dirs, files in os.walk(tmpdir):
            for name in files:
                if name == 'GeoLite2-ASN.mmdb':
                    mmdb_path = Path(root) / name
                    break
            if mmdb_path:
                break
        if not mmdb_path:
            print("ERROR -> Extracted archive did not contain GeoLite2-ASN.mmdb")
            sys.exit(1)
        shutil.copy2(mmdb_path, dest_path)
        print(f"INFO -> Saved ASN database to {dest_path}")


def main():
    parser = argparse.ArgumentParser(description='Fetch GeoLite2-ASN mmdb into data directory')
    parser.add_argument('--license-key', dest='license_key', default=os.environ.get('MAXMIND_LICENSE_KEY', ''), help='MaxMind license key (or set env MAXMIND_LICENSE_KEY)')
    parser.add_argument('--dest', dest='dest', default=str(DEST_PATH), help='Destination mmdb path')
    args = parser.parse_args()

    if not args.license_key:
        print('ERROR -> Missing MaxMind license key. Set MAXMIND_LICENSE_KEY env or pass --license-key <KEY>.')
        print('NOTE  -> You need a free MaxMind account and agree to GeoLite2 EULA to download.')
        sys.exit(1)

    dest_path = Path(args.dest)
    fetch_mmdb(args.license_key, dest_path)


if __name__ == '__main__':
    main()

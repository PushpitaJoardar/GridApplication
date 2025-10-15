#!/usr/bin/env python3
"""
Create one folder per cell from a GeoJSON file.

Input:  /mnt/data/Grid_metric.geojson
Output: /mnt/data/GridCells/cell_<cell_id>/
"""

import json
import os
from pathlib import Path

# -------- Configuration --------
INPUT_FILE = Path("/datassd4_8tb/p2t4_common_data/pushpita/GridApplication/Grid_metric.geojson")
OUTPUT_ROOT = Path("/datassd4_8tb/p2t4_common_data/datassd4_8tb/p2t4_common_data/Grid_folder")   # parent directory for all folders
KEY_NAME = "cell_id"   # change to "cell_no" if your file uses that field name
# --------------------------------

def main():
    # Load GeoJSON
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"GeoJSON not found at {INPUT_FILE}")
    print(f"[INFO] Reading GeoJSON from {INPUT_FILE}")
    data = json.loads(INPUT_FILE.read_text())
    features = data.get("features", [])
    print(f"[INFO] Found {len(features)} features")

    # Ensure output directory exists
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    created = 0
    missing_id = 0

    for i, feat in enumerate(features):
        props = feat.get("properties", {})
        cell_id = props.get(KEY_NAME)
        if cell_id is None:
            missing_id += 1
            cell_id = i  # fallback if missing
        folder_name = f"cell_{cell_id}"
        folder_path = OUTPUT_ROOT / folder_name
        folder_path.mkdir(exist_ok=True)
        created += 1

        # Optional: write this feature's geometry into its folder as GeoJSON
        single_feat = {
            "type": "FeatureCollection",
            "features": [feat]
        }
        single_path = folder_path / f"{folder_name}.geojson"
        single_path.write_text(json.dumps(single_feat))
        
        if created % 1000 == 0:
            print(f"[PROGRESS] {created} folders created...")

    print(f"[DONE] Created {created} folders in {OUTPUT_ROOT}")
    if missing_id:
        print(f"[WARN] {missing_id} features had no '{KEY_NAME}', used index instead.")

if __name__ == "__main__":
    main()

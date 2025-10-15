#!/usr/bin/env python3
"""
Scan the root grid folder and list which cell_<id> folders contain a visits_bucket0.csv file.

Usage:
  python find_cells_with_csv.py --root /path/to/Grid_folder [--bucket-id 0] [--out summary.csv]
"""

import argparse
from pathlib import Path
import csv

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path, help="Root folder containing cell_<id> subfolders.")
    parser.add_argument("--bucket-id", type=int, default=0, help="Bucket id to look for (default 0).")
    parser.add_argument("--out", type=Path, default=None, help="Optional path to save summary CSV.")
    args = parser.parse_args()

    pattern = f"visits_bucket{args.bucket_id}.csv"
    root = args.root

    if not root.exists():
        raise FileNotFoundError(f"Root folder not found: {root}")

    found = []
    missing = []

    print(f"[INFO] Scanning {root} for '{pattern}' ...")
    for cell_dir in sorted(root.glob("cell_*")):
        if not cell_dir.is_dir():
            continue
        csv_path = cell_dir / pattern
        if csv_path.exists():
            # extract numeric ID (e.g., "cell_12345" → 12345)
            try:
                cell_id = int(cell_dir.name.replace("cell_", ""))
            except ValueError:
                cell_id = cell_dir.name
            found.append(cell_id)
        else:
            missing.append(cell_dir.name)

    print(f"[INFO] Found {len(found)} folders containing {pattern}.")
    if missing:
        print(f"[INFO] {len(missing)} folders missing the file.")

    # Show a few examples
    print("Example cell_ids with file:", found[:10])

    if args.out:
        print(f"[INFO] Writing summary to {args.out}")
        with args.out.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["cell_id"])
            for cid in found:
                w.writerow([cid])

    print("[DONE]")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Convert a metric (UTM) grid GeoJSON to CSV with centroids and (optionally) lon/lat.

Input:
  /mnt/data/Grid_metric.geojson  (features should have cell_id,row,col,area_m2,utm_crs)

Output:
  /mnt/data/Grid_metric.csv

Columns:
  cell_id,row,col,area_m2,centroid_x_m,centroid_y_m,lon,lat
"""

import json
import re
from pathlib import Path
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry
from pyproj import CRS, Transformer
import csv
import sys

IN_PATH = Path("/datassd4_8tb/p2t4_common_data/datassd4_8tb/p2t4_common_data/Grid_folder/cell_229735/cell_229735.geojson")
OUT_PATH = Path("/datassd4_8tb/p2t4_common_data/pushpita/GridApplication/cell_229735.csv")

def parse_epsg(crs_str: str) -> int | None:
    """Extract an EPSG integer from strings like 'EPSG:32611' or 'epsg:32733'."""
    if not crs_str:
        return None
    m = re.search(r"epsg\s*:\s*(\d+)", crs_str, flags=re.IGNORECASE)
    if m:
        return int(m.group(1))
    # Sometimes CRS.to_string() may return 'WGS 84 / UTM zone 11N'—not ideal to parse.
    return None

def get_utm_from_features(features):
    """Find a usable UTM EPSG from feature properties (assumes all share same CRS)."""
    for f in features:
        props = f.get("properties", {}) or {}
        epsg = parse_epsg(str(props.get("utm_crs", "")))
        if epsg:
            return epsg
    return None

def centroid_xy(geom: BaseGeometry) -> tuple[float, float]:
    c = geom.centroid
    return float(c.x), float(c.y)

def main():
    if not IN_PATH.exists():
        print(f"ERROR: input not found: {IN_PATH}", file=sys.stderr)
        sys.exit(1)

    data = json.loads(IN_PATH.read_text())
    features = data.get("features", [])
    if not features:
        print("ERROR: no features in GeoJSON.", file=sys.stderr)
        sys.exit(1)

    # Determine UTM CRS (for lon/lat conversion)
    utm_epsg = get_utm_from_features(features)
    to_wgs = None
    if utm_epsg:
        try:
            to_wgs = Transformer.from_crs(CRS.from_epsg(utm_epsg), CRS.from_epsg(4326), always_xy=True)
        except Exception as e:
            print(f"WARNING: could not build transformer from EPSG:{utm_epsg} -> 4326: {e}", file=sys.stderr)
            to_wgs = None
    else:
        print("WARNING: 'utm_crs' not found or unparsable in properties; lon/lat will be blank.", file=sys.stderr)

    rows_written = 0
    with OUT_PATH.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["cell_id", "row", "col", "area_m2", "centroid_x_m", "centroid_y_m", "lon", "lat"])

        for i, feat in enumerate(features):
            props = feat.get("properties", {}) or {}
            geom = shape(feat.get("geometry", {}))

            # core fields (tolerate missing props)
            cell_id = props.get("cell_id", i)
            row_idx = props.get("row", None)
            col_idx = props.get("col", None)

            # area: use stored value if present, else compute
            area_m2 = props.get("area_m2", None)
            if area_m2 is None:
                try:
                    area_m2 = float(geom.area)
                except Exception:
                    area_m2 = ""

            # centroids in metric coords
            try:
                cx, cy = centroid_xy(geom)
            except Exception:
                cx, cy = "", ""

            # lon/lat via transform (optional)
            lon = lat = ""
            if to_wgs is not None and cx != "" and cy != "":
                try:
                    lon, lat = to_wgs.transform(cx, cy)
                except Exception:
                    lon = lat = ""

            w.writerow([cell_id, row_idx, col_idx, area_m2, cx, cy, lon, lat])
            rows_written += 1

    print(f"Done. Wrote {rows_written} rows to {OUT_PATH}")

if __name__ == "__main__":
    main()

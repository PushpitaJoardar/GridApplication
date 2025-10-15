#!/usr/bin/env python3
"""
Map agent trajectory points (lat/longitude) to grid cells and write a CSV per cell_id.

Inputs:
  --parquet  : Parquet path with columns (agent, timestamp, latitude, longitude)
  --grid     : Grid GeoJSON (either WGS84 or metric UTM). If metric, properties should include utm_crs like 'EPSG:32654'.
  --out-root : Root directory that already contains subfolders named by cell_id (e.g., /.../cell_123/)
  --bucket-id: Constant to attach to each output row (e.g., 0)

Output per cell_id:
  <out-root>/cell_<cell_id>/visits_bucket<bucket_id>.csv

Output columns:
  agent, latitude, longitude, timestamp, cell_id, bucket_id
"""

import argparse
import json
import re
from pathlib import Path

import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from pyproj import CRS

def parse_epsg_from_props(gdf: gpd.GeoDataFrame) -> int | None:
    """Extract EPSG from a 'utm_crs' string in properties (e.g., 'EPSG:32654')."""
    if "utm_crs" not in gdf.columns:
        return None
    series = gdf["utm_crs"].dropna().astype(str)
    if series.empty:
        return None
    m = re.search(r"epsg\s*:\s*(\d+)", series.iloc[0], flags=re.IGNORECASE)
    return int(m.group(1)) if m else None

def ensure_grid_crs(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Set CRS if missing. If metric geojson with 'utm_crs' in properties, apply that EPSG; else assume WGS84."""
    if gdf.crs:
        return gdf
    epsg = parse_epsg_from_props(gdf)
    if epsg:
        return gdf.set_crs(CRS.from_epsg(epsg))
    return gdf.set_crs("EPSG:4326")

def find_time_column(df: pd.DataFrame) -> str:
    """Pick the best time column name given common variants."""
    for cand in ("timestamp", "time", "datetime", "date_time", "ts"):
        if cand in df.columns:
            return cand
    raise ValueError("No time-like column found. Expected one of: timestamp, time, datetime, date_time, ts")

def read_parquet_any(path: Path) -> pd.DataFrame:
    """Read parquet using whichever engine is available (pyarrow or fastparquet)."""
    try:
        return pd.read_parquet(path, engine="pyarrow")
    except Exception:
        try:
            return pd.read_parquet(path, engine="fastparquet")
        except Exception as e:
            raise RuntimeError(
                f"Failed to read parquet {path}. Install pyarrow or fastparquet. Original error: {e}"
            )

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parquet", required=True, type=Path,
                    help="Path to parquet with (agent, timestamp, latitude, longitude).")
    ap.add_argument("--grid", required=True, type=Path,
                    help="Path to grid GeoJSON (WGS84 or metric with utm_crs prop).")
    ap.add_argument("--out-root", required=True, type=Path,
                    help="Root folder that contains subfolders like cell_<cell_id>/")
    ap.add_argument("--bucket-id", type=int, default=0, help="Bucket id to attach to rows (default 0).")
    ap.add_argument("--grid-id-field", default="cell_id", help="Grid id field name (default 'cell_id').")
    # Match your parquet schema defaults:
    ap.add_argument("--agent-id-field", default="agent", help="Agent id field name (default 'agent').")
    ap.add_argument("--latitude-field", default="latitude", help="Latitude field name (default 'latitude').")
    ap.add_argument("--longitude-field", default="longitude", help="Longitude field name (default 'longitude').")
    ap.add_argument("--output-filename", default=None,
                    help="CSV filename inside each cell folder. Default: visits_bucket<B>.csv")
    args = ap.parse_args()

    # --- Load grid ---
    print(f"[INFO] Reading grid: {args.grid}")
    grid = gpd.read_file(args.grid)
    grid = ensure_grid_crs(grid)

    if args.grid_id_field not in grid.columns:
        raise KeyError(f"Grid id field '{args.grid_id_field}' not found in grid attributes. Columns: {list(grid.columns)}")

    # Keep only id + geometry to lighten the sjoin
    grid = grid[[args.grid_id_field, "geometry"]].copy()

    # --- Load agents parquet ---
    print(f"[INFO] Reading trajectories parquet: {args.parquet}")
    df = read_parquet_any(args.parquet)

    # Validate columns
    for col in (args.agent_id_field, args.latitude_field, args.longitude_field):
        if col not in df.columns:
            raise KeyError(f"Expected column '{col}' in parquet. Found columns: {list(df.columns)}")
    time_col = find_time_column(df)

    # --- Build points GeoDataFrame in WGS84 then reproject to grid CRS if needed ---
    print("[INFO] Building point GeoDataFrame...")
    pts = gpd.GeoDataFrame(
        df[[args.agent_id_field, time_col, args.latitude_field, args.longitude_field]].copy(),
        geometry=gpd.points_from_xy(df[args.longitude_field], df[args.latitude_field]),
        crs="EPSG:4326"
    )
    if grid.crs is None:
        grid = grid.set_crs("EPSG:4326")
    if pts.crs != grid.crs:
        print(f"[INFO] Reprojecting points to grid CRS: {grid.crs.to_string() if grid.crs else grid.crs}")
        pts = pts.to_crs(grid.crs)

    # --- Spatial join: point within polygon (cell) ---
    print("[INFO] Spatial join (points → cells)...")
    joined = gpd.sjoin(pts, grid, predicate="within", how="inner")

    if joined.empty:
        print("[WARN] No points fell inside any grid cells. Nothing to write.")
        return

    # Normalize cell id field name and add bucket id
    joined["cell_id"] = joined[args.grid_id_field]
    joined["bucket_id"] = args.bucket_id

    # --- Prepare output columns in the requested order ---
    out_cols = [args.agent_id_field, args.latitude_field, args.longitude_field, time_col, "cell_id", "bucket_id"]

    # --- Write CSV per cell folder ---
    out_name = args.output_filename or f"visits_bucket{args.bucket_id}.csv"
    print(f"[INFO] Writing per-cell CSVs to: {args.out_root}/cell_<id>/{out_name}")
    args.out_root.mkdir(parents=True, exist_ok=True)

    count_cells = 0
    count_rows = 0
    for cell_id, sub in joined.groupby("cell_id", sort=True):
        folder = args.out_root / f"cell_{cell_id}"
        folder.mkdir(parents=True, exist_ok=True)
        out_csv = folder / out_name

        out_df = sub[out_cols].copy()
        # Sort by time (optional)
        out_df = out_df.sort_values(by=time_col)

        write_header = not out_csv.exists()
        out_df.to_csv(out_csv, mode="a", header=write_header, index=False)

        count_cells += 1
        count_rows += len(out_df)

    print(f"[DONE] Wrote {count_rows} rows across {count_cells} cell CSVs.")

if __name__ == "__main__":
    main()

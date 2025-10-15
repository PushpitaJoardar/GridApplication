#!/usr/bin/env python3
"""
Create a 50 m x 50 m grid over an AOI and CLIP edge cells for full coverage.
Includes detailed print statements for progress monitoring.
"""

import json, math, time
from pathlib import Path
from shapely.geometry import shape, mapping, Polygon, MultiPolygon, box
from shapely.ops import unary_union
from shapely.prepared import prep
from pyproj import CRS, Transformer


def load_aoi(path: Path):
    print(f"[INFO] Loading AOI from: {path}")
    data = json.loads(path.read_text())
    if data.get("type") == "FeatureCollection":
        geoms = [shape(f["geometry"]) for f in data["features"] if f.get("geometry")]
        geom = unary_union(geoms)
    elif data.get("type") == "Feature":
        geom = shape(data["geometry"])
    else:
        geom = shape(data)
    print(f"[INFO] AOI loaded successfully. Geometry type: {geom.geom_type}")
    return geom


def best_utm(lon, lat):
    zone = int((lon + 180)//6) + 1
    epsg = 32600 + zone if lat >= 0 else 32700 + zone
    print(f"[INFO] Selected UTM zone {zone}, EPSG:{epsg}")
    return CRS.from_epsg(epsg)


def project_poly(geom, transformer):
    if isinstance(geom, Polygon):
        ext_x, ext_y = transformer.transform(*zip(*geom.exterior.coords))
        interiors = []
        for ring in geom.interiors:
            ix, iy = transformer.transform(*zip(*ring.coords))
            interiors.append(list(zip(ix, iy)))
        return Polygon(list(zip(ext_x, ext_y)), interiors)
    elif isinstance(geom, MultiPolygon):
        return MultiPolygon([project_poly(p, transformer) for p in geom.geoms])
    else:
        raise TypeError("AOI must be Polygon or MultiPolygon")


def to_wgs_geom(geom, transformer):
    if isinstance(geom, Polygon):
        ext_x, ext_y = transformer.transform(*zip(*geom.exterior.coords))
        interiors = []
        for ring in geom.interiors:
            ix, iy = transformer.transform(*zip(*ring.coords))
            interiors.append(list(zip(ix, iy)))
        return Polygon(list(zip(ext_x, ext_y)), interiors)
    elif isinstance(geom, MultiPolygon):
        return MultiPolygon([to_wgs_geom(p, transformer) for p in geom.geoms])
    else:
        raise TypeError("Expected Polygon or MultiPolygon")


def main():
    AOI_PATH = Path("/datassd4_8tb/p2t4_common_data/pushpita/GridApplication/aoi.geojson")
    OUT_PREFIX = Path("/datassd4_8tb/p2t4_common_data/pushpita/GridApplication/Grid")
    CELL = 100.0

    t0 = time.time()
    aoi_wgs = load_aoi(AOI_PATH)
    cent = aoi_wgs.centroid
    utm = best_utm(cent.x, cent.y)
    to_utm = Transformer.from_crs(4326, utm, always_xy=True)
    to_wgs = Transformer.from_crs(utm, 4326, always_xy=True)

    print("[INFO] Projecting AOI to UTM coordinates...")
    aoi_m = project_poly(aoi_wgs, to_utm)
    aoi_prep = prep(aoi_m)
    print("[INFO] AOI projection complete.")

    minx, miny, maxx, maxy = aoi_m.bounds
    start_x = math.floor(minx / CELL) * CELL
    start_y = math.floor(miny / CELL) * CELL
    cols = int(math.ceil((maxx - start_x) / CELL))
    rows = int(math.ceil((maxy - start_y) / CELL))
    print(f"[INFO] Grid bounds: {cols} cols x {rows} rows (approx {cols*rows} cells)")

    features_metric, features_wgs84 = [], []
    cell_id = 0
    checkpoint = max(1, rows // 20)  # print every 5% of rows

    for r in range(rows):
        if r % checkpoint == 0:
            print(f"[PROGRESS] Processing row {r+1}/{rows} ({(r/rows)*100:.1f}%)")
        y0 = start_y + r * CELL
        for c in range(cols):
            x0 = start_x + c * CELL
            cell = box(x0, y0, x0 + CELL, y0 + CELL)
            if not aoi_prep.intersects(cell):
                continue
            inter = cell.intersection(aoi_m)
            if inter.is_empty:
                continue

            features_metric.append({
                "type": "Feature",
                "properties": {"cell_id": cell_id, "row": r, "col": c,
                               "utm_crs": utm.to_string(), "area_m2": float(inter.area)},
                "geometry": mapping(inter)
            })
            inter_w = to_wgs_geom(inter, to_wgs)
            features_wgs84.append({
                "type": "Feature",
                "properties": {"cell_id": cell_id, "row": r, "col": c,
                               "area_m2": float(inter.area)},
                "geometry": mapping(inter_w)
            })
            cell_id += 1

    print(f"[INFO] Clipping complete — {cell_id} total cells inside AOI.")
    print("[INFO] Writing GeoJSON outputs...")

    out_metric = Path(f"{OUT_PREFIX}_metric.geojson")
    out_wgs84 = Path(f"{OUT_PREFIX}_wgs84.geojson")
    out_metric.write_text(json.dumps({"type": "FeatureCollection", "features": features_metric}))
    out_wgs84.write_text(json.dumps({"type": "FeatureCollection", "features": features_wgs84}))

    print(f"[DONE] Metric GeoJSON saved to {out_metric}")
    print(f"[DONE] WGS84 GeoJSON saved to {out_wgs84}")
    print(f"[INFO] Total runtime: {(time.time() - t0):.1f} seconds.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Analog Atlas - Earth data pipeline (Microsoft Planetary Computer)
=================================================================

Pulls measured values for every Earth site in Analog Atlas and writes
`earth_sites_measured.json`. Open the app, click "Load measured data",
and choose that file: the estimated numbers are replaced by measured ones.

What it measures (all through the free Planetary Computer STAC API, no key):

  Dimension            Dataset (collection id)                     How
  -------------------  ------------------------------------------  ---------------------------------------------
  Air pressure  (P)    NASADEM (nasadem); Copernicus DEM           Median elevation in a ~3 km box, converted
                       GLO-30 (cop-dem-glo-30) outside 56S-60N     with the standard-atmosphere formula
  Roughness     (R)    same DEM                                    Mean slope in the box; 25 deg or more = 1.0
  Mean temp     (T)    MODIS LST 8-day v6.1 (modis-11A2-061),      Mean of all valid day+night land-surface
  Day-night     (dT)   Terra + Aqua                                temps for one year; dT = mean day - mean night
  Precipitation (W)    TerraClimate (terraclimate)                 Mean annual total, 1991-2020
  Illumination  (L)    computed from latitude                      Fraction of the year in polar day or night
  (context only)       ESA WorldCover 2021 (esa-worldcover)        % bare ground, snow/ice, vegetation in ~2 km box

Not covered here (left as curated estimates in the app): ice/permafrost (I),
dust (D) and geology tags (G). See README for the datasets that would fill them.

Install (in a fresh environment - see README; Anaconda users should use conda):
    conda create -n atlas -c conda-forge python=3.12 rasterio xarray zarr fsspec adlfs numpy pystac-client planetary-computer
    conda activate atlas

Run:
    python earth_pipeline.py                       # all sites, MODIS year 2023
    python earth_pipeline.py --year 2022
    python earth_pipeline.py --sites lonar,dallol  # just a few sites
    python earth_pipeline.py --modis-step 2        # every 2nd MODIS composite (faster)
"""
import argparse, json, math, sys, datetime as dt
from concurrent.futures import ThreadPoolExecutor

import numpy as np

STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"

# id, name, lat, lon  - must match the ids in the app
SITES = [
    ("lonar", "Lonar Crater", 19.98, 76.51),
    ("dallol", "Dallol / Danakil Depression", 14.24, 40.30),
    ("lut", "Lut Desert yardangs (Kalut)", 30.40, 58.30),
    ("qaidam", "Qaidam Basin (Dalangtan)", 38.60, 91.90),
    ("ojos", "Ojos del Salado high Puna", -27.11, -68.54),
    ("haughton", "Haughton Crater, Devon Island", 75.38, -89.68),
    ("dryvalleys", "McMurdo Dry Valleys", -77.50, 161.80),
    ("yungay", "Yungay, Atacama", -24.08, -69.93),
    ("lanzarote", "La Corona lava tube", 29.16, -13.43),
    ("cotm", "Craters of the Moon", 43.42, -113.52),
    ("riotinto", "Rio Tinto", 37.72, -6.55),
    ("bockfjorden", "Bockfjorden volcanoes", 79.44, 13.33),
    ("maunakea", "Mauna Kea summit", 19.82, -155.47),
    ("axelheiberg", "Lost Hammer spring, Axel Heiberg", 79.42, -90.75),
    ("ngari", "Ngari salt lakes", 32.50, 80.10),
    ("kamil", "Kamil Crater", 22.02, 26.09),
    ("salda", "Lake Salda", 37.55, 29.68),
    ("hanksville", "Hanksville badlands (MDRS)", 38.41, -110.79),
    ("pinacate", "Pinacate volcanic field", 31.77, -113.50),
]

# ----------------------------------------------------------------- pure helpers
def pressure_kpa(elev_m):
    """International Standard Atmosphere: pressure at elevation (valid to ~11 km)."""
    return 101.325 * (1 - 2.25577e-5 * elev_m) ** 5.25588


def roughness_index(mean_slope_deg):
    """Map mean slope to the app's 0-1 roughness index (25 deg or steeper = 1)."""
    return float(min(1.0, max(0.0, mean_slope_deg / 25.0)))


def illumination_extremes(lat):
    """Fraction of the year the sun never sets or never rises at this latitude."""
    n = 0
    for d in range(365):
        decl = -23.44 * math.cos(2 * math.pi * (d + 10) / 365)
        if abs(lat) >= 90 - abs(decl):
            n += 1
    return n / 365


def mean_slope_deg(z, res_x_m, res_y_m):
    gy, gx = np.gradient(z.astype("float64"), res_y_m, res_x_m)
    return float(np.degrees(np.arctan(np.hypot(gx, gy))).mean())


# ------------------------------------------------------------- raster reading
def read_box(href, lon, lat, half_m):
    """Read a square window of ~2*half_m metres around (lon, lat). Returns (masked array, res_m)."""
    import rasterio
    from rasterio import warp, windows
    with rasterio.open(href) as src:
        xs, ys = warp.transform("EPSG:4326", src.crs, [lon], [lat])
        x, y = xs[0], ys[0]
        if src.crs.is_geographic:
            dx = half_m / (111320 * max(0.05, math.cos(math.radians(lat))))
            dy = half_m / 110540
            res_m = (abs(src.res[0]) * 111320 * math.cos(math.radians(lat)), abs(src.res[1]) * 110540)
        else:
            dx = dy = half_m
            res_m = (abs(src.res[0]), abs(src.res[1]))
        win = windows.from_bounds(x - dx, y - dy, x + dx, y + dy, src.transform)
        win = win.round_offsets().round_lengths()
        if win.width < 1 or win.height < 1:
            win = windows.Window(win.col_off, win.row_off, max(1, win.width), max(1, win.height))
        arr = src.read(1, window=win, boundless=True, masked=True)
        return arr, res_m


def first_item(catalog, collection, lon, lat, **kw):
    items = list(catalog.search(collections=[collection],
                                intersects={"type": "Point", "coordinates": [lon, lat]},
                                max_items=1, **kw).items())
    return items[0] if items else None


# ------------------------------------------------------------- per dataset
def terrain(catalog, lon, lat):
    """Elevation, pressure, slope from NASADEM (56S-60N) or Copernicus DEM elsewhere."""
    for coll, asset, label in (("nasadem", "elevation", "NASADEM (NASA)"),
                               ("cop-dem-glo-30", "data", "Copernicus DEM GLO-30 (ESA)")):
        item = first_item(catalog, coll, lon, lat)
        if item is None:
            continue
        z, res = read_box(item.assets[asset].href, lon, lat, half_m=1500)
        z = np.ma.masked_less(z, -500)
        if z.count() < 10:
            continue
        elev = float(np.ma.median(z))
        slope = mean_slope_deg(z.filled(elev), res[0], res[1])
        return {"elev": elev, "P": pressure_kpa(elev), "slope": slope,
                "R": roughness_index(slope), "label": label}
    raise RuntimeError("no DEM tile found")


def lst(catalog, lon, lat, year, step):
    """Mean surface temperature and day-night difference from MODIS 8-day LST."""
    items = list(catalog.search(collections=["modis-11A2-061"],
                                intersects={"type": "Point", "coordinates": [lon, lat]},
                                datetime=f"{year}-01-01/{year}-12-31").items())
    items = items[::step]
    if not items:
        raise RuntimeError("no MODIS LST items")

    read_errors = []
    def one(args):
        item, key = args
        try:
            a, _ = read_box(item.assets[key].href, lon, lat, half_m=1500)
            a = np.ma.masked_equal(a, 0)  # 0 = fill
            return key, (float(a.mean()) * 0.02 - 273.15) if a.count() else None
        except Exception as ex:
            read_errors.append(f"{type(ex).__name__}: {ex}")
            return key, None

    jobs = [(it, k) for it in items for k in ("LST_Day_1km", "LST_Night_1km")]
    with ThreadPoolExecutor(16) as ex:
        res = list(ex.map(one, jobs))
    day = [v for k, v in res if k == "LST_Day_1km" and v is not None]
    night = [v for k, v in res if k == "LST_Night_1km" and v is not None]
    if not day or not night:
        if read_errors:  # every read failed: report the real cause, not "cloud"
            raise RuntimeError(f"could not read MODIS files ({len(read_errors)} failures), first: {read_errors[0]}")
        raise RuntimeError("MODIS returned no valid pixels (cloud/polar night)")
    d, n = float(np.mean(day)), float(np.mean(night))
    return {"T": (d + n) / 2, "dT": d - n, "day": d, "night": n,
            "n_day": len(day), "n_night": len(night), "n_items": len(items)}


_TC = None
def precip(catalog, lon, lat):
    """Mean annual precipitation 1991-2020 from TerraClimate (monthly, ~4 km)."""
    global _TC
    import xarray as xr
    if _TC is None:
        coll = catalog.get_collection("terraclimate")
        last = None
        # Planetary Computer has changed this metadata over time: try each published form.
        for key in ("zarr-abfs", "zarr-https"):
            asset = coll.assets.get(key)
            if asset is None:
                continue
            ef = asset.extra_fields
            opts = ef.get("xarray:storage_options") or (
                {"account_name": "cpdataeuwest"} if asset.href.startswith(("az://", "abfs://")) else {})
            kw = dict(ef.get("xarray:open_kwargs") or {})
            kw.pop("storage_options", None)
            try:
                _TC = xr.open_zarr(asset.href, storage_options=opts or None, **kw)["ppt"]
                break
            except Exception as ex:
                last = ex
        if _TC is None:
            raise RuntimeError(f"could not open TerraClimate ({last}); assets: {list(coll.assets)}")
    ppt = _TC.sel(time=slice("1991-01-01", "2020-12-31"))
    box = ppt.sel(lat=slice(lat + 0.1, lat - 0.1), lon=slice(lon - 0.1, lon + 0.1))
    if box.sizes.get("lat", 0) == 0:  # latitude may be stored ascending
        box = ppt.sel(lat=slice(lat - 0.1, lat + 0.1), lon=slice(lon - 0.1, lon + 0.1))
    monthly = box.mean(dim=["lat", "lon"], skipna=True).values
    if np.all(np.isnan(monthly)):
        raise RuntimeError("TerraClimate has no land pixels here")
    return {"W": float(np.nanmean(monthly) * 12)}


WC_CLASSES = {10: "tree", 20: "shrub", 30: "grass", 40: "crop", 50: "built", 60: "bare",
              70: "snow_ice", 80: "water", 90: "wetland", 95: "mangrove", 100: "moss_lichen"}
def worldcover(catalog, lon, lat):
    """Land-cover fractions from ESA WorldCover 2021 (10 m) in a ~2 km box."""
    item = first_item(catalog, "esa-worldcover", lon, lat)
    if item is None:
        raise RuntimeError("no WorldCover tile")
    a, _ = read_box(item.assets["map"].href, lon, lat, half_m=1000)
    vals, counts = np.unique(a.compressed(), return_counts=True)
    tot = counts.sum() or 1
    frac = {WC_CLASSES.get(int(v), str(v)): round(float(c) / tot, 3) for v, c in zip(vals, counts)}
    veg = sum(frac.get(k, 0) for k in ("tree", "shrub", "grass", "crop", "wetland", "mangrove"))
    return {"bare": frac.get("bare", 0) + frac.get("moss_lichen", 0),
            "snow_ice": frac.get("snow_ice", 0), "vegetated": round(veg, 3), "classes": frac}


# ------------------------------------------------------------- main
def process(catalog, site, year, step):
    sid, name, lat, lon = site
    out = {"values": {}, "sources": {}, "extra": {}, "errors": []}
    v, s, e = out["values"], out["sources"], out["extra"]

    v["L"] = round(illumination_extremes(lat), 3)
    s["L"] = "Computed from latitude (fraction of year in polar day or polar night)"

    try:
        t = terrain(catalog, lon, lat)
        v["P"], v["R"] = round(t["P"], 2), round(t["R"], 2)
        s["P"] = f"{t['label']} elevation -> standard atmosphere"
        s["R"] = f"{t['label']} mean slope ({t['slope']:.1f} deg) / 25 deg"
        e["elevation_m"], e["mean_slope_deg"] = round(t["elev"]), round(t["slope"], 1)
    except Exception as ex:
        out["errors"].append(f"terrain: {ex}")

    try:
        m = lst(catalog, lon, lat, year, step)
        v["T"], v["dT"] = round(m["T"], 1), round(m["dT"], 1)
        s["T"] = s["dT"] = f"MODIS LST 8-day v6.1 (Terra+Aqua), {year}, ~3 km mean"
        e["lst_day_c"], e["lst_night_c"] = round(m["day"], 1), round(m["night"], 1)
        e["lst_obs"] = {"day": m["n_day"], "night": m["n_night"], "composites": m["n_items"]}
    except Exception as ex:
        out["errors"].append(f"MODIS LST: {ex}")

    try:
        v["W"] = round(precip(catalog, lon, lat)["W"], 1)
        s["W"] = "TerraClimate mean annual precipitation, 1991-2020"
    except Exception as ex:
        out["errors"].append(f"TerraClimate: {ex}")

    try:
        e["worldcover"] = worldcover(catalog, lon, lat)
    except Exception as ex:
        out["errors"].append(f"WorldCover: {ex}")

    return sid, out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--year", type=int, default=2023, help="MODIS year (default 2023)")
    ap.add_argument("--sites", help="comma-separated site ids (default: all)")
    ap.add_argument("--modis-step", type=int, default=1, help="use every Nth 8-day composite")
    ap.add_argument("--out", default="earth_sites_measured.json")
    a = ap.parse_args()

    import pystac_client, planetary_computer
    print(f"Python: {sys.executable}")
    try:
        import rasterio, affine
        print(f"numpy {np.__version__} | rasterio {rasterio.__version__} | affine {affine.__version__}\n")
    except Exception as ex:
        print(f"! Package problem: {ex}\n  Make a fresh environment (see README).")
    catalog = pystac_client.Client.open(STAC_URL, modifier=planetary_computer.sign_inplace)

    wanted = set(a.sites.split(",")) if a.sites else None
    sites = [s for s in SITES if not wanted or s[0] in wanted]
    result = {"generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
              "modis_year": a.year, "pipeline": "earth_pipeline.py", "sites": {}}

    for i, site in enumerate(sites, 1):
        print(f"[{i}/{len(sites)}] {site[1]} ...", flush=True)
        sid, out = process(catalog, site, a.year, a.modis_step)
        result["sites"][sid] = out
        vals = ", ".join(f"{k}={v}" for k, v in out["values"].items())
        print(f"    {vals}")
        for err in out["errors"]:
            print(f"    ! {err}")

    with open(a.out, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\nWrote {a.out}. In Analog Atlas, click 'Load measured data' and choose this file.")


if __name__ == "__main__":
    sys.exit(main())

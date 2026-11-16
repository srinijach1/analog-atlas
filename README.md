# Analog Atlas: Earth data pipeline

`earth_pipeline.py` uses Microsoft Planetary Computer to pull measured values for the 19 Earth sites in Analog Atlas. It writes `earth_sites_measured.json`, which you load into the app.

## Run it (about 10–30 minutes for all sites)

If you have Anaconda (recommended):

```bash
conda create -n atlas -c conda-forge python=3.12 rasterio xarray zarr fsspec adlfs numpy pystac-client planetary-computer
conda activate atlas
```

Without Anaconda: `python -m venv venv`, activate it, then
`pip install pystac-client planetary-computer rasterio xarray zarr fsspec adlfs numpy`.
Don't mix the two: pip-installing into Anaconda's base Python breaks numpy/rasterio.
The script prints which Python it's using on the first line; it should be inside `atlas` (or `venv`), not `/opt/anaconda3/bin`.

```bash
python earth_pipeline.py                 # all sites, MODIS year 2023
python earth_pipeline.py --sites lonar,dallol   # quick test first
python earth_pipeline.py --modis-step 2  # twice as fast, half the MODIS composites
```

Then open Analog Atlas, click **Load measured data** and choose `earth_sites_measured.json`. Measured values show a filled dot ●; estimates show a hollow dot ○.

You don't need a key or sign-in: the Planetary Computer STAC API and data are public.

## What each dataset fills

| App dimension | Dataset | Collection id | Provider |
|---|---|---|---|
| Mean surface temp, day–night swing | MODIS Land Surface Temperature 8-day v6.1 (Terra + Aqua) | `modis-11A2-061` | NASA |
| Air pressure (from elevation), roughness (from slope) | NASADEM | `nasadem` | NASA |
| Same, for sites outside 56°S–60°N (Svalbard, Devon, Axel Heiberg, Dry Valleys) | Copernicus DEM GLO-30 | `cop-dem-glo-30` | ESA |
| Precipitation | TerraClimate (1991–2020 mean) | `terraclimate` | Univ. of Idaho |
| Ground cover (context only, not scored) | ESA WorldCover 2021 | `esa-worldcover` | ESA |
| Illumination extremes | Computed from latitude | — | — |

## Still estimates, and what would replace them

| Dimension | Earth | Moon | Mars |
|---|---|---|---|
| Ice / permafrost | MODIS snow cover (`modis-10A2-061`, on Planetary Computer); NSIDC permafrost maps | LRO LEND/LAMP, Chandrayaan-1 M³ (PDS) | SWIM ice maps, swim.psi.edu |
| Dust | MERRA-2 dust (NASA GES DISC, Earthdata login) | — | Mars Climate Database dust opacity |
| Geology | EMIT minerals (NASA Earthdata), USGS maps | LRO / Kaguya (PDS, JAXA DARTS) | CRISM (PDS), OMEGA (ESA PSA) |
| Temperature / pressure | (done above) | LRO Diviner (PDS Geosciences) | Mars Climate Database, www-mars.lmd.jussieu.fr |

## Known limitations (worth saying in your presentation)

- **MODIS overpasses happen at fixed times** (~10:30/22:30 for Terra, ~13:30/01:30 for Aqua), so the day–night swing is somewhat smaller than the true daily max − min.
- **Clouds and polar night leave gaps.** At polar sites, winter has no daytime readings, which biases the mean temperature upward. The JSON's `lst_obs` counts show how many observations each mean is based on.
- **MODIS measures ground (skin) temperature, not air temperature.** That's the right comparison for Diviner (Moon) and for rover ground-temperature sensors (Mars).
- **Pressure comes from elevation** via the standard atmosphere, so actual weather can shift it by a few percent.
- **Each value describes a ~2–3 km box around the site's coordinates.** Small features such as a cave entrance or a single spring are below that resolution.

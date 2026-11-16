# Analog Atlas: finding places on Earth that can stand in for the Moon and Mars

**NASA Space Apps Challenge 2026 · Challenge: Identify Earth Locations that Analog the Permanent Moon Base Locations and Mars**

🔗 **Live app:** https://srinijach1.github.io/analog-atlas/

---

## What it is

Analog Atlas is an interactive web app that ranks extreme places on Earth as analogs for candidate Moon-base and Mars landing sites.

Pick a target, such as Jezero Crater or the Shackleton rim at the lunar south pole. The app compares 19 Earth sites against it on nine dimensions:

- surface temperature
- day–night temperature swing
- air pressure
- precipitation
- terrain roughness
- ice
- dust
- extreme light cycles (polar day and night)
- geology

For each Earth site, it shows how close the match is on each dimension, where the analogy holds, where it breaks down, and how the site could help exploration.

The main idea: **no place on Earth matches the Moon or Mars on everything, so a single "best analog" is the wrong goal.** Analog Atlas makes the trade-offs visible. It also builds an *analog portfolio*: the best Earth site for each dimension, which together form a set of complementary test sites.

## How it addresses the challenge

| Challenge asks for… | Analog Atlas |
|---|---|
| Use open NASA Earth data with Moon/Mars data | Earth values are measured from NASA MODIS and NASADEM, plus ESA's Copernicus DEM and WorldCover. Key Moon and Mars values come from published Perseverance, Curiosity and LRO measurements. |
| Explain what is analogous and where the analogy breaks down | Each Earth site gets a match score per dimension, plus written notes on what holds, what breaks and how it helps exploration. Each target lists what Earth can't reproduce: gravity, vacuum or a thin CO₂ atmosphere, and radiation. |
| An analog doesn't need to match in every way | The *analog portfolio* picks the best Earth site for each dimension. |
| Look beyond well-known sites | 9 of the 19 Earth sites are rarely used as analogs (tagged *less-studied*): Lonar Crater (India), Dallol (Ethiopia), Lut yardangs (Iran), Qaidam Basin (China), Ojos del Salado, Lake Salda (Türkiye), Kamil Crater (Egypt), Lost Hammer spring (Canada) and Ngari (Tibet). The well-known sites are kept as reference points. |
| Think beyond visual similarity; consider processes | Sites are compared on physical measurements and on processes (wind erosion, acid–sulfate chemistry, brines, ground ice, lava tubes), not on appearance. |
| Similarity metrics / innovative methods | A transparent scoring method with adjustable weights and mission presets (Geology & life, Environment, Rover & EVA ops, Resources/ISRU). |
| Connect to exploration | Each site lists concrete uses: instrument testing, crew training, ISRU trials, life detection before sample return, and landing-hazard validation. |

## How the score works

For each dimension *i*, the similarity between an Earth site *e* and a target *t* is:

```
s_i = exp( −((x_i(e) − x_i(t)) / σ_i)² )                  (0 = no match, 1 = identical)
geology:  s_G = |shared mineral/process tags| / |target tags|
Score = 100 × Σ wᵢ·sᵢ / Σ wᵢ                              (weights set by the user or a preset)
```

Pressure and precipitation are compared on log scales, because the differences that matter span orders of magnitude.

The tolerances σ are:

| Dimension | σ |
|---|---|
| Temperature | 40 °C |
| Day–night swing | 60 °C |
| Pressure | 1.5 orders of magnitude |
| Precipitation | 1.5 orders of magnitude |
| 0–1 indices (roughness, ice, dust, light) | 0.35 |

## Data: measured vs estimated

Every number in the app shows where it came from. A **filled dot ●** means it was measured, either from satellite data or published mission measurements. A **hollow dot ○** means it is an estimate. Hovering over any dot shows its source.

### Earth (measured through Microsoft Planetary Computer, `earth_pipeline.py`)

Each value summarises a box about 3 km across around each site, using one year of MODIS data (2023).

| Dimension | Dataset | Provider |
|---|---|---|
| Mean surface temperature, day–night swing | MODIS Land Surface Temperature 8-day v6.1, Terra + Aqua (`modis-11A2-061`) | NASA |
| Air pressure (from elevation), terrain roughness (from slope) | NASADEM (`nasadem`) | NASA |
| Same, for polar sites outside NASADEM's 56°S–60°N coverage | Copernicus DEM GLO-30 (`cop-dem-glo-30`) | ESA |
| Ground cover (context, not scored) | ESA WorldCover 2021 (`esa-worldcover`) | ESA |
| Illumination extremes | Computed from latitude (fraction of the year in polar day or night) | — |

**Data quality review.** Lake Salda's sample box fell entirely on the lake, so its temperature and slope values were excluded and remain estimates. Lanzarote (41% sea) and Ngari (centred on a town) are flagged in the app with notes. Precipitation (TerraClimate) failed for every site because Planetary Computer changed the dataset's metadata, so rainfall remains an estimate everywhere.

### Moon and Mars targets (published mission measurements)

| Target | Values | Source |
|---|---|---|
| Jezero Crater | Surface −83 °C pre-dawn to 5 °C at noon; pressure 718 Pa | Perseverance MEDA (NASA) |
| Gale Crater | Ground temperature max ~250–290 K, min ~170–210 K; pressure ~685–780 Pa | Curiosity REMS (NASA; built by Spain's Centro de Astrobiología) |
| Mare Tranquillitatis and Marius Hills pits | Surface ~127 °C day / −173 °C night; shaded pit floor stays ~17 °C | LRO Diviner (NASA); Horvath et al. 2022, *Geophysical Research Letters*, doi:10.1029/2022GL099710 |
| Shackleton rim and Malapert Massif | Candidate south-pole sites range from +22 °C to −220 °C | NASA technical report NTRS 20205002224 |

**Still estimates:**
- Temperature and pressure for the six Mars targets without surface missions: Arcadia, Deuteronilus, Melas, Arsia, Meridiani and Medusae.
- The 0–1 indices for ice, dust and geology on all bodies.

The app's Method section lists the dataset that would replace each of these.

## Limitations (and why they matter)

- **Earth can't reproduce everything.** Gravity, vacuum or Mars's 0.6 kPa CO₂ atmosphere, and the radiation environment can't be matched anywhere on Earth. The app says so for every target.
- **MODIS measures at fixed overpass times.** Satellites pass at about 10:30/22:30 (Terra) and 13:30/01:30 (Aqua), so the measured day–night swing somewhat underestimates the true daily max − min.
- **MODIS measures ground (skin) temperature, not air temperature.** That is deliberate: Diviner and the rovers' ground sensors also measure ground temperature, so the comparison is like for like.
- **Values are site-scale averages.** Features smaller than about 3 km, such as cave interiors or individual springs, aren't resolved.
- **The 19 Earth sites were chosen by hand.** The natural next step is to run the same score on every pixel of a global satellite grid and produce a similarity heat map for each target. That would surface analogs nobody has proposed yet.

## Repository contents

| File | Purpose |
|---|---|
| `index.html` | The app, with measured data built in (this is what GitHub Pages serves) |
| `analog-atlas.html` | The same app without built-in data (the template that `bake_data.py` fills) |
| `earth_pipeline.py` | Pulls Earth measurements from Microsoft Planetary Computer and writes `earth_sites_measured.json` |
| `earth_sites_measured.json` | The measured Earth data used in the app (after quality review) |
| `bake_data.py` | Builds a JSON data file into the app |

### Reproduce the Earth data

```bash
conda create -n atlas -c conda-forge python=3.12 rasterio xarray zarr fsspec adlfs numpy pystac-client planetary-computer
conda activate atlas
python earth_pipeline.py          # ~10–30 min for all sites; no API key needed
python bake_data.py               # writes analog-atlas-measured.html with the data built in
```

To try a new data file without rebuilding, use the app's **Load measured data** button.

## Data, resources and tools

**NASA data:** MODIS LST (MOD11A2/MYD11A2 v6.1), NASADEM, Perseverance MEDA, Curiosity REMS, LRO Diviner, NASA NTRS 20205002224.

**Space Agency Partner data:**
- ESA: Copernicus DEM GLO-30, ESA WorldCover 2021.
- Spain: Curiosity's REMS instrument (Centro de Astrobiología).

**Other data, tools and resources:**
- Microsoft Planetary Computer (STAC API and data catalog)
- Natural Earth coastlines, via the [`world-atlas`](https://github.com/topojson/world-atlas) package
- Google Fonts: Space Grotesk and IBM Plex Mono (Open Font License)
- Python: pystac-client, planetary-computer, rasterio, xarray, numpy
- Published literature behind each site description

**AI assistance:** Claude (Anthropic) was used to help write the app's code and the data pipeline, to draft a few site descriptions, and to review the data. All data and sources are cited above.

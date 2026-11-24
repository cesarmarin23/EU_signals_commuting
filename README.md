# Home, work and commuting from Locomizer signals

Index of the notebooks, data and results. Everything runs on CSC Roihu as batch jobs; the notebooks are executed with
`jupyter nbconvert --execute` (see "How to run").

## Folder layout

| folder | content |
|---|---|
| `pipeline/` | country-level preprocessing, run once per country and month |
| `germany/` | one `commuting_<city>.ipynb` per German city plus `compare_cities.ipynb` |
| `france/` | the same for the French cities |
| `uk/` | the same for five UK cities (London, Manchester, Birmingham, Glasgow, Liverpool); boundaries from the Urban Audit **2020** edition, the last with UK polygons; Greater London is the 33 boroughs dissolved |
| `representation/` | `representation.ipynb`: sample representativeness as in Marin-Flores et al. (2026) Supplementary B: users per 2 km (headline) and 1 km grid square vs population (log–log fit, penetration, Poisson ceiling) for the fifteen cities; population from the Eurostat Census 2021 grid (DEU, FRA) and the JRC-GEOSTAT 2018 grid (GBR). `representation_uk_hex8.ipynb`: the same check for the six UK cities on **H3 level-8 hexagons**, with the ONS 2021 / NRS 2022 census Output Areas aggregated to the hexagons by centroid (the headline UK representativeness; no squares involved) |
| `diagnostics/` | one-off checks (month overlap and id-reset test for Berlin) |

Data and results live on scratch, `/scratch/project_2022768/<user>/locomizer/`:

| path | content |
|---|---|
| `<COUNTRY>_userday_h3_<RES>_<YYYY-MM>/userday.parquet` | one row per user, day and H3 level-8 cell with signal counts per hour (output of `pipeline/userday_month.ipynb`) |
| `results/<COUNTRY>/<city>_<period>/` | summary tables written by each city notebook (`counts`, `reasons`, `thresholds`, `distance`, `district_flows`, `district_internal`, `meta`) and by the representativeness notebook (`representation_grid{1,2}km.csv`) |
| `results/representation_summary_<period>.csv`, `results/representation_robustness_<period>.csv` | the representativeness summary of all cities (one row per city and square size) and the fit under stricter cuts |
| `results/representation_hex8_summary_GBR_<period>.csv`, `results/representation_hex8_robustness_GBR_<period>.csv` | the same for the UK cities on level-8 hexagons (`representation_uk_hex8.ipynb`); per-hexagon tables in `results/GBR/<city>_<period>/representation_hex8.csv` |
| `results/DEU/diagnostics/` | tables written by the scripts in `diagnostics/` |
| `boundaries/` | Eurostat Urban Audit and NUTS3 GeoJSON, cached basemap tiles, `census_grid_2021/` (Eurostat Census 2021 1 km grid), `jrc_grid_2018/` (JRC-GEOSTAT 2018 1 km grid, used for the UK square-grid check, with its technical factsheet), `uk_oa/` (ONS Census 2021 and NRS Census 2022 Output Area populations and centroids, and their aggregation to level-8 hexagons `uk_population_h3_8.parquet`) |
| `logs/` | Slurm logs and executed copies of the pipeline notebooks |

Raw data on Allas: `profile_signals_<COUNTRY>/signals_md5/<YYYY-MM>/` for DEU (project_2014316), GBR (project_2014314)
and FRA (project_2014315). Months available: 2024-05 and 2024-06. A GBR month is about 465 GiB, four times DEU or FRA: run it on a
full node with `LOCO_LOCAL_WORK=1` (partials on the 600 GiB node-local disk), `LOCO_BATCH_GIB=32`, `LOCO_H3_RES=9` and `LOCO_ALSO_H3_8=1`
(level-8 table derived from the same download). The Eurostat Census 2021 grid has no UK cells, so the representativeness notebook
uses the JRC-GEOSTAT 2018 grid (same 1 km cells, residents at mid-2018) for the UK cities; on shared cells the two grids agree within 1%.

## Pipeline

1. `pipeline/userday_month.ipynb` — one month of raw signals from Allas to the user-day-cell table. Country and month are
   taken from the environment variables `LOCO_COUNTRY` and `LOCO_MONTH` (defaults in the parameter cell).
2. `<country>/commuting_<city>.ipynb` — home and work cells per user and month, the two-month rule, commuting tables, maps and
   flows for one city. The city is chosen with `CITY_KEY`; country, Urban Audit codes and holidays follow from the `CITIES` table.
3. `<country>/compare_cities.ipynb` — the city summaries side by side.
4. `representation/representation.ipynb` — users per 2 km square of the European 1 km reference grid against grid population (census 2021 for DEU and FRA, JRC-GEOSTAT 2018 for GBR; headline unit chosen for a European-wide comparison), with the 1 km fit of the Finnish paper as a secondary row; independent of steps 2–3, it uses level-9 user-day tables (`LOCO_H3_RES=9`) and the same home rule. `LOCO_CITIES=<keys>` runs a subset whose rows are merged into the saved summary (needed because the DEU/FRA level-9 tables were deleted after their run).
5. `representation/representation_uk_hex8.ipynb` — the UK cities on level-8 hexagons: census Output Areas (ONS 2021 for England and Wales, NRS 2022 for Scotland) summed into the hexagon that contains their centroid, panel users by level-8 home cell from the same tables as the city notebooks, then the same log–log fit, Poisson ceiling and penetration. Decided on 2026-11-23 to keep the hexagon as the unit for the UK rather than converting hexagons to squares. The summary also gives the R² a perfectly proportional sample of the same size would reach (Poisson draws from the census population), the benchmark the observed R² should be read against.

`pipeline/extract_day.ipynb` extracts a single day of raw signals (used for the early exploration only).

## Method in short

- Home = cell with most signals 22:00–07:00 over the month; work = cell other than home with most signals 09:00–17:00 on
  working days (weekdays minus public holidays), as in scikit-mobility's `home_location`.
- Thresholds: home on at least 10 nights, work on at least 4 working days (`H_MIN`, `W_MIN`; alternatives in `thresholds.csv`).
- Two months (May and June 2024): home and work are detected per calendar month and one record per user is kept, the latest
  month in which both qualify, otherwise the latest month in which home qualifies (month-by-month detection as in Zhang,
  Poliakov, Tenkanen & Arcaute 2025, arXiv:2509.00919). The results folder of a two-month run is `<city>_2024-05_2024-06`.
- Berlin check (`diagnostics/`): only a fifth of May residents are residents again in June, but the ids that disappear are light
  users with no clustering at the month boundary and no excess of repeated home/work pairs, so this is panel churn, not id resets.

## Cities

| country | cities (`CITY_KEY`) | status |
|---|---|---|
| Germany (DEU) | munich, berlin, hamburg, frankfurt, cologne | two-month results done |
| United Kingdom (GBR) | london, manchester, birmingham, glasgow, liverpool | two-month results done (2026-11-23); representativeness run with the 2018 grid |
| France (FRA) | paris, lyon, marseille, nice | two-month results done; Toulouse was run but is excluded from the comparison and the representativeness analysis |

Note: the Urban Audit "city" of Paris (FR001C, about 2000 km²) is much larger than the commune of Paris.

## How to run

User-day table for one country and month (about 15 min, 32 cores, 128 GiB):

```bash
S=/scratch/project_2022768/$USER/locomizer
sbatch --account=project_2022768 --partition=small --time=02:00:00 --cpus-per-task=32 --mem=128G --job-name=userday_FRA_2024-05 \
  --export=ALL,LOCO_COUNTRY=FRA,LOCO_MONTH=2024-05 --output=$S/logs/userday_FRA_2024-05_%j.out \
  --wrap="module load allas python-geo; cd ~/locomizer_signals/pipeline; jupyter nbconvert --to notebook --execute --ExecutePreprocessor.timeout=-1 --output-dir=$S/logs --output=userday_FRA_2024-05.ipynb userday_month.ipynb"
```

All city notebooks of one country and the comparison (about 15 min for two months, 16 cores, 128 GiB):

```bash
sbatch --account=project_2022768 --partition=small --time=01:00:00 --cpus-per-task=16 --mem=128G --job-name=cities_FRA \
  --output=$S/logs/cities_FRA_%j.out \
  --wrap='module load allas python-geo; cd ~/locomizer_signals/france; for nb in commuting_paris commuting_lyon commuting_marseille commuting_nice compare_cities; do jupyter nbconvert --to notebook --execute --inplace --allow-errors --ExecutePreprocessor.timeout=-1 $nb.ipynb; done'
```

The city notebooks are executed in place, so the figures and tables are visible in the notebook afterwards.

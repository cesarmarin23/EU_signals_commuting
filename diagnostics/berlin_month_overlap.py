import os, duckdb, h3, geopandas as gpd, pandas as pd
from pathlib import Path
S = Path(f"/scratch/project_2022768/{os.environ['USER']}/locomizer")
fua  = gpd.read_file(S/"boundaries"/"URAU_RG_100K_2021_4326_FUA.geojson").set_index("URAU_CODE").loc["DE001F"].geometry
city = gpd.read_file(S/"boundaries"/"URAU_RG_100K_2021_4326_CITIES.geojson").set_index("URAU_CODE").loc["DE001C"].geometry
cf, cc = set(h3.geo_to_cells(fua, 8)), set(h3.geo_to_cells(city, 8))
area = pd.DataFrame({"h3_8": sorted(cf), "area": ["city" if c in cc else "metro_other" for c in sorted(cf)]})
NIGHT = " + ".join(f"h{h}" for h in [22,23,0,1,2,3,4,5,6]); WORK = " + ".join(f"h{h}" for h in range(9,17))
WD = "dow IN (1,2,3,4,5) AND NOT (month = '2024-05' AND day IN (1, 9, 20))"
con = duckdb.connect(); con.register("area", area)
con.execute(f"SET threads = {os.environ.get('SLURM_CPUS_PER_TASK', 8)}; SET memory_limit = '80GB'; SET temp_directory = '{os.environ.get('TMPDIR','/tmp')}/duck'; SET preserve_insertion_order = false;")
con.execute("CREATE VIEW ud AS " + " UNION ALL ".join(f"SELECT '{m}' AS month, * FROM read_parquet('{S}/DEU_userday_h3_8_{m}/userday.parquet')" for m in ["2024-05", "2024-06"]))
con.execute(f"""CREATE TABLE home AS SELECT userid, month, h3_8 AS home_cell, home_days FROM (
    SELECT userid, month, h3_8, count(*) AS home_days, row_number() OVER (PARTITION BY userid, month ORDER BY sum(n_night) DESC, sum(n_total) DESC, h3_8) AS rn
    FROM (SELECT userid, month, h3_8, n_total, ({NIGHT}) AS n_night FROM ud) WHERE n_night > 0 GROUP BY userid, month, h3_8) WHERE rn = 1""")
con.execute(f"""CREATE TABLE work AS SELECT userid, month, h3_8 AS work_cell, work_days FROM (
    SELECT u.userid, u.month, u.h3_8, count(*) AS work_days, row_number() OVER (PARTITION BY u.userid, u.month ORDER BY sum(u.n_work) DESC, sum(u.n_total) DESC, u.h3_8) AS rn
    FROM (SELECT userid, month, day, h3_8, n_total, ({WORK}) AS n_work FROM ud WHERE {WD}) u JOIN home h USING (userid, month)
    WHERE u.h3_8 <> h.home_cell AND u.n_work > 0 GROUP BY u.userid, u.month, u.h3_8) WHERE rn = 1""")
con.execute("""CREATE TABLE p AS SELECT h.*, w.work_cell, w.work_days, a.area AS home_area, aw.area AS work_area
    FROM home h LEFT JOIN work w USING (userid, month) LEFT JOIN area a ON h.home_cell = a.h3_8 LEFT JOIN area aw ON w.work_cell = aw.h3_8""")
Q = {"seen in the data (any signal)": "SELECT userid, month FROM (SELECT DISTINCT userid, month FROM ud)",
     "Berlin FUA resident (home_days >= 10)": "SELECT userid, month FROM p WHERE home_days >= 10 AND home_area IS NOT NULL",
     "Berlin city resident (home_days >= 10)": "SELECT userid, month FROM p WHERE home_days >= 10 AND home_area = 'city'",
     "FUA resident with work cell (work_days >= 4)": "SELECT userid, month FROM p WHERE home_days >= 10 AND home_area IS NOT NULL AND work_days >= 4",
     "commuter with home or work in FUA": "SELECT userid, month FROM p WHERE home_days >= 10 AND work_days >= 4 AND (home_area IS NOT NULL OR work_area IS NOT NULL)"}
rows = []
for name, q in Q.items():
    r = con.execute(f"""SELECT count(*) FILTER (WHERE month = '2024-05') AS may, count(*) FILTER (WHERE month = '2024-06') AS june,
        count(DISTINCT userid) AS either, count(*) - count(DISTINCT userid) AS both FROM ({q})""").df().iloc[0]
    rows.append({"users": name, **r.to_dict()})
out = pd.DataFrame(rows).set_index("users")
# among FUA residents with home and work in both months: same home / same work cell
r = con.execute("""SELECT count(*) AS both, count(*) FILTER (WHERE a.home_cell = b.home_cell) AS same_home, count(*) FILTER (WHERE a.work_cell = b.work_cell) AS same_work
    FROM p a JOIN p b ON a.userid = b.userid AND a.month = '2024-05' AND b.month = '2024-06'
    WHERE a.home_days >= 10 AND b.home_days >= 10 AND a.work_days >= 4 AND b.work_days >= 4 AND a.home_area IS NOT NULL AND b.home_area IS NOT NULL""").df()
print(out.to_string()); print("\nFUA residents with home and work in BOTH months:"); print(r.to_string(index=False))
out.to_csv(S/"results"/"berlin_month_overlap.csv"); r.to_csv(S/"results"/"berlin_month_overlap_same.csv", index=False)

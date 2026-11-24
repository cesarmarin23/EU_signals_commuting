import os, duckdb, h3, geopandas as gpd, pandas as pd, numpy as np
from pathlib import Path
S = Path(f"/scratch/project_2022768/{os.environ['USER']}/locomizer")
fua  = gpd.read_file(S/"boundaries"/"URAU_RG_100K_2021_4326_FUA.geojson").set_index("URAU_CODE").loc["DE001F"].geometry
cf = sorted(set(h3.geo_to_cells(fua, 8))); area = pd.DataFrame({"h3_8": cf})
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
# Berlin FUA residents per month with activity span
con.execute("""CREATE TABLE res AS
    SELECT h.userid, h.month, h.home_cell, h.home_days, w.work_cell, w.work_days, s.first_day, s.last_day, s.days_observed, s.n_signals
    FROM home h JOIN area a ON h.home_cell = a.h3_8 LEFT JOIN work w USING (userid, month)
    JOIN (SELECT userid, month, min(day) AS first_day, max(day) AS last_day, count(DISTINCT day) AS days_observed, sum(n_total) AS n_signals FROM ud GROUP BY 1, 2) s USING (userid, month)
    WHERE h.home_days >= 10""")

seen = con.execute("SELECT userid, bool_or(month = '2024-05') AS seen_may, bool_or(month = '2024-06') AS seen_june FROM (SELECT DISTINCT userid, month FROM ud) GROUP BY userid").df().set_index("userid")
con.execute("CREATE TABLE cls AS SELECT userid, count(*) = 2 AS in_both FROM res GROUP BY userid")
res = con.execute("SELECT r.*, c.in_both FROM res r JOIN cls c USING (userid)").df()
res = res.join(seen, on="userid")
may, june = res[res.month == "2024-05"], res[res.month == "2024-06"]
may_gone = may[~may.seen_june]          # resident in May, id never seen in June
june_new = june[~june.seen_may]         # resident in June, id never seen in May
may_other = may[~may.in_both & may.seen_june]; june_other = june[~june.in_both & june.seen_may]
both_m = may[may.in_both].set_index("userid"); both_j = june[june.in_both].set_index("userid")
print(f"Berlin FUA residents May: {len(may):,} = in both {len(both_m):,} + seen in June but not resident there {len(may_other):,} + id absent in June {len(may_gone):,}")
print(f"Berlin FUA residents June: {len(june):,} = in both {len(both_j):,} + seen in May but not resident there {len(june_other):,} + id absent in May {len(june_new):,}")

print("\n=== 1. activity span (share of users); uniform expectation for 3 of ~30 days is about 10% ===")
sp = lambda df, col, days: f"{100*df[col].isin(days).mean():.1f}%"
print(f"id absent in June: last seen 29-31 May  {sp(may_gone, 'last_day', [29,30,31])};  seen in June but not resident: {sp(may_other, 'last_day', [29,30,31])};  in both: {sp(both_m, 'last_day', [29,30,31])}")
print(f"id absent in May: first seen 1-3 June   {sp(june_new, 'first_day', [1,2,3])};  seen in May but not resident: {sp(june_other, 'first_day', [1,2,3])};  in both: {sp(both_j, 'first_day', [1,2,3])}")
print("last-seen day of May residents whose id is absent in June, by week: " + ", ".join(f"{a}-{b}: {100*may_gone.last_day.between(a,b).mean():.0f}%" for a,b in [(1,7),(8,14),(15,21),(22,28),(29,31)]))
print("first-seen day of June residents whose id is absent in May, by week: " + ", ".join(f"{a}-{b}: {100*june_new.first_day.between(a,b).mean():.0f}%" for a,b in [(1,3),(4,10),(11,17),(18,24),(25,30)]))
print(f"observed on >= 25 days: absent-in-June May residents {100*(may_gone.days_observed>=25).mean():.1f}%, absent-in-May June residents {100*(june_new.days_observed>=25).mean():.1f}%, in both {100*(both_m.days_observed>=25).mean():.1f}%")

print("\n=== 2. home+work pair matching (work_days >= 4): do June-new commuters repeat the pairs of May-gone commuters? ===")
cm = may_gone[may_gone.work_days >= 4]; cj = june_new[june_new.work_days >= 4]
bb = both_m.join(both_j, lsuffix="_m", rsuffix="_j"); bb = bb[(bb.work_days_m >= 4) & (bb.work_days_j >= 4)]
p_keep = ((bb.home_cell_m == bb.home_cell_j) & (bb.work_cell_m == bb.work_cell_j)).mean()
pairs_m = set(zip(cm.home_cell, cm.work_cell))
r1 = np.mean([(h, w) in pairs_m for h, w in zip(cj.home_cell, cj.work_cell)])
r0 = np.mean([(h, w) in pairs_m for h, w in zip(bb.home_cell_j, bb.work_cell_j)])      # baseline A: June pairs of users known to be stable ids (different people from May-gone)
rng = np.random.default_rng(0); r0b = []
cj6 = cj.assign(h6=[h3.cell_to_parent(c, 6) for c in cj.home_cell])
for _ in range(20):                                                                     # baseline B: shuffle work cells among June-new commuters living in the same level-6 area
    sh = cj6.groupby("h6").work_cell.transform(lambda s: rng.permutation(s.values))
    r0b.append(np.mean([(h, w) in pairs_m for h, w in zip(cj6.home_cell, sh)]))
r0b = np.mean(r0b)
print(f"May-gone commuters: {len(cm):,}; June-new commuters: {len(cj):,}; stable ids keeping the same home AND work cell: {100*p_keep:.1f}% (n={len(bb):,})")
print(f"share of June-new commuters whose exact pair exists among May-gone commuters: {100*r1:.1f}%")
print(f"baseline A (June pairs of stable ids): {100*r0:.1f}%;  baseline B (work cells shuffled within level-6 home area): {100*r0b:.1f}%")
for name, r0x in [("A", r0), ("B", r0b)]:
    f = max(r1 - r0x, 0) / (p_keep * (1 - r0x))
    print(f"  => with baseline {name}: estimated {100*f:.1f}% of June-new commuters are May-gone people with a new id = {f*len(cj):,.0f} users, {100*f*len(cj)/(len(cm)+len(cj)+len(bb)+len(may_other[may_other.work_days>=4])+len(june_other[june_other.work_days>=4])):.1f}% of the combined commuter panel")

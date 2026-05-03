# Data management

How to add, fix, dump, and migrate championship data — both locally and
in production. Companion to `.plans/deployment.md` (which focuses on the
container/Railway side); this doc focuses on the **CSVs and the rows they
become**.

If you just want to add a race result, jump to
[**"Add a new race day"**](#add-a-new-race-day).

---

## How the data flows

```
seed_data/<year>/*.csv          (source of truth, one CSV per race-day)
        │
        ▼
backend/scripts/import_race_day.py
        │  · upserts Season / Category / Event / Rider
        │  · writes EventResult rows (one per (rider, day))
        │  · records (filename, sha256) in import_log
        ▼
Postgres (local or prod)        (read-only at runtime by FastAPI)
```

Two driver scripts wrap `import_race_day`:

| Script | What it does | When |
|---|---|---|
| `backend/scripts/seed_new.py` | Walks `seed_data/`, hashes each CSV, calls `import_race_day` only for files NOT in `import_log`. Idempotent. | **Default — use this.** |
| `backend/scripts/seed_all.py` | Wipes championship tables (keeps `visit` rows), reimports everything. | Cleaning up after schema changes or duplicate-data mistakes. |

---

## File and folder layout

```
seed_data/
├── 2024/
│   ├── hard_enduro_botevgrad-2024-day1.csv
│   ├── hard_enduro_botevgrad-2024-day2.csv
│   └── …
├── 2025/
└── 2026/
```

**Filename pattern** (enforced by `import_race_day.py`):

```
<prefix>_<race_slug>-<year>-day<N>.csv     # 2024 — hyphen separator
<prefix>_<race_slug>_<year>-day<N>.csv     # 2025 onward — underscore
```

- `<prefix>` ∈ `hard_enduro` | `endurox` | `enduro` (case-sensitive)
- `<race_slug>` becomes the URL slug (`/results?...&race=buhovo`)
- `<year>` filters by season; must match the CSV's `year` column
- `<N>` is the day number for multi-day events (`day1`, `day2`)

**CSV columns** (header row required, exact names):

```
year, event_file, event, day, class, status, position, start_number,
rider_name, motorcycle, club, ride_time, gps_penalty, cp_penalty, laps,
total_time, start_time, finish_time, points, gap_to_leader, partial_time
```

| Column | Notes |
|---|---|
| `class` | Bulgarian label — `ПРОФИ`, `ЕКСПЕРТ`, `СТАНДАРТ`, `СТАНДАРТ-ДЖУНИЪР`, `ЖЕНИ`, `СЕНЬОРИ 40+`, `СЕНЬОРИ 50+`. Mapped to category codes by `CLASS_MAP` in `import_race_day.py:49`. Unknown labels get **silently skipped** — watch the importer's `(N skipped)` counter. |
| `rider_name` | `Първо ФАМИЛИЯ` — last name in ALL CAPS. The importer uses casing to split. |
| `total_time` | `H:MM:SS.cs` or `MM:SS.cs`. The display "Време" column. |
| `points` | Float; nullable. |
| `position` | Day position; multi-day rendering re-ranks by combined points/time. |
| `status` | `FIN` / `DNF` / `DNS` / etc. Anything non-FIN means the rider doesn't get a numeric position in the race-results page. |

A multi-day weekend = one CSV per day, same `<race_slug>`. The frontend
collapses them into one row per rider with summed points + summed time.

---

## Add a new race day

1. **Drop the CSV in the right folder.**

   ```bash
   cp ~/Downloads/buhovo_day2.csv seed_data/2026/hard_enduro_buhovo_2026-day2.csv
   ```

   Match an existing filename pattern in the same year folder so the
   slug parses correctly.

2. **Import locally.** `seed-new` is idempotent — safe to run from a
   clean repo too.

   ```bash
   make seed-new YEAR=2026
   ```

   Output:
   ```
   ✓ hard_enduro_buhovo_2026-day2.csv → 2026/buhovo day=2  162 result(s)
   ```

   Watch for `(N skipped)` — that means rows had unknown class labels
   or missing names. See [Common skipped-row reasons](#common-skipped-row-reasons).

3. **Verify in the UI.**

   ```bash
   curl -s http://127.0.0.1:5001/api/seasons/2026/categories/profi/events/buhovo \
     | python3 -m json.tool | head -40
   ```

   Or open `http://localhost:4321/results?season=2026&category=profi&race=buhovo`.

4. **Push to prod.**

   ```bash
   make db-dump ARGS="--data-only"
   make db-seed-prod FILE=db_dumps/local-20260427-094505Z.sql.gz   # confirms interactively
   ```

   Or, if you'd rather skip the local dump round-trip, run the
   importer against the prod DB directly:

   ```bash
   railway run python -m scripts.seed_new --year 2026
   ```

5. **Commit the CSV.** `seed_data/` is tracked in git so other
   devs / CI / a fresh laptop can rebuild the same database.

   ```bash
   git add seed_data/2026/hard_enduro_buhovo_2026-day2.csv
   git commit -m "data: import Buhovo 2026 day 2"
   git push
   ```

---

## Fix a CSV (re-import after editing)

`seed-new` deduplicates by `(filename, sha256)`. Editing a CSV changes
its hash, so the next `seed-new` will re-run that file's import.

```bash
# 1. Edit the CSV — fix typo, correct points, add a missing rider, etc.
$EDITOR seed_data/2026/hard_enduro_buhovo_2026-day2.csv

# 2. Re-import. The importer wipes existing EventResult rows for
#    (event, day, categories-in-this-CSV) before re-inserting,
#    so you don't get duplicates.
make seed-new YEAR=2026

# 3. (Optional) push to prod.
make db-dump ARGS="--data-only"
make db-seed-prod FILE=db_dumps/local-….sql.gz
```

The relevant truncate-then-insert lives at
`backend/scripts/import_race_day.py:331`. **It only touches categories
present in the CSV**, so editing a profi-only CSV doesn't blow away
expert results from a sibling day.

---

## Add a new category

Bulgarian class labels are mapped to category codes in
`backend/scripts/import_race_day.py`:

```python
CLASS_MAP: dict[str, tuple[str, str]] = {
    "ПРОФИ":             ("profi",           "ПРОФИ"),
    "ЕКСПЕРТ":           ("expert",          "ЕКСПЕРТ"),
    # …
}
```

If a CSV ships a class not yet in `CLASS_MAP`, the importer logs
`unknown class '<label>'` once and silently skips every row in that
class. To add one:

1. Pick a stable code (snake_case, lowercase) — e.g. `junior` for
   `ДЖУНИЪР`.
2. Add the entry to `CLASS_MAP`.
3. Add `("junior", N)` to `CATEGORY_SORT_ORDER` so it lands in the
   right tab position.
4. Re-import the affected file:

   ```bash
   # The CSV's already-logged sha won't change, so seed-new alone
   # would skip it. Either delete the import_log row or call the
   # single-file importer directly:
   cd backend && source .venv/bin/activate
   python -m scripts.import_race_day --file ../seed_data/2026/hard_enduro_buhovo_2026-day2.csv
   ```

5. Verify the new category shows on `/results?season=2026&category=junior`.

---

## Wipe and reload a year

If a year's data is corrupted or you've made too many manual fixes
to trust the state:

```bash
# Wipes only the chosen year's championship rows; keeps visits +
# import_log.
cd backend && source .venv/bin/activate
python -m scripts.seed_all --year 2026

# Or wipe + reload everything:
make seed-all
```

Then push to prod via Path A (full dump) or rerun the importer there:

```bash
railway run python -m scripts.seed_all --year 2026
```

---

## Dumping data

Backups, snapshots before risky changes, or "give me a frozen copy of
local before I edit the CSVs". All output lives under `db_dumps/` which
is gitignored.

| Command | Output | Contents |
|---|---|---|
| `make db-dump` | `db_dumps/local-<ts>.sql.gz` | Full schema + data, local. |
| `make db-dump ARGS="--data-only"` | `db_dumps/local-<ts>.sql.gz` (~30 KB) | Data only — pair with prod that already has schema. |
| `make db-dump ARGS="--schema-only"` | DDL only | Sanity-check what migrations produce. |
| `make db-dump ARGS="--tag pre-fix"` | `db_dumps/local-pre-fix-<ts>.sql.gz` | Custom suffix for ad-hoc snapshots. |
| `make db-dump-prod` | `db_dumps/prod-<ts>.sql.gz` | Full prod backup. Needs `PROD_DATABASE_URL` or linked Railway CLI. |
| `make db-dump-prod ARGS="--tag nightly"` | `db_dumps/prod-nightly-<ts>.sql.gz` | Tagged prod backup. |

Filenames use UTC timestamps (`20260427-093253Z`) so dumps sort
chronologically across timezones.

---

## Restoring data

| Command | What it does |
|---|---|
| `make db-restore FILE=db_dumps/local-….sql.gz` | Restore into local Docker Postgres. |
| `make db-seed-prod FILE=db_dumps/local-….sql.gz` | Push **data-only** dump to prod. Interactive confirm. |
| `./scripts/db-restore.sh prod <file> --yes` | Push to prod (full or data-only) without the Makefile prompt. |
| `./scripts/db-restore.sh url <URL> <file> --yes` | Restore to an arbitrary Postgres URL (e.g. a staging DB). |

**Production safety:** `db-restore.sh prod` always requires `--yes`, and
the Makefile target adds an interactive confirm on top. Both print the
target hostname (with the password redacted) before any write.

---

## Common skipped-row reasons

When the importer reports `(N skipped)`, here are the usual culprits.
Check the terminal output — the importer prints why each row was
dropped.

| Reason | Example | Fix |
|---|---|---|
| Unknown class label | `unknown class 'ДЖУНИЪР'` | Add the label to `CLASS_MAP` in `import_race_day.py`. |
| Missing rider number or name | `row missing number/name: {…}` | Fix the source CSV. |
| Time-token leakage in `rider_name` | `Иван ИВАНОВ 3:34:40.7` | The importer strips a single trailing time token automatically (`_split_name`); deeper corruption needs a manual CSV edit. |
| Unrecognised time format | `total_time` outside `H:MM:SS[.cs]` / `MM:SS[.cs]` | Reformat the cell. |

---

## Visits and analytics — keep these out of CSV imports

`visit` rows live alongside championship data but follow a different
lifecycle: they accumulate at runtime via `POST /api/track`. The
seeders **never** touch them. Two implications:

1. **Wiping seasons preserves your stats history.** `seed-all` only
   deletes Season/Category/Event/Rider/EventResult; `visit` rows
   survive.
2. **A full prod backup IS the only way to preserve visits across a
   migration.** If you do `seed-all` against prod, the championship
   side resets but visits stay; if you do a full schema+data restore,
   visits are overwritten by whatever was in the dump.

---

## Quick reference

```bash
# Adding a CSV
make seed-new YEAR=2026                                # local: import new CSVs only
railway run python -m scripts.seed_new --year 2026     # prod: same, against Railway

# Editing a CSV
make seed-new YEAR=2026                                # the new sha re-imports just the edited file

# Dumping
make db-dump                                           # local full
make db-dump ARGS="--data-only"                        # local data only
make db-dump-prod                                      # prod (needs Railway CLI / PROD_DATABASE_URL)

# Restoring
make db-restore FILE=db_dumps/local-….sql.gz           # into local
make db-seed-prod FILE=db_dumps/local-….sql.gz         # → prod (gated)

# Resetting
make seed-all                                          # local: wipe + reimport every CSV
make db-reset                                          # local: nuke Postgres volume + alembic + seed
railway run python -m scripts.seed_all --year 2026     # prod: wipe + reimport one year
```

For deployment / Railway-specific concerns (env vars, build flow,
backups), see [`.plans/deployment.md`](../.plans/deployment.md).

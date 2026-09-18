# URECA Project — ECD / Image-Quality Specular Microscopy Report

Self-contained local pipeline: two xlsx exports in, one static HTML dashboard
out. No servers, no frameworks, no external API calls.

## What this is / what's been done

This project turns two clinical-trial spreadsheet exports (an image-quality
grade file and an ECD-value file) into the interactive HTML dashboard you
originally had as a single hand-built file
(`ECD_Image_Quality_Report (3).html`). That original file was a one-off —
the data was baked into it and there was no way to regenerate it from new
spreadsheets without redoing the work.

What changed: the dashboard's markup/CSS/charting JS was extracted into a
reusable **template** (`report_template.html`) with one placeholder where
data goes, and a **build script** (`build_report.py`) was written that reads
the two xlsx files, merges and classifies every image, and drops the result
into that placeholder to produce a fresh `output/report.html`. The pipeline
was verified to reproduce the original report exactly (1973 image records,
0 mismatches) before anything else was built on top of it.

In short: what used to be a static file is now a repeatable pipeline —
drop in new xlsx exports, run one command, get an updated dashboard.

## File-by-file

| Path | What it is |
|---|---|
| `report_template.html` | The dashboard shell: all HTML/CSS and the chart/table JS logic. Contains one placeholder, `__REPORT_DATA_JSON__`, inside `<script id="report-data" type="application/json">`, where the real data gets substituted in. You never open this file directly to view a report — it has no data in it. |
| `build_report.py` | The build script. Reads the IQ-grade xlsx and the ECD-value xlsx, decrypts either one if it's password-protected (via `msoffcrypto-tool`), merges them by filename, classifies every image (pass/fail/excluded/orphan — see below), and writes the filled-in HTML to whatever `--out` path you give it. |
| `requirements.txt` | Python dependencies: `pandas` (spreadsheet parsing), `openpyxl` (xlsx engine), `msoffcrypto-tool` (decrypting password-protected xlsx files). |
| `data/` | The two source xlsx files. Committed to this repo — see the hosting/privacy note below before treating that as the default for other projects. |
| `docs/index.html` | The generated dashboard, filled with the real data from `data/`. This is what GitHub Pages serves (GitHub Pages is configured to build from `main` / `/docs`). Regenerate it with the command below any time the source data changes. |
| `output/` | Gitignored local scratch copy of the same generated report, used for quick local viewing without touching the tracked `docs/index.html` until you're ready to update the published copy. |
| `ECD_Image_Quality_Report (3).html` | The original hand-built report you started with. Kept for reference/comparison; no longer needed day-to-day once you trust the pipeline. |
| `.gitignore` | Excludes `output/`, `.venv/`, `.claude/`, and Python cache files from git. |

## How it works

1. **Read.** Each xlsx is loaded with `pandas`. If `msoffcrypto` detects the
   file is encrypted, it's decrypted in-memory first using the password you
   pass on the command line (`--iq-password` / `--ecd-password`) — no
   decrypted copy is ever written to disk.
2. **Parse filenames.** Every row's `Filename` (e.g. `ROCKI-001_OD_M3_10.png`)
   is split into subject ID, eye, visit, and corneal location.
3. **Merge.** The IQ-grade rows and ECD-value rows are outer-joined on
   filename, so images that only appear in one file are kept (not silently
   dropped).
4. **Classify** each image into one category:
   - only in the ECD file (no IQ grade) → `orphan_ecd_only`
   - IQ grade is `0` (poor quality) → `excluded_poor_quality`
   - IQ grade > 0 but missing from the ECD file → `excluded_missing_ecd`
   - IQ grade > 0 and ECD present → `pass` if `Binary ECD` is `1`, else `fail`
5. **Inject.** The classified records are serialized to JSON and substituted
   into `report_template.html` in place of `__REPORT_DATA_JSON__`, producing
   a single self-contained HTML file — same charts, tables, and filters as
   the original, now driven by whatever data you just fed in.

The pipeline was verified against the original hand-built report before
anything else was built on top of it: same 1973 image records, same category
counts, 0 mismatches, and the surrounding HTML/CSS/JS byte-identical outside
the data payload.

## One-time setup

```
pip install -r requirements.txt
```

> Note for this machine: creating a `venv` under this Desktop folder tripped
> Windows Application Control on pandas' compiled DLL (freshly-installed
> binaries in a new venv path get blocked; the already-trusted user-level
> install did not). If `pip install -r requirements.txt` ever fails the same
> way, just run it without a venv (as above) rather than fighting the venv.

## Regenerating the report

To update the **published** dashboard (GitHub Pages serves this path):

```
python build_report.py --iq data/multiIQ_Grade.xlsx --ecd data/ECD_screening_ECDValue.xlsx \
    --iq-password <password> --template report_template.html --out docs/index.html
```

To generate a local-only copy without touching the published one:

```
python build_report.py --iq data/multiIQ_Grade.xlsx --ecd data/ECD_screening_ECDValue.xlsx \
    --iq-password <password> --template report_template.html --out output/report.html
```

Notes on the two source files:
- **IQ grade file** (`--iq`) has columns `Filename`, `Predicted Multi-class
  Grade`. On this dataset it is the password-protected one — pass its
  password with `--iq-password`.
- **ECD file** (`--ecd`) has columns `Filename`, `ECDValue`, `Binary ECD`. It
  was not encrypted here, so `--ecd-password` is normally omitted — but the
  flag exists and works the same way if a future export is protected instead.
- Filenames must follow `SubjectID_Eye_Visit_Location.ext` (e.g.
  `ROCKI-001_OD_M3_10.png`) — that's how each record is split into subject,
  eye, visit, and corneal location.

Swap in new xlsx files under `data/` any time and re-run the same command —
nothing else needs to change.

## Viewing it

**Hosted:** https://9irija.github.io/Clinical-Report/ — GitHub Pages serves
`docs/index.html` directly, updates a minute or two after you push a new
version of that file.

**Locally:** just double-click `output/report.html` (or `docs/index.html`).
Everything (styles, chart logic, and the data) is embedded in the one file
with no external API calls, so it works straight off disk in any browser.

If you'd rather serve it (e.g. to avoid any browser file:// quirks):

```
cd output
python -m http.server 8000
```

then open http://localhost:8000/report.html.

## Editing the look of the report

`report_template.html` is the dashboard shell. Edit its CSS/HTML/JS freely —
just don't touch the `__REPORT_DATA_JSON__` placeholder (inside the
`<script id="report-data" type="application/json">` tag). `build_report.py`
looks for that exact token and substitutes the merged data there.

## Hosting note (GitHub Pages)

This repo is **public**, and `data/`, `docs/index.html`, and
`ECD_Image_Quality_Report (3).html` all contain real per-subject clinical
data (subject IDs, per-eye/visit ECD values and quality grades). That data
is publicly visible to anyone with the repo/site link — this was a
deliberate choice made when setting this up, not an oversight. If that
changes, pull `data/` and the filled reports back out of git (keep only
`report_template.html`, `build_report.py`, `requirements.txt`) and host
elsewhere with access control instead.

GitHub Pages is configured to build from the `main` branch, `/docs` folder,
so the live site always reflects whatever is currently committed at
`docs/index.html`.

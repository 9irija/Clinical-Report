# URECA Project — ECD / Image-Quality Specular Microscopy Report

Self-contained local pipeline: two AI-model-output xlsx exports (plus an
optional folder of raw images) in, one static HTML dashboard out. No
servers, no frameworks, no external API calls.

## What this is / what's been done

This project turns the actual AI pipeline's predictions into the interactive
HTML dashboard you originally had as a single hand-built file
(`ECD_Image_Quality_Report (3).html`). The real pipeline is:

```
Specular microscopy image
  → Binary Image Quality AI model → Good / Bad
        Bad  → excluded / manual review
        Good → Binary ECD AI model → Acceptable ECD (≥1000 cells/mm²) / Low ECD (<1000)
```

The dashboard's markup/CSS/charting JS lives in a reusable **template**
(`report_template.html`) with one placeholder where data goes, and a
**build script** (`build_report.py`) reads the two source xlsx files,
merges them by filename, classifies every image by the AI models' own
predictions (never by re-thresholding a real ECD number), and drops the
result into that placeholder to produce a fresh `docs/index.html`.

**Important distinction kept throughout the report:** box/wedge *colour*
(Pass / Fail / Excluded) always comes from the AI models' predictions.
Any *number* shown (histograms, per-subject means, the Regional Map's
per-location values, the wheel's "ECD value" view) is the real,
segmented-cell ECD — the ground truth the AI is trying to predict, not the
AI's own estimate. The two are never conflated: the "AI prediction" wheel
view shows the model's confidence (%), not a fabricated ECD number.

## File-by-file

| Path | What it is |
|---|---|
| `report_template.html` | The dashboard shell: all HTML/CSS and the chart/table JS logic. Contains one placeholder, `__REPORT_DATA_JSON__`, inside `<script id="report-data" type="application/json">`, where the real data gets substituted in. You never open this file directly to view a report — it has no data in it. |
| `build_report.py` | The build script. Reads the image-quality xlsx and the ECD xlsx, decrypts either one if it's password-protected (via `msoffcrypto-tool`), merges them by filename, classifies every image (see below), optionally generates preview thumbnails from a folder of raw images, and writes the filled-in HTML to whatever `--out` path you give it. |
| `requirements.txt` | Python dependencies: `pandas`, `openpyxl` (xlsx engine), `msoffcrypto-tool` (decrypting password-protected xlsx files), `Pillow` (thumbnail generation). |
| `data/` | The two source xlsx files (`predictions_ImageQuality.xlsx`, `Grade2Plus_BinaryECDPredictions_ECDValues.xlsx`). Committed to this repo — see the hosting/privacy note below before treating that as the default for other projects. |
| `docs/index.html` | The generated dashboard, filled with the real data from `data/`. This is what GitHub Pages serves (GitHub Pages is configured to build from `main` / `/docs`). Regenerate it with the command below any time the source data changes. |
| `docs/images/` | Resized (260px-wide JPEG) preview thumbnails, one per image that has a matching raw capture. Committed — this is what the wheel's click-to-preview panel loads. |
| `output/` | Gitignored local scratch copy of the same generated report, used for quick local viewing without touching the tracked `docs/index.html` until you're ready to update the published copy. |
| `images_raw/`, `Images-*.zip` | The raw, full-resolution source images (multi-GB) that thumbnails are generated from. **Gitignored** — never committed, only `docs/images/`'s small resized copies are. |
| `ECD_Image_Quality_Report (3).html` | The original hand-built report you started with. Kept for reference/comparison; no longer needed day-to-day once you trust the pipeline. |
| `.gitignore` | Excludes `output/`, `.venv/`, `.claude/`, `images_raw/`, the raw images zip, and Python cache files from git. |

## How it works

1. **Read.** Each xlsx is loaded with `pandas`. If `msoffcrypto` detects the
   file is encrypted, it's decrypted in-memory first using the password you
   pass on the command line (`--quality-password` / `--ecd-password`) — no
   decrypted copy is ever written to disk.
2. **Parse filenames.** Every row's `Filename` (e.g. `ROCKI-001_OD_M3_10.png`)
   is split into subject ID, eye, visit, and corneal location.
3. **Merge.** The quality-model rows (the full image universe) are
   left-joined with the ECD rows (a subset — only images a human rated
   grade≥2 got a segmented-cell ECD measurement) on filename.
4. **Classify** each image using the AI models' own predictions only:
   - `Predicted Label` (quality model) is `0` → `excluded_poor_quality`
   - quality model says `Good` but there's no ECD-file row for it → `excluded_missing_ecd`
   - quality model says `Good` and an ECD-file row exists → `pass` if `Predicted Label_ECDScreening` is `1`, else `fail`
5. **Thumbnails** (optional, via `--images-dir`). Coverage isn't complete in
   any single raw-image folder, so each filename is looked up across
   `Images/` (real single-location capture, preferred) then `for_show1/` (a
   3-panel QC composite, used as a fallback) inside `--images-dir`, resized
   to a 260px-wide JPEG, and dropped in `<out>/images/`. A third subfolder,
   `masks1/` (raw segmentation label masks), is deliberately **not** used —
   most locations have only a handful of segmented cells, so it renders as a
   near-blank image that looks broken rather than informative.
6. **Inject.** The classified records are serialized to JSON and substituted
   into `report_template.html` in place of `__REPORT_DATA_JSON__`, producing
   a single self-contained HTML file.

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

To update the **published** dashboard (GitHub Pages serves this path),
including refreshing preview thumbnails from a local folder of raw images:

```
python build_report.py --quality data/predictions_ImageQuality.xlsx \
    --ecd data/Grade2Plus_BinaryECDPredictions_ECDValues.xlsx \
    --template report_template.html --out docs/index.html \
    --images-dir images_raw/Images
```

(`--images-dir` points at the folder that directly *contains* `Images/` and
`for_show1/`, not at `Images/` itself — the script checks both.)

Drop `--images-dir` entirely if you don't have the raw images locally —
the report still works fine without thumbnails, it just shows data only.

To generate a local-only copy without touching the published one, swap
`--out` for `output/report.html` instead.

Notes on the two source files:
- **Quality file** (`--quality`) — `predictions_ImageQuality.xlsx` — has
  columns `Filename`, `Predicted Label` (0=Bad, 1=Good), `Prob_Class_0`,
  `Prob_Class_1`. This is the Binary Image Quality AI model's own output
  for every captured image.
- **ECD file** (`--ecd`) — `Grade2Plus_BinaryECDPredictions_ECDValues.xlsx`
  — a master file keyed by `File Name`, with the real `ECD` (segmented-cell
  measurement) alongside `Predicted Label_ECDScreening` (0=Low, 1=Acceptable)
  and its own `Prob_Class_0`/`Prob_Class_1` — the Binary ECD AI model's
  output. Only present for images a human grader rated ≥2.
- Neither file was password-protected in this dataset, but `--quality-password`
  / `--ecd-password` exist and work the same way if a future export is.
- Filenames must follow `SubjectID_Eye_Visit_Location.ext` (e.g.
  `ROCKI-001_OD_M3_10.png`) — that's how each record is split into subject,
  eye, visit, and corneal location.

Swap in new xlsx files under `data/` any time and re-run the same command —
nothing else needs to change.

## Getting the raw preview images

The dashboard's click-to-preview thumbnails come from a raw capture folder
that's too large to keep in the repo (~2GB zipped, ~4GB unzipped). To
refresh them:
1. Download the source images folder as a zip (e.g. from wherever your team
   shares it) into the project root.
2. Unzip it — this project expects `images_raw/Images/Images/<Filename>.png`
   (real captures) and `images_raw/Images/for_show1/<Filename>.png` (QC
   composite fallback); a third subfolder, `images_raw/Images/masks1/`, may
   also be present but is intentionally unused (see "How it works" above).
3. Re-run the regenerate command above with `--images-dir images_raw/Images`.

No single folder covers every image (~75% in `Images/`, rising to ~87% once
`for_show1/` fills the gaps) — this is a real gap in the source data, not a
bug in the pipeline. The wheel's default subject/eye/visit is chosen to
have good thumbnail coverage so the preview feature is visible right away;
switching to a sparsely-covered subject will show "No thumbnail available"
for locations that genuinely have no captured image on file.

## Viewing it

**Hosted:** https://9irija.github.io/Clinical-Report/ — GitHub Pages serves
`docs/index.html` directly, updates a minute or two after you push a new
version of that file.

**Locally:** just double-click `output/report.html` (or `docs/index.html`).
Everything (styles, chart logic, and the data) is embedded in the one file
with no external API calls, so it works straight off disk in any browser —
thumbnails load from the `images/` folder that sits next to whichever HTML
file you open, so keep them together if you copy the file elsewhere.

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

## Where this is headed: live prediction on new images

Right now the dashboard only displays pre-computed spreadsheet exports.
The plan is to let this same page accept a newly captured image, run it
through the two AI models directly, and show the result inline. Section 8
of the report (**"Predict New Image"**) is a **non-functional placeholder**
for that — an upload control and a mockup result card, both disabled, so
the layout exists ahead of the actual integration. Nothing about it changes
how the rest of the report is built or displayed today.

When that's implemented, the design intent is for it to reuse the existing
per-record shape (`qpred`/`qconf`/`ecd`/`aipred`/`aiconf`) that
`build_report.py` already produces, so a live prediction can be rendered
with the same `whWedgeColor`/pass-fail-category logic already in
`report_template.html` instead of a separate code path. That'll need an
actual inference endpoint (the two trained models aren't part of this
repo) — out of scope until that piece exists.

## Hosting note (GitHub Pages)

This repo is **public**, and `data/`, `docs/index.html`, and
`ECD_Image_Quality_Report (3).html` all contain real per-subject clinical
data (subject IDs, per-eye/visit ECD values and AI predictions). That data
is publicly visible to anyone with the repo/site link — this was a
deliberate choice made when setting this up, not an oversight. If that
changes, pull `data/` and the filled reports back out of git (keep only
`report_template.html`, `build_report.py`, `requirements.txt`) and host
elsewhere with access control instead.

GitHub Pages is configured to build from the `main` branch, `/docs` folder,
so the live site always reflects whatever is currently committed at
`docs/index.html`.

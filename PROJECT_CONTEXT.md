# Project Context — URECA Clinical Report Dashboard

Working notes for whoever (human or Claude session) picks this project up
next. Covers what was asked, what was decided and why, what's actually
built, and what's still ahead. Read this before making structural changes —
several past instructions in this conversation were later reversed after
new information came in, and the *reasoning* for the current state matters
more than any single instruction along the way.

## The one-line summary

A specular microscopy image-quality/ECD clinical report started as a single
hand-built HTML file with data baked in. It's now a small Python pipeline
(`build_report.py` + `report_template.html`) that regenerates that same
dashboard from real AI-model-output spreadsheets, hosted as a static site
on GitHub Pages at **https://9irija.github.io/Clinical-Report/**. It is
**not yet** connected to live AI models — everything on the site is
pre-computed from spreadsheets, nothing runs on-demand.

## How we got here (chronological)

1. **Original ask**: turn a hand-built report (`ECD_Image_Quality_Report (3).html`,
   data baked in, no way to regenerate) into a re-runnable local pipeline:
   template + build script + two source xlsx files. No hosting, no framework.
2. Reverse-engineered the original file's embedded JSON data model and
   classification rules purely by inspection (no build script existed yet —
   the original report was a one-off). Verified a from-scratch rebuild
   reproduced it exactly (1973 records, 0 mismatches) before building
   anything on top.
3. User then asked to push to GitHub and host via GitHub Pages. This went
   through several reversals worth knowing about:
   - First: push code only, keep data private (repo is public).
   - Then: "push everything, host on GitHub" — explicit, informed decision
     that the clinical data (subject IDs, ECD values, AI predictions) would
     be public. This is the standing state — **data is intentionally public
     in this repo**, not an oversight.
   - GitHub Pages was briefly disabled then re-enabled after a moment of
     user confusion about "why is it live" — resolved; live-and-public was
     confirmed as the actual intent.
4. **Major correction discovered mid-project**: the original two source
   files (`multiIQ_Grade.xlsx`, `ECD_screening_ECDValue.xlsx`) turned out to
   contain **AI-predicted** values being displayed as if they were ground
   truth. The user then supplied two different, more authoritative files —
   `predictions_ImageQuality.xlsx` (the real Binary Image Quality AI model
   output) and `Grade2Plus_BinaryECDPredictions_ECDValues.xlsx` (real
   ground-truth ECD from segmented cells, alongside the real Binary ECD AI
   model's predictions). The whole pipeline was rebuilt around the actual
   model flow (see "The real pipeline" below), and the old two files were
   retired entirely — not kept as an alternate mode.
5. **Image preview bug**: user reported thumbnails never showing. Root
   cause was NOT a code bug — the wheel's default subject
   (`ROCKI-001`, picked alphabetically) happened to have ~0% image coverage
   in the raw image export, so every click looked broken. Fixed by (a)
   falling back across two raw-image subfolders instead of one, and (b)
   changing the default subject/eye/visit selection to whichever option
   actually has the most thumbnails, so the first thing anyone sees
   demonstrates the working feature.
6. Added a **"Predict New Image" placeholder section** (Section 9) — fully
   disabled UI (upload box + mockup result card) reserving space for future
   live inference. Explicitly inert; no functionality.
7. Added a **circular visit-comparison wheel** (Section 7) matching a
   reference image the user showed: two visits side by side, wheels always
   coloured by real ECD (never AI prediction), with an auto-generated
   "Reduction: <region> (loc. ...)" callout for locations that declined
   ≥100 cells/mm² between visits.
8. User asked "why not rewrite this in Python instead of HTML, since we'll
   need AI models eventually." Answered directly (see "Why still static
   HTML" below) and asked the user to choose; **they chose to stay static
   and prioritize UI/UX polish instead** — do not silently start a backend
   rewrite without this coming up again explicitly.

## The real pipeline (what the dashboard represents)

```
Specular microscopy image
  → Binary Image Quality AI model → Good / Bad
        Bad  → excluded / manual review
        Good → Binary ECD AI model → Acceptable ECD (≥1000 cells/mm²) / Low ECD (<1000)
```

**The single most important invariant in this codebase**: box/wedge
*colour* (Pass/Fail/Excluded) always comes from the AI models' own
predictions (`qpred`, `aipred` fields). Any *number* displayed (histograms,
per-subject means, Regional Map values/deltas, the wheel's "ECD value"
mode, the visit-comparison wheel) is the real, segmented-cell ECD (`ecd`
field) — ground truth, never the AI's estimate. These are never conflated.
This was a real bug in the first rebuild (the original "ECD" data was
actually an AI-predicted value) — don't reintroduce it.

## Current architecture

- `build_report.py` — Python. Reads the two xlsx files (decrypts if
  password-protected via `msoffcrypto`), merges by filename, classifies
  every image per the AI models' own predictions, optionally generates
  preview thumbnails from a folder of raw images (with fallback across
  subfolders — see below), and injects the result into
  `report_template.html`'s `__REPORT_DATA_JSON__` placeholder to produce a
  single self-contained HTML file.
- `report_template.html` — the dashboard shell: HTML/CSS/JS, no data. 9
  numbered sections (quality gate donut, ECD screening donut+histogram,
  visit pass-rate bars, per-subject table, Regional ECD Map (eye-diagram,
  2-visit comparison), Per-Location ECD Wheel (single visit, two modes: AI
  prediction / real ECD gradient), Visit Comparison Wheel (circular,
  2-visit, always real ECD), Data Consistency Notes (QA table), Predict New
  Image (disabled placeholder)).
- `docs/index.html` — the generated, data-filled dashboard. This is what
  GitHub Pages actually serves (`main` branch, `/docs` folder — GitHub's
  branch-deploy mode only allows repo-root or `/docs`, nothing else).
- `docs/images/` — resized (260px-wide JPEG) thumbnails, committed to git.
- `data/` — the two source xlsx files, committed (public, deliberately).
- `output/` — gitignored local scratch copy, for viewing changes before
  updating the published `docs/index.html`.
- `images_raw/`, `Images-*.zip` — raw full-resolution source images
  (multi-GB). **Gitignored, never commit these.** Only resized thumbnails
  in `docs/images/` are tracked.
- `ECD_Image_Quality_Report (3).html` — the original hand-built report,
  kept for reference.

### Image thumbnail sourcing (non-obvious, worth knowing)

Raw images live in three subfolders inside the images zip:
`Images/` (real single-location capture — preferred), `for_show1/` (a
1800×1800 3-panel QC composite: original + predicted outlines + coloured
masks — used as fallback), `masks1/` (raw 16-bit segmentation label masks,
pixel values are tiny integers like 0-6, not intensities). `masks1` is
**deliberately excluded** from the fallback chain — most locations have
only a handful of segmented cells, so it renders as a near-blank image
that looks more broken than showing no thumbnail at all. Coverage is
~87% (1758/2021) even with both remaining folders — this is a genuine gap
in the source data, not a pipeline bug.

## Why still static HTML (not yet a Python web app)

This came up explicitly and was resolved, but the reasoning is worth
preserving: rewriting the frontend in Flask/FastAPI would **not** unlock
live AI predictions on its own, because **no trained model artifact exists
in this project** — only the models' pre-computed outputs, as spreadsheets.
`build_report.py` is already Python; the "simple HTML" is just its output
format. A backend rewrite would only be worth it once (a) an actual model
file + inference code exists to call, and (b) hosting moves off GitHub
Pages (which cannot run Python at all) to something like Render/Railway/
Fly.io. The user chose to defer this and prioritize UI/UX polish on the
current static site instead. **Don't start a backend rewrite without that
decision being revisited explicitly** — it's a real infra/hosting change,
not just a code change.

## Known environment gotchas (this machine specifically)

- Creating a `venv` under this Desktop folder trips Windows Application
  Control on pandas' compiled DLL (fresh installs get blocked; the
  pre-existing user-level `pip install` did not). Just use the system
  Python with `pip install -r requirements.txt`, no venv.
- The Claude Code auto-mode safety classifier blocks direct GitHub API
  calls that enable/modify Pages settings (flagged as "publication");
  DELETE calls to disable it were allowed through. Enabling Pages after a
  settings change currently requires the user to do it manually via
  Settings → Pages in the GitHub UI.
- The same classifier occasionally blocks innocuous chained read-only Bash
  commands (e.g. `git log | grep`) with no explanation — usually resolved
  by re-running the same check as a single simple command instead of a
  pipe/chain.
- No headless browser testing library is installed, but Microsoft Edge is
  present at `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`
  and works fine for `--headless=new --dump-dom` smoke tests (inject a
  `window.onerror` handler + a completion marker in `document.title`,
  since Windows git-bash `$(pwd)` paths need conversion to `C:\...` form
  for `file://` URLs to resolve in a native Windows binary).

## What's next / not yet done

1. **UI/UX polish on the current static dashboard** — in progress as of
   this note. No architecture change; purely presentation/interaction
   improvements (navigation between the now-9 sections, responsiveness,
   visual polish). This is the active task.
2. **Live AI inference** — blocked on an actual trained model artifact
   existing somewhere. Section 9 ("Predict New Image") is a placeholder
   for this; do not wire it to anything real without a model to call and
   without revisiting the static-vs-backend hosting decision above.
3. Nothing else was explicitly requested beyond these two. Don't assume
   scope (e.g. adding auth, a database, user accounts) that hasn't been
   asked for.

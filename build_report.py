#!/usr/bin/env python
"""
Build the ECD / Image-Quality specular microscopy report.

Follows the actual AI pipeline: a Binary Image Quality AI model gates each
image (Good -> proceed, Bad -> excluded), then a Binary ECD AI model
classifies quality-passing images as Acceptable (>=1000 cells/mm^2) or Low
(<1000 cells/mm^2) ECD. Ground-truth ECD (measured from segmented cells) is
carried alongside for the report's real-value views (histograms, regional
map, per-visit comparisons) but never used to derive pass/fail/excluded --
that classification always comes from the AI models' own predictions.

Usage:
    python build_report.py --quality data/testing_predictions_ImageQuality.xlsx \
        --ecd data/testing_Grade2Plus_BinaryECDPredictions_ECDValues.xlsx \
        --template report_template.html --out docs/index.html \
        --images-dir images_raw/Images/Images
"""

import argparse
import io
import json
import re
from pathlib import Path

import msoffcrypto
import pandas as pd
from PIL import Image

DATA_PLACEHOLDER = "__REPORT_DATA_JSON__"
THUMB_WIDTH = 260
ECD_CUTOFF = 1000  # cells/mm^2 -- the boundary the Binary ECD AI model was trained on

FILENAME_RE = re.compile(r"^(?P<subj>.+)_(?P<eye>[A-Za-z]+)_(?P<visit>[A-Za-z0-9]+)_(?P<loc>\d+)\.[A-Za-z0-9]+$")


def load_workbook(path: Path, password: "str | None") -> pd.DataFrame:
    with open(path, "rb") as f:
        office_file = msoffcrypto.OfficeFile(f)
        if office_file.is_encrypted():
            if not password:
                raise SystemExit(f"{path} is password-protected; pass its password.")
            office_file.load_key(password=password)
            buf = io.BytesIO()
            office_file.decrypt(buf)
            buf.seek(0)
            return pd.read_excel(buf)
        return pd.read_excel(path)


def parse_filename(filename: str):
    m = FILENAME_RE.match(filename)
    if not m:
        raise ValueError(f"Filename does not match 'Subject_Eye_Visit_Location.ext': {filename}")
    return m.group("subj"), m.group("eye"), m.group("visit"), int(m.group("loc"))


def nullable_int(value):
    if pd.isna(value):
        return None
    return int(value)


def nullable_round(value, ndigits=1):
    if pd.isna(value):
        return None
    return round(float(value), ndigits)


def confidence_pct(predicted_label, prob0, prob1):
    """Confidence (%) of whichever class the model actually predicted."""
    if predicted_label is None or pd.isna(prob0) or pd.isna(prob1):
        return None
    prob = prob1 if predicted_label == 1 else prob0
    return round(float(prob) * 100, 1)


def classify(qpred, ecd, aipred):
    if qpred == 0:
        return "excluded_poor_quality"
    if ecd is None:
        return "excluded_missing_ecd"
    return "pass" if aipred == 1 else "fail"


def build_records(quality_df: pd.DataFrame, ecd_df: pd.DataFrame, images_dir: "Path | None"):
    quality = quality_df[["Filename", "Predicted Label", "Prob_Class_0", "Prob_Class_1"]].rename(
        columns={"Predicted Label": "qpred", "Prob_Class_0": "q_p0", "Prob_Class_1": "q_p1"}
    )

    ecd = ecd_df[["File Name", "ECD", "Predicted Label_ECDScreening", "Prob_Class_0", "Prob_Class_1"]].copy()
    ecd["Filename"] = ecd["File Name"] + ".png"
    ecd = ecd.rename(
        columns={
            "ECD": "ecd_true",
            "Predicted Label_ECDScreening": "aipred",
            "Prob_Class_0": "ai_p0",
            "Prob_Class_1": "ai_p1",
        }
    )[["Filename", "ecd_true", "aipred", "ai_p0", "ai_p1"]]

    merged = pd.merge(quality, ecd, on="Filename", how="left")

    records = []
    for row in merged.itertuples(index=False):
        subj, eye, visit, loc = parse_filename(row.Filename)
        qpred = nullable_int(row.qpred)
        qconf = confidence_pct(qpred, row.q_p0, row.q_p1)
        ecd_val = nullable_round(row.ecd_true)
        aipred = nullable_int(row.aipred)
        aiconf = confidence_pct(aipred, row.ai_p0, row.ai_p1)
        has_image = bool(images_dir) and (images_dir / row.Filename).is_file()
        records.append(
            {
                "f": row.Filename,
                "subj": subj,
                "eye": eye,
                "visit": visit,
                "loc": loc,
                "qpred": qpred,
                "qconf": qconf,
                "ecd": ecd_val,
                "aipred": aipred,
                "aiconf": aiconf,
                "cat": classify(qpred, ecd_val, aipred),
                "img": has_image,
            }
        )

    records.sort(key=lambda r: (r["subj"], r["eye"], r["visit"], r["loc"]))
    return records


def thumb_name(filename: str) -> str:
    return Path(filename).stem + ".jpg"


def build_thumbnails(records, images_dir: Path, thumbs_dir: Path):
    thumbs_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for rec in records:
        if not rec["img"]:
            continue
        dest = thumbs_dir / thumb_name(rec["f"])
        if dest.exists():
            continue
        with Image.open(images_dir / rec["f"]) as im:
            im = im.convert("L") if im.mode in ("I", "I;16", "I;16B") else im.convert("RGB")
            ratio = THUMB_WIDTH / im.width
            im = im.resize((THUMB_WIDTH, max(1, round(im.height * ratio))), Image.LANCZOS)
            im.save(dest, "JPEG", quality=78)
        written += 1
    return written


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quality", required=True, type=Path, help="Path to the Binary Image Quality AI predictions xlsx")
    parser.add_argument("--ecd", required=True, type=Path, help="Path to the Grade2Plus Binary ECD predictions + ECD values xlsx")
    parser.add_argument("--quality-password", default=None, help="Password for the quality xlsx, if encrypted")
    parser.add_argument("--ecd-password", default=None, help="Password for the ECD xlsx, if encrypted")
    parser.add_argument("--template", required=True, type=Path, help="Path to report_template.html")
    parser.add_argument("--out", required=True, type=Path, help="Path to write the generated report")
    parser.add_argument(
        "--images-dir",
        default=None,
        type=Path,
        help="Folder of raw per-location images (matched by exact filename) to generate preview thumbnails from",
    )
    args = parser.parse_args()

    quality_df = load_workbook(args.quality, args.quality_password)
    ecd_df = load_workbook(args.ecd, args.ecd_password)

    records = build_records(quality_df, ecd_df, args.images_dir)
    data_json = json.dumps(records)

    template_html = args.template.read_text(encoding="utf-8")
    if DATA_PLACEHOLDER not in template_html:
        raise SystemExit(f"Template is missing the {DATA_PLACEHOLDER} placeholder.")
    report_html = template_html.replace(DATA_PLACEHOLDER, data_json)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report_html, encoding="utf-8")

    print(f"Wrote {args.out} ({len(records)} image records)")

    if args.images_dir:
        thumbs_dir = args.out.parent / "images"
        written = build_thumbnails(records, args.images_dir, thumbs_dir)
        have_image = sum(1 for r in records if r["img"])
        print(f"Wrote {written} new thumbnails to {thumbs_dir} ({have_image}/{len(records)} records have one)")


if __name__ == "__main__":
    main()

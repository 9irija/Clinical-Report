#!/usr/bin/env python
"""
Build the ECD / Image-Quality specular microscopy report.

Reads the IQ-grade spreadsheet and the ECD-value spreadsheet, merges them by
filename, classifies every image, and injects the result into
report_template.html to produce a self-contained static report.

Usage:
    python build_report.py --iq data/multiIQ_Grade.xlsx --ecd data/ECD_screening_ECDValue.xlsx \
        --iq-password 1234 --template report_template.html --out output/report.html
"""

import argparse
import io
import json
import re
import sys
from pathlib import Path

import msoffcrypto
import pandas as pd

DATA_PLACEHOLDER = "__REPORT_DATA_JSON__"

FILENAME_RE = re.compile(r"^(?P<subj>.+)_(?P<eye>[A-Za-z]+)_(?P<visit>[A-Za-z0-9]+)_(?P<loc>\d+)\.[A-Za-z0-9]+$")


def load_workbook(path: Path, password: str | None) -> pd.DataFrame:
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


def classify(grade, ecd, ecd_bin):
    if grade is None:
        return "orphan_ecd_only"
    if grade == 0:
        return "excluded_poor_quality"
    if ecd is None:
        return "excluded_missing_ecd"
    return "pass" if ecd_bin == 1 else "fail"


def build_records(iq_df: pd.DataFrame, ecd_df: pd.DataFrame):
    iq = iq_df[["Filename", "Predicted Multi-class Grade"]].rename(
        columns={"Predicted Multi-class Grade": "grade"}
    )
    ecd = ecd_df[["Filename", "ECDValue", "Binary ECD"]].rename(
        columns={"ECDValue": "ecd", "Binary ECD": "bin"}
    )

    merged = pd.merge(iq, ecd, on="Filename", how="outer")

    records = []
    for row in merged.itertuples(index=False):
        subj, eye, visit, loc = parse_filename(row.Filename)
        grade = nullable_int(row.grade)
        ecd_val = nullable_round(row.ecd)
        ecd_bin = nullable_int(row.bin)
        records.append(
            {
                "f": row.Filename,
                "subj": subj,
                "eye": eye,
                "visit": visit,
                "loc": loc,
                "grade": grade,
                "ecd": ecd_val,
                "bin": ecd_bin,
                "cat": classify(grade, ecd_val, ecd_bin),
            }
        )

    records.sort(key=lambda r: (r["subj"], r["eye"], r["visit"], r["loc"]))
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iq", required=True, type=Path, help="Path to the multi-class IQ grade xlsx")
    parser.add_argument("--ecd", required=True, type=Path, help="Path to the ECD value xlsx")
    parser.add_argument("--iq-password", default=None, help="Password for the IQ xlsx, if encrypted")
    parser.add_argument("--ecd-password", default=None, help="Password for the ECD xlsx, if encrypted")
    parser.add_argument("--template", required=True, type=Path, help="Path to report_template.html")
    parser.add_argument("--out", required=True, type=Path, help="Path to write the generated report")
    args = parser.parse_args()

    iq_df = load_workbook(args.iq, args.iq_password)
    ecd_df = load_workbook(args.ecd, args.ecd_password)

    records = build_records(iq_df, ecd_df)
    data_json = json.dumps(records)

    template_html = args.template.read_text(encoding="utf-8")
    if DATA_PLACEHOLDER not in template_html:
        raise SystemExit(f"Template is missing the {DATA_PLACEHOLDER} placeholder.")
    report_html = template_html.replace(DATA_PLACEHOLDER, data_json)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report_html, encoding="utf-8")

    print(f"Wrote {args.out} ({len(records)} image records)")


if __name__ == "__main__":
    main()

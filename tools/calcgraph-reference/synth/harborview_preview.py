"""Generate a small, clearly synthetic Harborview PDF for parser and UI previews."""

from __future__ import annotations

import argparse
import io
import json
import unicodedata
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[3]
BUNDLE_PATH = ROOT / "data" / "harborview-tower-rev1-base.bundle.json"
DEFAULT_OUTPUT = ROOT / "data" / "harborview-demo-calcs-preview.pdf"

NAVY = (0.12, 0.18, 0.25)
BLUE = (0.24, 0.39, 0.50)
RED = (0.68, 0.18, 0.18)
INK = (0.16, 0.20, 0.23)
MUTED = (0.38, 0.43, 0.46)
PALE = (0.93, 0.95, 0.96)
RULE = (0.77, 0.81, 0.83)
WHITE = (1, 1, 1)

SHEET_SPECS = (
    ("doc-fdn-a1", ("pcap-A1", "pile-A1")),
    ("doc-girder-line-1-l01", ("girder-A1-B1-L01", "girder-B1-C1-L01", "girder-C1-D1-L01", "girder-D1-E1-L01")),
    ("doc-col-stack-a1", ("col-A1-L01", "col-A1-L02", "col-A1-L03", "col-A1-L04", "col-A1-L05")),
)
BASEPLATE_CALC_KEY = "doc-conn-baseplates"


def ascii_text(value: object) -> str:
    return unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")


def load_preview_data() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    bundle = json.loads(BUNDLE_PATH.read_text(encoding="utf-8"))
    nodes = bundle["elementGraph"]["nodes"]
    elements = {node["id"]: node for node in nodes}
    calcs = {calc["key"]: calc for calc in bundle["calcGraph"]["calcs"]}

    sheets: list[dict[str, object]] = []
    for calc_key, element_ids in SHEET_SPECS:
        calc = calcs.get(calc_key)
        if calc is None:
            raise ValueError(f"Harborview bundle is missing calculation {calc_key!r}")
        rows = [elements[element_id] for element_id in element_ids if element_id in elements]
        if len(rows) != len(element_ids):
            raise ValueError(f"Harborview bundle is missing elements for {calc_key!r}")
        sheets.append({"calc": calc, "elements": rows})

    baseplate_calc = calcs.get(BASEPLATE_CALC_KEY)
    if baseplate_calc is None:
        raise ValueError(f"Harborview bundle is missing calculation {BASEPLATE_CALC_KEY!r}")
    baseplates = sorted(
        (node for node in nodes if node.get("kind") == "connection" and str(node.get("mark", "")).startswith("BP-")),
        key=lambda node: str(node["mark"]),
    )
    if not baseplates:
        raise ValueError("Harborview bundle contains no base-plate elements")
    sheets.append({"calc": baseplate_calc, "elements": baseplates})
    return sheets, nodes


def element_token(element: dict[str, object]) -> str:
    return ascii_text(element.get("mark", "")).replace(" ", "")


def draw_cover(doc: pymupdf.Document, sheets: list[dict[str, object]]) -> None:
    page = doc.new_page(width=612, height=792)
    page.draw_rect(pymupdf.Rect(0, 0, 612, 12), color=None, fill=NAVY)
    page.insert_text((42, 51), "COVER SHEET", fontname="cour", fontsize=8, color=MUTED)
    page.insert_text((42, 67), "HARBORVIEW TOWER", fontname="hebo", fontsize=13, color=BLUE)
    page.insert_text((42, 112), "Model-linked calc preview", fontname="hebo", fontsize=28, color=NAVY)
    page.draw_rect(pymupdf.Rect(42, 142, 570, 190), color=None, fill=RED)
    page.insert_text((56, 162), "DEMO ONLY - NOT FOR CONSTRUCTION", fontname="hebo", fontsize=16, color=WHITE)
    page.insert_text((56, 180), "No loads, capacities, or engineering conclusions are represented.", fontname="helv", fontsize=9, color=WHITE)

    page.insert_text((42, 230), "What this file demonstrates", fontname="hebo", fontsize=12, color=INK)
    page.insert_textbox(
        pymupdf.Rect(42, 242, 560, 292),
        "A short, synthetic PDF package for checking calculation segmentation, model-mark matching, "
        "and highlighted PDF evidence in the Harborview demo. Loads, capacities, code checks, and "
        "engineering conclusions are intentionally omitted.",
        fontname="helv",
        fontsize=10,
        color=INK,
        lineheight=1.35,
    )
    page.insert_text((42, 326), "Included calculation sheets", fontname="hebo", fontsize=12, color=INK)

    y = 350
    for sheet in sheets:
        calc = sheet["calc"]
        page.draw_line((42, y + 6), (570, y + 6), color=RULE, width=0.6)
        page.insert_text((48, y), ascii_text(calc["title"]), fontname="helv", fontsize=9, color=INK)
        y += 24

    page.draw_rect(pymupdf.Rect(42, 618, 570, 700), color=RULE, fill=PALE, width=0.8)
    page.insert_text((56, 642), "Use only as preview data", fontname="hebo", fontsize=11, color=NAVY)
    page.insert_textbox(
        pymupdf.Rect(56, 650, 552, 690),
        "Do not use for design, construction, permitting, or reliance. To preview extraction, load "
        "the Harborview A/B demo and add this file from Project > Add calc PDFs.",
        fontname="helv",
        fontsize=9,
        color=INK,
        lineheight=1.3,
    )
    page.insert_text((42, 754), "SYNTHETIC DATASET  |  REV 1 MODEL REFERENCES", fontname="cour", fontsize=7, color=MUTED)


def draw_calc_sheet(page: pymupdf.Page, sheet: dict[str, object], page_number: int) -> None:
    calc = sheet["calc"]
    elements = sheet["elements"]
    title = ascii_text(calc["title"])
    if calc["key"] == BASEPLATE_CALC_KEY:
        title += " Calc"

    page.draw_rect(pymupdf.Rect(0, 0, 612, 25), color=None, fill=RED)
    page.insert_text((40, 17), "DEMO ONLY - NOT FOR CONSTRUCTION", fontname="hebo", fontsize=10, color=WHITE)
    page.insert_text((40, 49), "HARBORVIEW CORPORATE CENTER  /  SYNTHETIC PREVIEW", fontname="cour", fontsize=7.5, color=BLUE)
    page.insert_textbox(
        pymupdf.Rect(40, 58, 572, 116),
        title,
        fontname="hebo",
        fontsize=17,
        color=NAVY,
        lineheight=1.1,
    )
    page.insert_text((40, 129), f"SHEET {page_number:02d}  |  REV 1 MODEL  |  PREVIEW RECORD", fontname="cour", fontsize=8, color=MUTED)
    page.draw_line((40, 145), (572, 145), color=BLUE, width=1.1)

    page.insert_text((40, 173), "Model references", fontname="hebo", fontsize=12, color=INK)
    page.draw_rect(pymupdf.Rect(40, 177, 572, 201), color=None, fill=BLUE)
    page.insert_text((48, 192), "PDF mark", fontname="hebo", fontsize=8, color=WHITE)
    page.insert_text((178, 192), "Element kind", fontname="hebo", fontsize=8, color=WHITE)
    page.insert_text((282, 192), "Model profile", fontname="hebo", fontsize=8, color=WHITE)

    row_top = 201
    row_height = min(15, 310 / max(len(elements), 1))
    for index, element in enumerate(elements):
        y = row_top + index * row_height
        if index % 2 == 0:
            page.draw_rect(pymupdf.Rect(40, y, 572, y + row_height), color=None, fill=PALE)
        baseline = y + row_height - 4
        page.insert_text((48, baseline), element_token(element), fontname="cour", fontsize=7.2, color=INK)
        page.insert_text((178, baseline), ascii_text(element.get("kind", "element")), fontname="helv", fontsize=7.2, color=INK)
        page.insert_text((282, baseline), ascii_text(element.get("profile") or "Not provided"), fontname="helv", fontsize=7.2, color=INK)
        page.draw_line((40, y + row_height), (572, y + row_height), color=RULE, width=0.35)

    section_y = row_top + len(elements) * row_height + 22
    page.insert_text((40, section_y), "Preview record", fontname="hebo", fontsize=12, color=INK)
    box_top = section_y + 10
    page.draw_rect(pymupdf.Rect(40, box_top, 572, box_top + 103), color=RULE, fill=(0.97, 0.98, 0.98), width=0.7)
    page.insert_text((52, box_top + 23), "Demand, capacity, and code checks: not supplied.", fontname="helv", fontsize=9, color=INK)
    page.insert_text((52, box_top + 43), "Design status: no calculation performed or reviewed.", fontname="helv", fontsize=9, color=INK)
    page.insert_textbox(
        pymupdf.Rect(52, box_top + 54, 558, box_top + 94),
        "Use this sheet only to preview PDF extraction, calc grouping, mark matching, and evidence highlighting.",
        fontname="helv",
        fontsize=8.5,
        color=MUTED,
        lineheight=1.25,
    )

    page.draw_line((40, 730), (572, 730), color=RULE, width=0.6)
    page.insert_text((40, 746), "SYNTHETIC DEMONSTRATION ONLY - NOT FOR DESIGN, CONSTRUCTION, OR PERMITTING", fontname="hebo", fontsize=7, color=RED)
    page.insert_text((538, 764), f"{page_number:02d}", fontname="cour", fontsize=7, color=MUTED)


def render_pdf() -> bytes:
    sheets, _ = load_preview_data()
    doc = pymupdf.open()
    draw_cover(doc, sheets)
    for index, sheet in enumerate(sheets, start=2):
        draw_calc_sheet(doc.new_page(width=612, height=792), sheet, index)
    doc.set_metadata(
        {
            "title": "Harborview synthetic calculation preview",
            "author": "unLoaded demo data",
            "subject": "Synthetic parser and UI preview; not engineering calculations",
            "keywords": "synthetic, demo, not for construction",
            "creator": "tools/calcgraph-reference/synth/harborview_preview.py",
            "producer": "PyMuPDF",
            "creationDate": "D:20260101000000Z",
            "modDate": "D:20260101000000Z",
        }
    )
    output = io.BytesIO()
    doc.save(output, garbage=4, deflate=True, no_new_id=True)
    doc.close()
    return output.getvalue()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT, help="output PDF path")
    parser.add_argument("--check", action="store_true", help="fail if the existing PDF differs from generated output")
    args = parser.parse_args()
    generated = render_pdf()
    if args.check:
        if not args.out.exists() or args.out.read_bytes() != generated:
            raise SystemExit(f"{args.out} is missing or out of date")
        print(f"Harborview preview is byte-stable: {args.out}")
        return
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(generated)
    print(f"Wrote {args.out} ({len(generated)} bytes)")


if __name__ == "__main__":
    main()

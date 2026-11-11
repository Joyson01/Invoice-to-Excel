#!/usr/bin/env python3
"""
Keep only the FIRST label page of each AWB
==========================================

A merged label PDF holds one page per package: an AWB with 9 boxes prints 9
near-identical labels (...754001, ...754002 ... ...754009). This keeps the
first page of each AWB and drops the rest, preserving the original page order
and the pages themselves (no re-rendering, no quality loss).

Usage
-----
Put the label PDF(s) in a "labels" folder next to this script, then:

    python first_label_per_awb.py

    -> output/mergedPdf_first-label_05-09-2026_161230.pdf
       output/mergedPdf_first-label_05-09-2026_161230_pages.csv

Options
-------
    --input PATH...     PDF file(s)/folder(s)      (default: ./labels, then ./)
    --output PATH       file or folder             (default: ./output/)
    --merge             combine all input PDFs into one output, deduping across them
    --keep last         keep the last label of each AWB instead of the first
    --key package       dedupe on the full package barcode instead of the AWB
                        (i.e. only remove exact duplicate pages)
    --dry-run           report what would be kept, write nothing
    --doctor            show what was detected on every page, then exit

Dependencies:  pip install pypdf pdfplumber
"""

from __future__ import annotations

import argparse
import csv
import logging
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import warnings
warnings.filterwarnings("ignore", message=".*ARC4.*")   # noisy pypdf/cryptography notice

import pdfplumber
from pypdf import PdfReader, PdfWriter

VERSION = "1.0"

# --- config ---------------------------------------------------------------
DEFAULT_INPUT_DIRNAME = "labels"
DEFAULT_OUTPUT_DIRNAME = "output"
OUTPUT_SUFFIX = "first-label"
TIMESTAMP_FORMAT = "%d-%m-%Y_%H%M%S"

# How the AWB is found on a page, tried in order. First capturing group wins.
# Add your courier's pattern here if you switch carriers.
AWB_PATTERNS = [
    r"Shipment\s*:\s*([A-Z]{0,3}\d{8,})",        # Movin: "Shipment: H90304969754"
    r"AWB\s*(?:No\.?|Number)?\s*:?\s*([A-Z]{0,3}\d{8,})",
    r"Waybill\s*(?:No\.?|Number)?\s*:?\s*([A-Z]{0,3}\d{8,})",
    r"Tracking\s*(?:ID|No\.?|Number)?\s*:?\s*([A-Z]{0,3}\d{8,})",
]
# Per-package barcode, e.g. H90304969754007 -> AWB H90304969754 + package 007.
PACKAGE_PATTERN = r"\b([A-Z]{0,3}\d{8,})(\d{3})\b"
# Package-count field, used only as a sanity check in the report.
TOTAL_PACKAGES_PATTERN = r"Total\s*Packages\s*:\s*(\d+)"

log = logging.getLogger("labels")


@dataclass
class Page:
    source: str
    index: int              # 0-based page number in its source PDF
    awb: str = ""
    package: str = ""
    total_packages: str = ""
    note: str = ""

    @property
    def human(self) -> str:
        return f"{Path(self.source).name} p{self.index + 1}"


def _first_match(text: str, patterns: list[str]) -> str:
    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m:
            return m.group(1).strip()
    return ""


def scan(path: str) -> list[Page]:
    """Read every page of one PDF and work out its AWB."""
    pages: list[Page] = []
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            p = Page(source=path, index=i)

            if not text.strip():
                p.note = "no text layer (scanned/image label) - kept"
                pages.append(p)
                continue

            pkg_match = re.search(PACKAGE_PATTERN, text)
            if pkg_match:
                p.package = pkg_match.group(1) + pkg_match.group(2)

            p.awb = _first_match(text, AWB_PATTERNS)
            if not p.awb and pkg_match:
                p.awb = pkg_match.group(1)      # strip the 3-digit package suffix
                p.note = "AWB derived from package barcode"
            if not p.awb:
                p.note = "no AWB found - kept"

            tot = re.search(TOTAL_PACKAGES_PATTERN, text, re.I)
            if tot:
                p.total_packages = tot.group(1)

            pages.append(p)
    return pages


def choose(pages: list[Page], key: str = "awb", keep: str = "first") -> list[Page]:
    """Pick one page per AWB (or per package). Pages with no key are all kept."""
    chosen: dict[str, Page] = {}
    unkeyed: list[Page] = []
    for p in pages:
        k = p.package if key == "package" else p.awb
        if not k:
            unkeyed.append(p)
            continue
        if k not in chosen or keep == "last":
            chosen[k] = p
    out = list(chosen.values()) + unkeyed
    out.sort(key=lambda p: (p.source, p.index))     # keep original order
    return out


def write_pdf(selected: list[Page], output: str) -> None:
    writer = PdfWriter()
    readers: dict[str, PdfReader] = {}
    for p in selected:
        if p.source not in readers:
            readers[p.source] = PdfReader(p.source)
        writer.add_page(readers[p.source].pages[p.index])
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    with open(output, "wb") as fh:
        writer.write(fh)


def write_manifest(path: str, pages: list[Page], selected: set[tuple[str, int]]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["source_file", "page", "awb", "package", "total_packages",
                    "kept", "note"])
        for p in pages:
            w.writerow([Path(p.source).name, p.index + 1, p.awb, p.package,
                        p.total_packages,
                        "YES" if (p.source, p.index) in selected else "",
                        p.note])


# --- paths ----------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent


def _search_dirs() -> list[Path]:
    out, seen = [], set()
    for d in (Path.cwd(), BASE_DIR):
        if d not in seen:
            seen.add(d)
            out.append(d)
    return out


def default_input() -> list[str]:
    for d in _search_dirs():
        cand = d / DEFAULT_INPUT_DIRNAME
        if cand.is_dir() and any(cand.rglob("*.pdf")):
            return [str(cand)]
    for d in _search_dirs():
        if any(d.glob("*.pdf")):
            return [str(d)]
    return [str(Path.cwd() / DEFAULT_INPUT_DIRNAME)]


def find_pdfs(inputs, recursive=True) -> list[str]:
    files: list[str] = []
    for item in inputs:
        p = Path(item)
        if p.is_dir():
            files.extend(str(f) for f in (p.rglob("*.pdf") if recursive else p.glob("*.pdf")))
        elif p.is_file():
            files.append(str(p))
        else:
            log.warning("not found: %s", item)
    # never re-process our own outputs
    files = [f for f in files if OUTPUT_SUFFIX not in Path(f).name]
    return sorted(set(files))


def output_for(src: str | None, arg: str | None, stamp: str) -> str:
    stem = Path(src).stem if src else "labels"
    name = f"{stem}_{OUTPUT_SUFFIX}_{stamp}.pdf"
    if arg is None:
        return str(Path.cwd() / DEFAULT_OUTPUT_DIRNAME / name)
    p = Path(arg)
    if p.is_dir() or arg.endswith(("/", os.sep)) or p.suffix == "":
        return str(p / name)
    return str(p.with_name(f"{p.stem}_{stamp}{p.suffix or '.pdf'}"))


# --- CLI ------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Keep only the first label page of each AWB in a merged label PDF.")
    ap.add_argument("--input", "-i", nargs="+", help=f"PDF(s)/folder(s). Default: ./{DEFAULT_INPUT_DIRNAME}")
    ap.add_argument("--output", "-o", help=f"file or folder. Default: ./{DEFAULT_OUTPUT_DIRNAME}/")
    ap.add_argument("--merge", action="store_true",
                    help="one combined output, deduped across all input files")
    ap.add_argument("--keep", choices=["first", "last"], default="first")
    ap.add_argument("--key", choices=["awb", "package"], default="awb")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--doctor", action="store_true")
    ap.add_argument("--no-manifest", action="store_true")
    ap.add_argument("--quiet", "-q", action="store_true")
    ap.add_argument("--version", action="version", version=f"first_label_per_awb {VERSION}")
    a = ap.parse_args(argv)

    logging.basicConfig(level=logging.WARNING if a.quiet else logging.INFO,
                        format="%(levelname)-7s %(message)s")
    log.info("first_label_per_awb v%s  |  python %s", VERSION, sys.version.split()[0])

    inputs = a.input or default_input()
    pdfs = find_pdfs(inputs)
    if not pdfs:
        log.error("no PDFs found in: %s", ", ".join(inputs))
        log.error("put the label PDF in a '%s' folder next to this script, "
                  "or pass --input PATH", DEFAULT_INPUT_DIRNAME)
        return 1
    log.info("input: %d PDF(s)", len(pdfs))

    stamp = datetime.now().strftime(TIMESTAMP_FORMAT)
    all_pages: list[Page] = []
    for f in pdfs:
        try:
            all_pages.extend(scan(f))
        except Exception as exc:                               # noqa: BLE001
            log.error("FAILED %s: %s", Path(f).name, exc)

    if a.doctor:
        for p in all_pages:
            log.info("%-28s awb=%-16s pkg=%-18s %s",
                     p.human, p.awb or "-", p.package or "-", p.note)
        return 0

    groups = {None: all_pages} if a.merge else \
             {f: [p for p in all_pages if p.source == f] for f in pdfs}

    total_in = total_out = 0
    for src, pages in groups.items():
        if not pages:
            continue
        selected = choose(pages, key=a.key, keep=a.keep)
        sel_ids = {(p.source, p.index) for p in selected}
        total_in += len(pages)
        total_out += len(selected)

        awbs = sorted({p.awb for p in pages if p.awb})
        label = Path(src).name if src else f"{len(pdfs)} file(s) merged"
        log.info("%s: %d page(s), %d AWB(s) -> keeping %d page(s)",
                 label, len(pages), len(awbs), len(selected))
        for p in selected:
            if p.note:
                log.warning("  %s: %s", p.human, p.note)

        if a.dry_run:
            continue

        out = output_for(src or pdfs[0], a.output, stamp)
        if src is None:
            out = output_for("labels_merged", a.output, stamp)
        write_pdf(selected, out)
        log.info("  wrote %s", out)
        if not a.no_manifest:
            man = str(Path(out).with_suffix("")) + "_pages.csv"
            write_manifest(man, pages, sel_ids)
            log.info("  wrote %s", man)

    print(f"\nDone. {total_in} page(s) in -> {total_out} page(s) kept"
          + (" (dry run, nothing written)" if a.dry_run else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())

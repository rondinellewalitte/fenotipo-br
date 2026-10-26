"""Render reports/piloto.pdf from reports/piloto.md, for readers without a Markdown viewer.
Markdown -> HTML with markdown-it-py, then HTML -> PDF with headless Chrome or Edge, which
use system fonts (so symbols such as ≈ and 10⁻⁵ render). Run after build_piloto.py.

    uv run python reports/build_piloto_pdf.py

Set CHROME to the browser executable if it is not in a standard location.
"""
# ruff: noqa: E501  (the CSS below keeps one rule per line)

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from html import escape
from pathlib import Path

from markdown_it import MarkdownIt
from pypdf import PdfReader, PdfWriter

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "reports" / "piloto.md"
OUT = ROOT / "reports" / "piloto.pdf"
AUTHOR = "R. Walitte (ORCID 0009-0004-1776-2754)"
BROWSERS = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "google-chrome",
    "chromium",
    "msedge",
)
# Text that must never reach the PDF: a browser header/footer would print the local file URL.
FORBIDDEN = ("file:///", str(Path.home()), "C:\\Users")
CSS = """
@page { size: A4; margin: 18mm 17mm 20mm 17mm;
  @bottom-center { content: counter(page) " / " counter(pages); font: 8pt Arial, sans-serif; color: #666; } }
body { font-family: "Segoe UI", Arial, sans-serif; font-size: 10pt; line-height: 1.45; color: #1a1a1a; }
h1 { font-size: 17pt; margin: 0 0 6pt; }
h2 { font-size: 13pt; margin: 16pt 0 6pt; padding-bottom: 2pt; border-bottom: 1px solid #bbb; }
h3 { font-size: 11pt; margin: 12pt 0 4pt; }
h1, h2, h3 { break-after: avoid; }
p, li { margin: 3pt 0; }
ul, ol { padding-left: 16pt; }
blockquote { margin: 8pt 0; padding: 4pt 10pt; border-left: 3px solid #999; background: #f4f4f4; }
code { font-family: Consolas, "Courier New", monospace; font-size: 8.5pt; background: #f1f1f1; padding: 0 2pt; }
table { border-collapse: collapse; margin: 6pt 0 8pt; font-size: 8.5pt; width: 100%; }
th, td { border: 1px solid #c8c8c8; padding: 2.5pt 4pt; text-align: left; vertical-align: top; }
th { background: #e8e8e8; }
tr { break-inside: avoid; }
"""


def find_browser() -> str:
    for cand in (os.environ.get("CHROME"), *BROWSERS):
        if cand and (Path(cand).is_file() or shutil.which(cand)):
            return shutil.which(cand) or cand
    raise SystemExit("Chrome or Edge not found; set CHROME to the browser executable.")


def to_html(md: str) -> str:
    title = next((ln[2:].strip() for ln in md.splitlines() if ln.startswith("# ")), "Piloto")
    body = MarkdownIt("commonmark", {"html": False}).enable("table").render(md)
    return (
        f'<!doctype html>\n<html lang="pt-BR"><head><meta charset="utf-8">'
        f"<title>{escape(title)}</title><style>{CSS}</style></head>\n<body>\n{body}</body></html>\n"
    )


def print_pdf(browser: str, html: Path, out: Path, profile: Path) -> None:
    subprocess.run(
        [
            browser,
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            "--no-pdf-header-footer",
            f"--user-data-dir={profile}",
            f"--print-to-pdf={out}",
            html.as_uri(),
        ],
        check=True,
        capture_output=True,
        timeout=120,
    )


def main() -> None:
    md = SRC.read_text(encoding="utf-8")
    browser = find_browser()
    with tempfile.TemporaryDirectory() as tmp:
        html, raw = Path(tmp) / "piloto.html", Path(tmp) / "piloto.pdf"
        html.write_text(to_html(md), encoding="utf-8")
        print_pdf(browser, html, raw, Path(tmp) / "profile")
        reader = PdfReader(raw)
        text = "\n".join(p.extract_text() or "" for p in reader.pages)
        leaked = [s for s in FORBIDDEN if s in text]
        if leaked:
            raise SystemExit(f"PDF contains local paths {leaked}; not written.")
        writer = PdfWriter(clone_from=reader)
        writer.add_metadata(
            {"/Author": AUTHOR, "/Subject": "Gerado de reports/piloto.md por build_piloto_pdf.py"}
        )
        with OUT.open("wb") as f:
            writer.write(f)
    first = md.splitlines()[0].lstrip("# ").strip()
    assert first.split(":")[0] in text, "title missing from the PDF text"
    print(f"-> {OUT} ({len(reader.pages)} pages, browser {Path(browser).name})")


if __name__ == "__main__":
    main()

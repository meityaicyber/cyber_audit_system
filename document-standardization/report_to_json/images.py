"""
Image offloading and page masking.

1. ``offload_images`` stores every embedded image in deep storage. Each placement
   large enough to be a figure gets a tag such as ``[IMAGE_PAGE_3_FIG_1]``.
   Smaller placements (slices of a rasterised table header, icons, rules) are
   layout, not figures: they are stored and listed in the manifest but left
   visible on the page, because masking them would hide text the model must read.
2. ``render_masked_page`` renders a page for the vision model with each image
   covered by a white box containing its tag, so the model transcribes the
   pointer at the exact position the image occupied.
3. ``reconcile_tags`` repairs the model's output afterwards: misread tags are
   mapped back to the real ones and any tag the model dropped is appended to
   the page, so no image pointer is ever lost.
"""

from __future__ import annotations

import difflib
import logging
import os
import re
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageFont

from .storage import DeepStorage, StoredImage

log = logging.getLogger(__name__)

TAG_RE = re.compile(r"\[\s*IMAGE[_ ]PAGE[_ ](\d+)[_ ]FIG[_ ](\d+)\s*\]", re.IGNORECASE)
# Loose form used to catch OCR-mangled tags ("[IMAGE_PAGE_3_FIG_l]", "[lMAGE PAGE 3 FIG 1]").
_LOOSE_TAG_RE = re.compile(r"\[\s*[I1l]MAGE[\s_]*PAGE[\s_]*[\dOoIl]+[\s_]*F[I1l]G[\s_]*[\dOoIl]+\s*\]", re.IGNORECASE)
MIN_IMAGE_PX = 8  # below this the "image" is a spacer pixel, not worth storing


def min_figure_box_pt() -> float:
    """Placements whose shorter side is smaller than this (PDF points) are layout, not figures."""
    try:
        return float(os.environ.get("MIN_FIGURE_BOX_PT", 40))
    except ValueError:
        return 40.0


def make_tag(page: int, figure: int) -> str:
    return f"[IMAGE_PAGE_{page}_FIG_{figure}]"


@dataclass
class Offload:
    figures: Dict[int, List[StoredImage]]   # {page: tagged placements}, masked in pass 1
    layout: List[StoredImage]               # stored but left visible (tag is "")

    def all_figures(self) -> List[StoredImage]:
        return [r for records in self.figures.values() for r in records]


def offload_images(pdf_path: str, storage: DeepStorage) -> Offload:
    """Store every image; tag and return the placements that are figures."""
    figures: Dict[int, List[StoredImage]] = {}
    layout: List[StoredImage] = []
    min_box = min_figure_box_pt()
    with fitz.open(pdf_path) as doc:
        for page in doc:
            page_no = page.number + 1
            records: List[StoredImage] = []
            seen_xrefs = set()
            for info in page.get_images(full=True):
                xref = info[0]
                if xref in seen_xrefs:  # listed again via another XObject; its placements are already handled
                    continue
                seen_xrefs.add(xref)
                # Where the image is actually drawn on this page. Empty when it is only listed in
                # shared resources, in which case it belongs to whichever page draws it.
                rects = [r for r in page.get_image_rects(xref) if not r.is_empty]
                if not rects:
                    continue
                base = doc.extract_image(xref)
                if not base or min(base.get("width", 0), base.get("height", 0)) < MIN_IMAGE_PX:
                    continue
                sha256, uri = storage.put(base["image"], base.get("ext", "png"))
                meta = dict(sha256=sha256, uri=uri, format=base.get("ext", "png"),
                            width=base.get("width", 0), height=base.get("height", 0))
                for rect in rects:  # the same image drawn twice gets two tags
                    bbox = [round(v, 2) for v in rect]
                    if min(rect.width, rect.height) < min_box:
                        layout.append(StoredImage(tag="", page=page_no, figure=0, bbox=bbox, **meta))
                        continue
                    fig = len(records) + 1
                    records.append(StoredImage(tag=make_tag(page_no, fig), page=page_no, figure=fig,
                                               bbox=bbox, **meta))
            if records:
                figures[page_no] = records
    log.info("Offloaded %d figure(s) and %d layout image(s)",
             sum(len(v) for v in figures.values()), len(layout))
    return Offload(figures, layout)


def _font(size: int) -> ImageFont.ImageFont:
    for name in ("DejaVuSansMono-Bold.ttf", "consolab.ttf", "courbd.ttf", "DejaVuSansMono.ttf", "consola.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def render_masked_page(page: fitz.Page, images: Sequence[StoredImage], dpi: int) -> Image.Image:
    """Render ``page`` with each placed image replaced by a labelled box."""
    zoom = dpi / 72.0
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    draw = ImageDraw.Draw(img)
    for record in images:
        if record.bbox is None:
            continue
        x0, y0, x1, y1 = (v * zoom for v in record.bbox)
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(img.width - 1, x1), min(img.height - 1, y1)
        if x1 - x0 < 2 or y1 - y0 < 2:
            continue
        draw.rectangle([x0, y0, x1, y1], fill="white", outline="black", width=max(1, int(zoom)))
        # Largest font (up to ~14pt) that fits the box; never smaller than a legible minimum.
        min_size = max(12, int(zoom * 8))
        size = max(min_size, min(int((y1 - y0) * 0.5), int(zoom * 14)))
        font = _font(size)
        while size > min_size and draw.textlength(record.tag, font=font) > (x1 - x0) * 0.95:
            size -= 1
            font = _font(size)
        left, top, right, bottom = draw.textbbox((0, 0), record.tag, font=font)
        tw, th = right - left, bottom - top
        tx = (x0 + x1 - tw) / 2
        ty = (y0 + y1 - th) / 2
        tx = min(max(2, tx), img.width - tw - 2)
        # The label keeps its own white plate so it stays legible even when wider than the box.
        pad = max(2, size // 4)
        draw.rectangle([tx - pad, ty - pad, tx + tw + pad, ty + th + pad], fill="white", outline="black")
        draw.text((tx - left, ty - top), record.tag, fill="black", font=font)
    return img


def reconcile_tags(markdown: str, expected: Sequence[StoredImage]) -> Tuple[str, List[str]]:
    """Normalise image tags in a page transcript against the page's real tags.

    Returns the repaired Markdown and a list of issues (for ``_meta``).
    """
    wanted = [r.tag for r in expected]
    issues: List[str] = []

    def fix(match: re.Match) -> str:
        raw = match.group(0)
        canonical = TAG_RE.fullmatch(raw)
        if canonical:
            tag = make_tag(int(canonical.group(1)), int(canonical.group(2)))
            if tag in wanted:
                return tag
        close = difflib.get_close_matches(raw.upper().replace(" ", "_"), wanted, n=1, cutoff=0.8)
        if close:
            if close[0] != raw:
                issues.append(f"misread tag {raw!r} corrected to {close[0]}")
            return close[0]
        issues.append(f"unknown image tag {raw!r} left as text")
        return raw

    repaired = _LOOSE_TAG_RE.sub(fix, markdown)
    missing = [tag for tag in wanted if tag not in repaired]
    if missing:
        issues.append(f"tags not transcribed, appended to page end: {missing}")
        repaired = repaired.rstrip() + "\n\n" + "\n".join(missing)
    return repaired, issues

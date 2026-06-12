"""Generate a fake-data PDF that reproduces the LiteParse 'missing text' bug.

The bug: some lines are drawn as *vector glyph outlines* (filled Bezier paths),
not as real PDF text. They render perfectly but carry no character codes, so no
text extractor can read them. LiteParse would normally rescue them via OCR — but
only if the page looks text-sparse. This page is deliberately TEXT-DENSE
(coverage well above LiteParse's 0.15 threshold) so `needs_ocr = false` and the
outlined lines are dropped silently, exactly like the real client document.

All content is fictional.
"""

from __future__ import annotations

from pathlib import Path

from fontTools.pens.basePen import BasePen
from fontTools.ttLib import TTFont
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont as RLTTFont
from reportlab.pdfgen import canvas

REG_TTF = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
BOLD_TTF = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
OUT = Path("pdf/synthetic_missing_text_repro.pdf")

PAGE_W, PAGE_H = letter  # 612 x 792
LEFT = 72
RIGHT = 540
TOP = 720
LEADING = 14
BODY_SIZE = 10.5
HEAD_SIZE = 12


class _PDFPathPen(BasePen):
    """Collects a glyph outline as a reportlab path, scaled to font size."""

    def __init__(self, glyph_set, rl_path, scale, x0, y0):
        super().__init__(glyph_set)
        self.p = rl_path
        self.s = scale
        self.x0 = x0
        self.y0 = y0

    def _pt(self, pt):
        return self.x0 + pt[0] * self.s, self.y0 + pt[1] * self.s

    def _moveTo(self, pt):
        x, y = self._pt(pt)
        self.p.moveTo(x, y)

    def _lineTo(self, pt):
        x, y = self._pt(pt)
        self.p.lineTo(x, y)

    def _curveToOne(self, p1, p2, p3):
        (x1, y1), (x2, y2), (x3, y3) = self._pt(p1), self._pt(p2), self._pt(p3)
        self.p.curveTo(x1, y1, x2, y2, x3, y3)

    def _closePath(self):
        self.p.close()


class OutlineDrawer:
    """Draws a string as filled vector outlines (NOT real text)."""

    def __init__(self, ttf_path: str):
        self.font = TTFont(ttf_path)
        self.upm = self.font["head"].unitsPerEm
        self.glyph_set = self.font.getGlyphSet()
        self.cmap = self.font.getBestCmap()
        self.hmtx = self.font["hmtx"]

    def draw(self, c: canvas.Canvas, text: str, x: float, y: float, size: float):
        scale = size / self.upm
        pen_x = x
        for ch in text:
            gname = self.cmap.get(ord(ch))
            if gname is None:
                gname = ".notdef"
            adv = self.hmtx[gname][0]
            if ch != " ":
                path = c.beginPath()
                pen = _PDFPathPen(self.glyph_set, path, scale, pen_x, y)
                self.glyph_set[gname].draw(pen)
                c.drawPath(path, fill=1, stroke=0)
            pen_x += adv * scale
        return pen_x


# (text, is_heading, render_as_outline)
LINES = [
    ("NORTHWIND LOGISTICS - MASTER SERVICES AGREEMENT (FICTIONAL)", True, False),
    ("", False, False),
    ("1. Engagement", True, False),
    ("Vendor shall provide the organization, management, and coordination of the", False, False),
    ("logistics services and the development of the operating plan described herein.", False, False),
    ("Client shall afford Vendor a reasonable opportunity to review and provide input", False, False),
    # --- BUG LINE 1 (vector outlines, no text layer) ---
    ("on the form and content of the operating plan, and confirm that Vendor data is", False, True),
    ("accurately described and identified in it prior to submission to the Steering Board.", False, False),
    ("", False, False),
    ("2. Subcontracting", True, False),
    ("Vendor and Client shall endeavor in good faith to negotiate and enter into a", False, False),
    ("subcontract setting forth the scope of services and the basis for compensation,", False, False),
    ("and shall incorporate the agreed terms of the Master Agreement. Each of Vendor", False, False),
    # --- BUG LINE 2 (vector outlines, no text layer) ---
    ("approved subcontractors will have an obligation to meet certain diversity sourcing", False, True),
    ("requirements for their respective work segments under this Agreement.", False, False),
    ("", False, False),
    ("3. Services", True, False),
    ("a. Planning-Phase Services: Vendor shall provide such technical and pricing input", False, False),
    ("in support of the development of a responsive operating plan as Client may request", False, False),
    ("pursuant to written task orders issued from time to time during the term hereof.", False, False),
    ("b. Post-Award Services: Subsequent to award, in the event Client requires services", False, False),
    ("prior to execution of the subcontract, the parties shall execute a limited notice to", False, False),
    ("proceed that identifies the early work and establishes the applicable compensation.", False, False),
    ("c. Ownership of Documents: Unless otherwise agreed by Client in writing, all the", False, False),
    ("materials resulting from the Services, including drawings, specifications, reports,", False, False),
    ("samples, and other documents, shall be deemed the property of Client and shall be", False, False),
    ("furnished to Client upon its request at the conclusion of the engagement period.", False, False),
    ("", False, False),
    ("4. Compensation and Reimbursement", True, False),
    ("Client will reimburse Vendor for direct labor costs times the labor multiplier", False, False),
    ("stipulated below, plus approved other direct costs incurred in the performance of", False, False),
    ("the Services. Direct labor costs shall mean wages and salaries actually paid to the", False, False),
    ("Vendor personnel, with no amounts added for profit or fee on such labor costs.", False, False),
    ("", False, False),
    ("This entire document is fictional and intended solely as a bug-report test fixture", False, False),
    ("for PDF text-extraction tooling, and contains no real or confidential information.", False, False),
]


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    pdfmetrics.registerFont(RLTTFont("DejaVu", REG_TTF))
    pdfmetrics.registerFont(RLTTFont("DejaVu-Bold", BOLD_TTF))
    outliner = OutlineDrawer(REG_TTF)

    c = canvas.Canvas(str(OUT), pagesize=letter)
    c.setTitle("Northwind Logistics - Sample Services Agreement (Fictional)")
    c.setAuthor("anonymous")

    y = TOP
    outline_count = 0
    for text, is_head, as_outline in LINES:
        if text == "":
            y -= LEADING
            continue
        size = HEAD_SIZE if is_head else BODY_SIZE
        if as_outline:
            # Drawn as filled glyph outlines -> visible but NOT extractable.
            outliner.draw(c, text, LEFT, y, size)
            outline_count += 1
        else:
            c.setFont("DejaVu-Bold" if is_head else "DejaVu", size)
            c.drawString(LEFT, y, text)
        y -= LEADING + (2 if is_head else 0)

    c.showPage()
    c.save()
    print(f"Wrote {OUT}  ({outline_count} lines flattened to vector outlines)")


if __name__ == "__main__":
    main()

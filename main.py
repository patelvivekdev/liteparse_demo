"""Parse PDFs with LiteParse, draw text bounding boxes, save to out/<doc_name>/results/."""

from __future__ import annotations

import io
import json
from pathlib import Path

from PIL import Image, ImageDraw
from liteparse import LiteParse

PDFS_DIR = Path("pdf")
OUT_DIR = Path("out")
BOX_COLOR = (255, 0, 0, 180)
BOX_WIDTH = 2


def page_to_image_bbox(
    item_x: float,
    item_y: float,
    item_w: float,
    item_h: float,
    page_w: float,
    page_h: float,
    img_w: int,
    img_h: int,
) -> tuple[int, int, int, int]:
    """Convert page coords (top-left origin) to image pixel coords."""
    scale_x = img_w / page_w
    scale_y = img_h / page_h
    left = int(item_x * scale_x)
    top = int(item_y * scale_y)
    right = int((item_x + item_w) * scale_x)
    bottom = int((item_y + item_h) * scale_y)
    return left, top, right, bottom


def draw_bounding_boxes(
    image_bytes: bytes,
    text_items: list,
    page_w: float,
    page_h: float,
) -> Image.Image:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    for item in text_items:
        bbox = page_to_image_bbox(
            item.x,
            item.y,
            item.width,
            item.height,
            page_w,
            page_h,
            img.width,
            img.height,
        )
        draw.rectangle(bbox, outline=BOX_COLOR[:3], width=BOX_WIDTH)

    return Image.alpha_composite(img, overlay)


def process_pdf(pdf_path: Path, out_dir: Path, parser: LiteParse) -> None:
    """Parse one PDF and write page images, text, and bounding-box JSON to out_dir."""
    out_dir.mkdir(parents=True, exist_ok=True)

    result = parser.parse(pdf_path)
    screenshots = parser.screenshot(pdf_path)
    screenshot_by_page = {s.page_num: s for s in screenshots}

    for page in result.pages:
        screenshot = screenshot_by_page.get(page.page_num)
        if screenshot is None:
            continue

        annotated = draw_bounding_boxes(
            screenshot.image_bytes,
            page.text_items,
            page.width,
            page.height,
        )

        out_image = out_dir / f"page_{page.page_num:03d}_bbox.png"
        annotated.convert("RGB").save(out_image)

        out_json = out_dir / f"page_{page.page_num:03d}_text_items.json"
        out_json.write_text(
            json.dumps(
                [
                    {
                        "text": item.text,
                        "x": item.x,
                        "y": item.y,
                        "width": item.width,
                        "height": item.height,
                        "font_name": item.font_name,
                        "font_size": item.font_size,
                        "confidence": item.confidence,
                    }
                    for item in page.text_items
                ],
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        out_txt = out_dir / f"page_{page.page_num:03d}.txt"
        out_txt.write_text(page.text, encoding="utf-8")

        print(
            f"  Page {page.page_num}: {len(page.text_items)} boxes -> "
            f"{out_image.name}, {out_txt.name}"
        )


def main() -> None:
    if not PDFS_DIR.is_dir():
        raise SystemExit(f"PDF directory not found: {PDFS_DIR.resolve()}")

    pdf_files = sorted(PDFS_DIR.glob("*.pdf"))
    if not pdf_files:
        raise SystemExit(f"No PDF files found in {PDFS_DIR.resolve()}")

    parser = LiteParse()

    for pdf_path in pdf_files:
        doc_name = pdf_path.stem
        results_dir = OUT_DIR / doc_name / "results"
        print(f"Processing {pdf_path.name} -> {results_dir}/")
        process_pdf(pdf_path, results_dir, parser)

    print(f"Done. Processed {len(pdf_files)} PDF(s) under {OUT_DIR.resolve()}")


if __name__ == "__main__":
    main()

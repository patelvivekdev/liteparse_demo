# LiteParse — missing text on dense pages with vector-outlined glyphs

## The issue

Some PDFs contain lines that are drawn as **vector glyph outlines** (filled Bézier paths shaped like letters) instead of as real PDF text. Such lines:

- **render perfectly** — they look identical to normal text on screen and in any rasterized image of the page, but
- carry **no character codes, no font mapping, no** `ToUnicode` — so no text extractor (LiteParse, `pdftotext`, PyMuPDF, etc.) can read or search them.

LiteParse can normally rescue this kind of content with OCR. But OCR is only run on pages that look **text-sparse**. The decision is per-page:

```rust
// crates/liteparse/src/ocr_merge.rs
let needs_ocr =
    text_length < 20 || text_coverage < 0.15 || has_images || page_is_garbled(page);
if !needs_ocr { continue; } // page is NOT rendered and NOT OCR'd
```

On a **text-dense** page — plenty of normal selectable text, no images,`text_coverage` above `0.15` — `needs_ocr` is `false`. LiteParse trusts the native text layer, **skips OCR entirely**, and any line that was flattened to vector outlines is **silently dropped**. It is visible in a screenshot but absent from the extracted text, with no recovery path.

This is easy to miss because it only triggers when *both* conditions hold at once: (1) the affected line has no real text layer, and (2) the surrounding page is dense enough that LiteParse never falls back to OCR. A page with the same flattened line but sparse surrounding text gets OCR'd and the line is recovered — which makes the bug look intermittent.

## Reproduction

`make_repro_pdf.py` builds a self-contained PDF with **entirely fictional data**. The page is a dense, multi-paragraph document; two of its body lines are drawn as vector glyph outlines rather than text.

```bash
uv run make_repro_pdf.py          # writes pdf/synthetic_missing_text_repro.pdf
uv run main.py                    # runs LiteParse over everything in pdf/
```

### Observed behaviour on the repro PDF


| Check                                                    | Result                                           |
| -------------------------------------------------------- | ------------------------------------------------ |
| Page renders all text (including the two outlined lines) | yes — see `pdf/synthetic_missing_text_repro.png` |
| `text_coverage`                                          | `0.245` (≥ `0.15`)                               |
| embedded images / garbled text                           | none                                             |
| LiteParse OCR decision (`RUST_LOG=debug`)                | `ocr render: 0 pages` — OCR skipped              |
| The two outlined lines in LiteParse output               | **missing**                                      |
| Same lines via `pdftotext` / PyMuPDF search              | **also missing**                                 |


The two dropped lines are:

- `…and confirm that Vendor data is`
- `approved subcontractors will have an obligation to meet certain diversity sourcing`

Both are clearly legible in the rendered page but never appear in extracted text.

## Root cause summary

LiteParse's coverage/length heuristic skips OCR on text-dense pages. On such pages, any text flattened to vector outlines (no character codes) is dropped silently — there is no signal to the caller that part of the page was unreadable.

## Layout

```
make_repro_pdf.py       # generates the synthetic repro PDF (fictional data)
main.py                 # runs LiteParse over pdf/, draws bounding boxes to out/
pdf/                    # input PDFs
out/<doc>/results/      # per-page text, bounding-box JSON, and annotated PNG
.references/liteparse/  # LiteParse source, for tracing the OCR decision
```


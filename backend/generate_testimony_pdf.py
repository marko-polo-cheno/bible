import io
import json
import random
from pathlib import Path

import fitz
from PIL import Image, ImageFilter
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, PageBreak, Image as RLImage
from reportlab.lib.enums import TA_LEFT

JSONL_PATH = Path(__file__).parent / "testimonies.jsonl"
OUTPUT_PATH = Path.home() / "Downloads" / "testimonies_chinese.pdf"
NOISE_SIZE = 800
NUM_RECORDS = 400
TARGET_SIZE_MB = 45


def is_chinese(text: str) -> bool:
    return any("\u4e00" <= c <= "\u9fff" for c in text)


def load_chinese_testimonies() -> list[dict]:
    entries = []
    with open(JSONL_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                d = json.loads(line)
                if is_chinese(d.get("content", "") or ""):
                    entries.append(d)
            except json.JSONDecodeError:
                pass
    return entries[-NUM_RECORDS:]


def create_noise_image(path: Path, size: int | None = None, use_jpeg: bool = False) -> Path:
    size = size or NOISE_SIZE
    img = Image.new("RGB", (size, size))
    pixels = img.load()
    for i in range(size):
        for j in range(size):
            pixels[i, j] = (
                random.randint(0, 255),
                random.randint(0, 255),
                random.randint(0, 255),
            )
    if use_jpeg:
        img.save(path, "JPEG", quality=85)
    else:
        img.save(path)
    return path


def apply_scan_effect(pil_img: Image.Image) -> Image.Image:
    img = pil_img.convert("L")
    img = img.point(lambda x: min(255, int(x * 0.95) + random.randint(0, 12)), mode="L")
    img = img.convert("RGB")
    for _ in range(3):
        img = img.filter(ImageFilter.GaussianBlur(radius=0.3))
    return img


def add_anticompress_bloat(pdf_path: Path, compact: bool = False) -> None:
    doc = fitz.open(pdf_path)
    rng = random.Random(42)

    meta_size = 30_000 if compact else 500_000
    doc.set_metadata({"keywords": "".join(chr(rng.randint(32, 126)) for _ in range(meta_size))})

    tree_depth = 4
    branch_factor = 5
    node_names = []
    stack = ["root"]
    for _ in range(tree_depth):
        next_stack = []
        for parent in stack:
            for k in range(branch_factor):
                name = f"{parent}_c{k}"
                node_names.append(name)
                next_stack.append(name)
        stack = next_stack

    node_size = 5_000 if compact else 100_000
    for name in node_names:
        doc.embfile_add(name, bytes(rng.randint(0, 255) for _ in range(node_size)), filename=name)

    manifest_size = 10_000 if compact else 200_000
    manifest = "\n".join(node_names) + "\n" + "".join(chr(rng.randint(0, 255)) for _ in range(manifest_size))
    doc.embfile_add("tree_manifest", manifest.encode("utf-8", errors="replace"), filename="tree_manifest")

    blob_size = 50_000 if compact else 1_000_000
    for _ in range(3):
        doc.embfile_add(
            f"blob_{_}",
            bytes(rng.randint(0, 255) for _ in range(blob_size)),
            filename=f"blob_{_}.bin",
        )

    hidden_img_size = 40 if compact else 80
    hidden_pil = Image.new("RGB", (hidden_img_size, hidden_img_size))
    px = hidden_pil.load()
    for i in range(hidden_img_size):
        for j in range(hidden_img_size):
            px[i, j] = (rng.randint(0, 255), rng.randint(0, 255), rng.randint(0, 255))
    hidden_buf = io.BytesIO()
    hidden_pil.save(hidden_buf, format="PNG")
    hidden_stream = hidden_buf.getvalue()
    for page in doc:
        rect = fitz.Rect(0, 0, 1, 1)
        try:
            page.insert_image(rect, stream=hidden_stream, alpha=0)
        except Exception:
            pass

    temp_path = pdf_path.with_suffix(".tmp.pdf")
    doc.save(temp_path, garbage=4, deflate=compact, use_objstms=False)
    doc.close()
    temp_path.replace(pdf_path)


def rasterize_and_replace_pages(
    pdf_path: Path,
    content_page_indices: list[int],
    scan_fraction: float = 1 / 3,
    scan_scale: float = 2.0,
    use_jpeg: bool = False,
):
    doc = fitz.open(pdf_path)
    to_scan = set(random.sample(content_page_indices, int(len(content_page_indices) * scan_fraction)))
    new_doc = fitz.open()

    for page_num in range(len(doc)):
        if page_num in to_scan:
            page = doc[page_num]
            mat = fitz.Matrix(scan_scale, scan_scale)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img_data = pix.tobytes("png")
            pil_img = Image.open(io.BytesIO(img_data)).convert("RGB")
            scanned = apply_scan_effect(pil_img)
            buf = io.BytesIO()
            if use_jpeg:
                scanned.save(buf, format="JPEG", quality=85)
            else:
                scanned.save(buf, format="PNG")
            buf.seek(0)
            new_page = new_doc.new_page(width=page.rect.width, height=page.rect.height)
            new_page.insert_image(new_page.rect, stream=buf.read())
        else:
            new_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)

    doc.close()
    temp_path = pdf_path.with_suffix(".tmp.pdf")
    new_doc.save(temp_path, garbage=4, deflate=True)
    new_doc.close()
    temp_path.replace(pdf_path)


def register_chinese_font():
    font_paths = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Supplemental/Songti.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
    ]
    for fp in font_paths:
        if Path(fp).exists():
            try:
                pdfmetrics.registerFont(TTFont("ChineseFont", fp))
                return "ChineseFont"
            except Exception:
                continue
    return "Helvetica"


def main():
    entries = load_chinese_testimonies()
    font_name = register_chinese_font()

    styles = getSampleStyleSheet()
    body_style = ParagraphStyle(
        name="ChineseBody",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=8,
        leading=11,
        alignment=TA_LEFT,
    )

    insertion_points = []
    idx = 0
    while idx < NUM_RECORDS:
        step = random.choice([9, 10, 11])
        idx += step
        if idx <= NUM_RECORDS:
            insertion_points.append(idx)

    content_pages = list(range(NUM_RECORDS))
    for pos in reversed(insertion_points):
        content_pages.insert(pos, None)

    doc = SimpleDocTemplate(
        str(OUTPUT_PATH),
        pagesize=A4,
        rightMargin=inch,
        leftMargin=inch,
        topMargin=inch,
        bottomMargin=inch,
    )
    story = []

    compact = TARGET_SIZE_MB is not None
    noise_size = NOISE_SIZE // 2 if compact else NOISE_SIZE
    temp_noise = Path(__file__).parent / "_noise_temp.png"
    create_noise_image(temp_noise, size=noise_size)
    display_size = min(400, noise_size)
    noise_img = RLImage(str(temp_noise), width=display_size, height=display_size)

    for i, page_spec in enumerate(content_pages):
        if page_spec is None:
            story.append(PageBreak())
            story.append(noise_img)
            story.append(PageBreak())
        else:
            entry = entries[page_spec]
            content = (entry.get("content") or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            content = content.replace("\n", "<br/>")
            p = Paragraph(content, body_style)
            story.append(p)
            story.append(PageBreak())

    doc.build(story)
    temp_noise.unlink(missing_ok=True)

    content_page_indices = [i for i in range(len(content_pages)) if content_pages[i] is not None]
    rasterize_and_replace_pages(
        OUTPUT_PATH,
        content_page_indices,
        scan_fraction=1 / 3,
        scan_scale=1.6 if compact else 2.0,
        use_jpeg=False,
    )
    add_anticompress_bloat(OUTPUT_PATH, compact=compact)
    print(f"Saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

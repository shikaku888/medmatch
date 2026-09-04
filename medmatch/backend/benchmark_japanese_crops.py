"""Benchmark overlapping vertical crops for Japanese product-label OCR."""
from __future__ import annotations

import argparse
import asyncio
import base64
import io
import json
import re
import statistics
import time
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from .scanner.parsing import ocr_image_to_text

DEFAULT_DIR = Path(__file__).parent / "data" / "japanese_ocr_benchmark"
CROP_RANGES = ((0.0, 0.55), (0.25, 0.8), (0.5, 1.0))


def preprocess_crop(image: Image.Image) -> bytes:
    gray = ImageOps.grayscale(image)
    scaled = gray.resize((gray.width * 2, gray.height * 2), Image.Resampling.LANCZOS)
    enhanced = ImageOps.autocontrast(scaled, cutoff=1)
    enhanced = ImageEnhance.Contrast(enhanced).enhance(1.25).filter(
        ImageFilter.UnsharpMask(radius=1.2, percent=120, threshold=3)
    )
    output = io.BytesIO()
    enhanced.save(output, format="JPEG", quality=95, optimize=True)
    return output.getvalue()


def merge_texts(texts: list[str]) -> str:
    lines = []
    seen = set()
    for text in texts:
        for line in text.splitlines():
            line = re.sub(r"\s+", " ", line).strip()
            if line and line not in seen:
                seen.add(line)
                lines.append(line)
    return "\n".join(lines)


async def benchmark(manifest_path: Path, output_path: Path) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    items = [item for item in manifest["items"] if item["filename"].startswith("user_supplied/")]
    rows = []
    for item in items:
        image_path = manifest_path.parent / item["filename"]
        started = time.perf_counter()
        texts = []
        error = None
        try:
            with Image.open(image_path) as image:
                width, height = image.size
                for top, bottom in CROP_RANGES:
                    crop = image.crop((0, int(height * top), width, int(height * bottom)))
                    encoded = base64.b64encode(preprocess_crop(crop)).decode("ascii")
                    texts.append(await ocr_image_to_text(encoded, "image/jpeg"))
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        text = merge_texts(texts)
        rows.append({
            **item,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
            "ocr_text": text,
            "ocr_chars": len(text),
            "japanese_chars": len(re.findall(r"[\u3040-\u30ff\u3400-\u9fff]", text)),
            "has_text": bool(text),
            "error": error,
        })

    summary = {
        "engine": "rapidocr_onnxruntime",
        "preprocess": "three overlapping vertical crops, grayscale, 2x upscale, contrast, sharpen",
        "dataset_size": len(rows),
        "successful_runs": sum(not row["error"] for row in rows),
        "nonempty_outputs": sum(row["has_text"] for row in rows),
        "japanese_text_outputs": sum(row["japanese_chars"] > 0 for row in rows),
        "mean_elapsed_ms": round(statistics.mean(row["elapsed_ms"] for row in rows), 1) if rows else 0,
        "median_elapsed_ms": round(statistics.median(row["elapsed_ms"] for row in rows), 1) if rows else 0,
        "total_ocr_chars": sum(row["ocr_chars"] for row in rows),
        "note": "Screening only; exact accuracy requires ground-truth transcription.",
    }
    output_path.write_text(json.dumps({"summary": summary, "items": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_DIR / "manifest.json")
    parser.add_argument("--output", type=Path, default=DEFAULT_DIR / "benchmark_crops.json")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(benchmark(args.input, args.output)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

"""Benchmark RapidOCR on the curated Japanese-label image manifest."""
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


def preprocess_image(image_path: Path) -> bytes:
    with Image.open(image_path) as image:
        gray = ImageOps.grayscale(image)
        upscaled = gray.resize((gray.width * 2, gray.height * 2), Image.Resampling.LANCZOS)
        contrast = ImageOps.autocontrast(upscaled, cutoff=1)
        sharpened = ImageEnhance.Contrast(contrast).enhance(1.25).filter(
            ImageFilter.UnsharpMask(radius=1.2, percent=120, threshold=3)
        )
        output = io.BytesIO()
        sharpened.save(output, format="JPEG", quality=95, optimize=True)
        return output.getvalue()


async def benchmark(manifest_path: Path, output_path: Path, preprocess: bool = False) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows = []
    for item in manifest["items"]:
        image_path = manifest_path.parent / item["filename"]
        started = time.perf_counter()
        text = ""
        error = None
        try:
            image_bytes = preprocess_image(image_path) if preprocess else image_path.read_bytes()
            encoded = base64.b64encode(image_bytes).decode("ascii")
            text = await ocr_image_to_text(encoded, "image/jpeg")
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
        rows.append({
            **item,
            "elapsed_ms": elapsed_ms,
            "ocr_text": text,
            "ocr_chars": len(text),
            "japanese_chars": len(re.findall(r"[\u3040-\u30ff\u3400-\u9fff]", text)),
            "has_text": bool(text.strip()),
            "error": error,
        })

    summary = {
        "engine": "rapidocr_onnxruntime",
        "preprocess": preprocess,
        "dataset_size": len(rows),
        "successful_runs": sum(not row["error"] for row in rows),
        "nonempty_outputs": sum(row["has_text"] for row in rows),
        "japanese_text_outputs": sum(row["japanese_chars"] > 0 for row in rows),
        "mean_elapsed_ms": round(statistics.mean(row["elapsed_ms"] for row in rows), 1) if rows else 0,
        "median_elapsed_ms": round(statistics.median(row["elapsed_ms"] for row in rows), 1) if rows else 0,
        "min_elapsed_ms": min((row["elapsed_ms"] for row in rows), default=0),
        "max_elapsed_ms": max((row["elapsed_ms"] for row in rows), default=0),
        "total_ocr_chars": sum(row["ocr_chars"] for row in rows),
        "note": "No ground-truth transcriptions yet; Japanese character presence and runtime are screening metrics, not accuracy.",
    }
    output_path.write_text(json.dumps({
        "engine": "rapidocr_onnxruntime",
        "preprocess": preprocess,
        "dataset_manifest": manifest_path.name,
        "summary": summary,
        "items": rows,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_DIR / "manifest.json")
    parser.add_argument("--output", type=Path, default=DEFAULT_DIR / "benchmark_results.json")
    parser.add_argument("--preprocess", action="store_true")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(benchmark(args.input, args.output, args.preprocess)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

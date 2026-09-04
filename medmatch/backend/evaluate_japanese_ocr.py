"""Evaluate Japanese OCR against manually reviewed visible key terms."""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

from .scanner.parsing import normalize_ocr_text

DEFAULT_DIR = Path(__file__).parent / "data" / "japanese_ocr_benchmark"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate(ground_truth: dict, benchmark: dict) -> dict:
    benchmark_by_filename = {item["filename"]: item for item in benchmark["items"]}
    rows: list[dict] = []
    terms_total = 0
    terms_found = 0

    for annotation in ground_truth["items"]:
        filename = annotation["filename"]
        result = benchmark_by_filename.get(filename, {})
        raw_terms = annotation.get("verified_key_terms") or []
        normalized_text = normalize_ocr_text(result.get("ocr_text", ""))
        normalized_terms = [(term, normalize_ocr_text(term)) for term in raw_terms]
        found = [term for term, normalized_term in normalized_terms if normalized_term and normalized_term in normalized_text]
        missing = [term for term, normalized_term in normalized_terms if not normalized_term or normalized_term not in normalized_text]
        row_terms_total = len(raw_terms)
        row_terms_found = len(found)
        terms_total += row_terms_total
        terms_found += row_terms_found
        rows.append(
            {
                "id": annotation["id"],
                "filename": filename,
                "priority": annotation.get("priority"),
                "terms_total": row_terms_total,
                "terms_found": row_terms_found,
                "recall": round(row_terms_found / row_terms_total, 3) if row_terms_total else None,
                "found": found,
                "missing": missing,
                "ocr_japanese_chars": result.get("japanese_chars", 0),
                "ocr_nonempty": result.get("has_text", False),
                "elapsed_ms": result.get("elapsed_ms"),
                "ocr_error": result.get("error"),
            }
        )

    benchmark_summary = benchmark.get("summary", {})
    elapsed_values = [row["elapsed_ms"] for row in rows if isinstance(row.get("elapsed_ms"), (int, float))]
    summary = {
        "images": len(rows),
        "images_with_terms": sum(bool(annotation.get("verified_key_terms")) for annotation in ground_truth["items"]),
        "terms_total": terms_total,
        "terms_found": terms_found,
        "micro_recall": round(terms_found / terms_total, 3) if terms_total else 0,
        "successful_runs": sum(not row["ocr_error"] for row in rows),
        "nonempty_outputs": sum(bool(row["ocr_nonempty"]) for row in rows),
        "japanese_text_outputs": sum((row["ocr_japanese_chars"] or 0) > 0 for row in rows),
        "mean_elapsed_ms": round(statistics.mean(elapsed_values), 1) if elapsed_values else 0,
        "median_elapsed_ms": round(statistics.median(elapsed_values), 1) if elapsed_values else 0,
        "benchmark_dataset_size": len(benchmark.get("items", [])),
        "note": "Exact substring screening against manually reviewed visible key terms after conservative Unicode/unit normalization; not full transcription CER/WER or complete ingredient precision/recall.",
    }
    return {
        "engine": benchmark.get("engine", "rapidocr_onnxruntime"),
        "benchmark_summary": benchmark_summary,
        "summary": summary,
        "items": rows,
    }


def compare_fallback(baseline: dict, crop: dict) -> dict:
    baseline_by_filename = {item["filename"]: item for item in baseline["items"]}
    crop_by_filename = {item["filename"]: item for item in crop["items"]}
    paired = [
        (baseline_by_filename[filename], crop_by_filename[filename])
        for filename in baseline_by_filename.keys() & crop_by_filename.keys()
    ]
    positive_pairs = [pair for pair in paired if pair[0]["terms_total"]]
    low_signal_pairs = [pair for pair in paired if pair[0]["ocr_japanese_chars"] <= 1]
    return {
        "candidate_rule": "Run crop only when baseline Japanese-character count <= 1",
        "candidate_images": len(low_signal_pairs),
        "candidate_positive_images": sum(pair[0]["terms_total"] > 0 for pair in low_signal_pairs),
        "positive_images_crop_better": sum(pair[1]["terms_found"] > pair[0]["terms_found"] for pair in positive_pairs),
        "positive_images_equal": sum(pair[1]["terms_found"] == pair[0]["terms_found"] for pair in positive_pairs),
        "positive_images_crop_worse": sum(pair[1]["terms_found"] < pair[0]["terms_found"] for pair in positive_pairs),
        "recommendation": "Do not enable crop fallback yet; the low-signal candidates contain no reviewed positive image, and crop has no key-term gain on the positive set.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ground-truth", type=Path, default=DEFAULT_DIR / "ground_truth_template.json")
    parser.add_argument("--baseline", type=Path, default=DEFAULT_DIR / "benchmark_results.json")
    parser.add_argument("--crop", type=Path, default=DEFAULT_DIR / "benchmark_crops.json")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_DIR)
    args = parser.parse_args()

    ground_truth = _load(args.ground_truth)
    baseline = evaluate(ground_truth, _load(args.baseline))
    crop = evaluate(ground_truth, _load(args.crop))

    args.output_dir.joinpath("key_term_evaluation.json").write_text(
        json.dumps(baseline, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    args.output_dir.joinpath("crop_key_term_evaluation.json").write_text(
        json.dumps(crop, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    fallback = compare_fallback(baseline, crop)
    combined = {
        "dataset": ground_truth.get("dataset"),
        "baseline": baseline["summary"],
        "crop": crop["summary"],
        "fallback_analysis": fallback,
        "decision": {
            "default_pipeline": "baseline",
            "crop_fallback": "not enabled",
            "reason": "Crop OCR raises Japanese-output coverage but lowers exact key-term recall and materially increases latency on this reviewed set.",
        },
    }
    args.output_dir.joinpath("ocr_evaluation_summary.json").write_text(
        json.dumps(combined, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(combined, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

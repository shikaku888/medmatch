from __future__ import annotations

import csv
import io
import sqlite3
import zipfile

from backend.onsides import import_full


def _csv(rows: list[list[str]]) -> str:
    stream = io.StringIO()
    csv.writer(stream).writerows(rows)
    return stream.getvalue()


def test_import_full_retains_raw_provenance_and_ingredient_aggregate(tmp_path) -> None:
    archive = tmp_path / "onsides.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr(
            "csv/product_label.csv",
            _csv([
                ["label_id", "source", "source_product_name", "source_product_id", "source_label_url"],
                ["1", "US", "Aspirin", "A1", "https://example.test/a1"],
                ["2", "EU", "Unknown", "E2", "https://example.test/e2"],
            ]),
        )
        z.writestr(
            "csv/vocab_meddra_adverse_effect.csv",
            _csv([["meddra_id", "meddra_name", "meddra_term_type"], ["1001", "Headache", "PT"]]),
        )
        z.writestr(
            "csv/high_confidence.csv",
            _csv([["ingredient_id", "effect_meddra_id"], ["1202", "1001"]]),
        )
        z.writestr(
            "csv/product_to_rxnorm.csv",
            _csv([["label_id", "rxnorm_product_id"], ["1", "403840"]]),
        )
        z.writestr(
            "csv/vocab_rxnorm_ingredient_to_product.csv",
            _csv([["product_id", "ingredient_id"], ["403840", "1202"]]),
        )
        z.writestr(
            "csv/vocab_rxnorm_ingredient.csv",
            _csv([["rxnorm_id", "rxnorm_name", "rxnorm_term_type"], ["1202", "aspirin", "Ingredient"]]),
        )
        z.writestr(
            "csv/product_adverse_effect.csv",
            _csv([
                ["product_label_id", "effect_id", "label_section", "effect_meddra_id", "match_method", "pred0", "pred1"],
                ["1", "e1", "WARNINGS", "1001", "PMB", "0.8", "0.9"],
                ["2", "e2", "WARNINGS", "1001", "PMB", "0.7", "0.8"],
            ]),
        )

    conn = sqlite3.connect(":memory:")
    result = import_full(conn, archive)

    assert result["rows"] == 2
    assert result["raw_rows"] == 2
    assert result["mapped_rows"] == 1
    assert result["ingredient_effects"] == 1
    row = conn.execute("SELECT * FROM onsides_ingredient_effects").fetchone()
    assert row[0:5] == ("1202", "aspirin", "1001", "Headache", "US")
    assert row[9] == 1
    assert conn.execute("SELECT source_label_url FROM onsides_effects_raw").fetchone()[0].startswith("https://")
    conn.close()

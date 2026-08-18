"""Tests de l'utilitaire d'écriture en masse (découpage sous la limite de paramètres PG)."""
from __future__ import annotations

from backend.app.core.bulk import chunked, safe_chunk_size


def test_chunked_splits_evenly():
    assert [list(c) for c in chunked([1, 2, 3, 4, 5], 2)] == [[1, 2], [3, 4], [5]]
    assert list(chunked([], 3)) == []


def test_safe_chunk_size_stays_under_pg_limit():
    # Sous la limite dure de 65535 paramètres, quel que soit le nombre de colonnes.
    for n_cols in (2, 3, 18, 40):
        assert safe_chunk_size(n_cols) * n_cols <= 65535
        assert safe_chunk_size(n_cols) >= 1

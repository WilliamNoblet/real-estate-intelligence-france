"""Utilitaires d'écriture en masse.

PostgreSQL limite un message Bind à 65535 paramètres liés. Un `INSERT ... VALUES` unique
avec des dizaines de milliers de lignes dépasse cette borne → on découpe en lots."""
from __future__ import annotations

from collections.abc import Iterator, Sequence

# Marge de sécurité sous 65535 paramètres.
_MAX_PARAMS = 60000


def chunked[T](rows: Sequence[T], size: int) -> Iterator[Sequence[T]]:
    for i in range(0, len(rows), size):
        yield rows[i : i + size]


def safe_chunk_size(n_columns: int) -> int:
    """Taille de lot maximale (nombre de lignes) pour rester sous la limite de paramètres."""
    return max(1, _MAX_PARAMS // max(1, n_columns))

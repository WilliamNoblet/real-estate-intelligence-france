"""Téléchargement des fichiers geo-dvf + empreinte SHA256 (idempotence, §23).
Le fichier brut est conservé tel quel dans data/raw/dvf/ (immuable, §24)."""
from __future__ import annotations

import hashlib
from pathlib import Path

import httpx

from backend.app.core.config import ROOT_DIR, settings
from pipelines.dvf.source import EXCLUDED_DEPARTMENTS, department_csv_url

RAW_DIR = ROOT_DIR / "data" / "raw" / "dvf"


def download_department(dep: str, year: int, dest_dir: Path | None = None) -> tuple[Path, str]:
    """Télécharge le fichier départemental d'une année, renvoie (chemin, sha256).
    Le user-agent est honnête et identifiable (§32)."""
    if dep in EXCLUDED_DEPARTMENTS:
        raise ValueError(f"Département {dep} hors périmètre DVF (Alsace-Moselle / Mayotte).")

    url = department_csv_url(dep, year)
    target_dir = (dest_dir or RAW_DIR) / str(year)
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"{dep}.csv.gz"

    sha = hashlib.sha256()
    headers = {"User-Agent": settings.user_agent}
    with httpx.stream("GET", url, timeout=180.0, follow_redirects=True, headers=headers) as resp:
        resp.raise_for_status()
        with path.open("wb") as fh:
            for chunk in resp.iter_bytes(chunk_size=1 << 16):
                fh.write(chunk)
                sha.update(chunk)
    return path, sha.hexdigest()


def sha256_of_file(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            sha.update(chunk)
    return sha.hexdigest()

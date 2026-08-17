"""Dashboard d'amorçage (Phase 1). Les pages métier — Marché, Annonces, Détail,
Comparables, Carte (§98-104) — arrivent en Phase 8. Ici : vérifier que la stack répond,
et poser d'emblée la distinction fondamentale prix demandé / prix de transaction (§3)."""
from __future__ import annotations

import os

import httpx
import streamlit as st

API_URL = os.environ.get("API_URL", "http://localhost:8000")

st.set_page_config(page_title="Observatoire immobilier FR", page_icon="🏘️", layout="wide")

st.title("🏘️ Observatoire du marché immobilier français")
st.caption("Local-first · open data · collecte responsable")

st.info(
    "**Règle fondamentale.** Ce système distingue toujours deux notions :\n\n"
    "- 🟠 **Prix demandé** — ce que le vendeur affiche dans une annonce.\n"
    "- 🟢 **Prix de transaction (DVF)** — ce qui a réellement été payé.\n\n"
    "Elles ne sont jamais mélangées.",
    icon="⚖️",
)

st.subheader("État de la stack")
try:
    resp = httpx.get(f"{API_URL}/health", timeout=5.0)
    data = resp.json()
    col1, col2, col3 = st.columns(3)
    col1.metric("API", data.get("status", "?"))
    col2.metric("Base de données", "OK" if data.get("database") else "KO")
    col3.metric("PostGIS", data.get("postgis") or "absent")
except Exception as exc:  # noqa: BLE001
    st.error(f"API injoignable sur {API_URL} : {exc}")

st.divider()
st.caption(
    "Phase 1 terminée : schéma PostGIS + API de santé. Prochaines phases : import DVF (Gironde), "
    "géo/carte, premier connecteur d'annonces (Immonot), snapshots & événements de prix."
)

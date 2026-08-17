"""Dashboard d'amorçage. Phase 1 : santé. Phase 3 : carte des transactions DVF par commune.
Les pages métier complètes (Marché, Annonces, Détail, Comparables — §98-104) arrivent en Phase 8.
Distinction fondamentale prix demandé / prix de transaction posée d'emblée (§3)."""
from __future__ import annotations

import os

import httpx
import pydeck as pdk
import streamlit as st

API_URL = os.environ.get("API_URL", "http://localhost:8000")

st.set_page_config(page_title="Observatoire immobilier FR", page_icon="🏘️", layout="wide")
st.title("🏘️ Observatoire du marché immobilier français")
st.caption("Local-first · open data · collecte responsable")

st.info(
    "**Règle fondamentale.** 🟠 **Prix demandé** (annonce) ≠ "
    "🟢 **Prix de transaction** (DVF, réellement payé). "
    "Ces deux notions ne sont jamais mélangées.",
    icon="⚖️",
)


def api_get(path: str, params: dict | None = None) -> dict | None:
    try:
        resp = httpx.get(f"{API_URL}{path}", params=params, timeout=10.0)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:  # noqa: BLE001
        st.error(f"API {path} : {exc}")
        return None


# --- État de la stack ---
with st.expander("État de la stack", expanded=False):
    health = api_get("/health")
    if health:
        c1, c2, c3 = st.columns(3)
        c1.metric("API", health.get("status", "?"))
        c2.metric("Base de données", "OK" if health.get("database") else "KO")
        c3.metric("PostGIS", health.get("postgis") or "absent")

st.divider()

# --- Carte des transactions DVF (prix payés) ---
st.subheader("🟢 Transactions DVF sur une carte")
col_a, col_b, col_c = st.columns([2, 2, 1])
insee = col_a.text_input("Code INSEE commune", value="33063", help="Ex. 33063 = Bordeaux")
ptype = col_b.selectbox("Type de bien", ["(tous)", "HOUSE", "APARTMENT", "LAND", "OTHER"], index=1)
limit = col_c.number_input("Max points", min_value=50, max_value=1000, value=300, step=50)

params = {"insee_code": insee, "limit": int(limit)}
if ptype != "(tous)":
    params["property_type"] = ptype

market_params = {"property_type": ptype} if ptype != "(tous)" else None
data = api_get("/transactions", params) if insee else None
market = api_get(f"/markets/{insee}", market_params) if insee else None

if market:
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Transactions (échantillon)", market.get("sample_size", 0))
    med = market.get("median_price_per_m2")
    m2.metric("Médiane €/m² (payé)", f"{med:,.0f}".replace(",", " ") if med else "—")
    m3.metric("Q1 €/m²", f"{market.get('q1_price_per_m2') or 0:,.0f}".replace(",", " "))
    m4.metric("Q3 €/m²", f"{market.get('q3_price_per_m2') or 0:,.0f}".replace(",", " "))
    if market.get("insufficient_sample"):
        st.warning(
            f"Échantillon insuffisant (< {market.get('min_sample')}) — "
            "médiane peu significative (§159)."
        )

if data and data.get("items"):
    points = [
        {
            "lon": it["longitude"],
            "lat": it["latitude"],
            "price": it.get("sale_price"),
            "ppm2": it.get("price_per_m2"),
        }
        for it in data["items"]
        if it.get("latitude") is not None and it.get("longitude") is not None
    ]
    if points:
        clat = sum(p["lat"] for p in points) / len(points)
        clon = sum(p["lon"] for p in points) / len(points)
        layer = pdk.Layer(
            "ScatterplotLayer",
            data=points,
            get_position="[lon, lat]",
            get_radius=35,
            get_fill_color=[16, 110, 92, 170],
            pickable=True,
        )
        st.pydeck_chart(
            pdk.Deck(
                layers=[layer],
                initial_view_state=pdk.ViewState(latitude=clat, longitude=clon, zoom=12),
                tooltip={"text": "{price} € — {ppm2} €/m²"},
                map_style=None,
            )
        )
        st.caption(f"{len(points)} transactions géolocalisées — prix **payés** (DVF).")
    else:
        st.info("Aucune transaction géolocalisée — lance `make geo-load` pour peupler `location`.")
elif insee:
    st.info("Aucune transaction pour cette commune. As-tu lancé `make dvf-import DEP=…` ?")

st.divider()
st.caption(
    "Phases livrées : 0-1 (socle), 2 (import DVF), 3 (géo/carte). "
    "Prochaines : connecteur d'annonces (Immonot), snapshots & historique de prix."
)

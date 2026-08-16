"""Outil « position » : géolocalisation (IP) + position curseur/fenêtre rapportées
par le frontend Electron (stockées dans _state via /position/update)."""
import httpx
from . import tool

GEO_API = "https://ipapi.co/json/"
GEO_FALLBACKS = ["https://ipinfo.io/json", "https://ipwho.is/"]
GEO_TIMEOUT = 8

# État remonté par le frontend Electron (curseur + fenêtre)
_state: dict = {"cursor": None, "window": None, "ts": 0.0}

def update_from_frontend(cursor=None, window=None):
    import time
    _state["cursor"] = cursor
    _state["window"] = window
    _state["ts"] = time.time()

def _fmt_geo() -> str:
    urls = [GEO_API, *GEO_FALLBACKS]
    for url in urls:
        try:
            r = httpx.get(url, timeout=GEO_TIMEOUT, headers={"User-Agent": "alex-assistant/1.0"})
            r.raise_for_status()
            d = r.json()
            ip = d.get("ip") or d.get("query")
            if not ip:
                continue
            if "city" in d:  # ipinfo.io
                parts = [d.get("city"), d.get("region"), d.get("country")]
                place = ", ".join(p for p in parts if p)
            else:  # ipwho.is
                parts = [d.get("city"), d.get("region"), d.get("country")]
                place = ", ".join(p for p in parts if p)
            lat = d.get("latitude") or d.get("loc", "").split(",")[0]
            lon = d.get("longitude") or (d.get("loc", "").split(",")[1] if "," in d.get("loc", "") else None)
            return f"{place} (lat {lat}, lon {lon})" if place else f"{ip}"
        except Exception as e:
            last_err = e
            continue
    return f"Localisation indisponible (offline ?) : {last_err}"

@tool("position", "Donne la position actuelle : géolocalisation (ville/pays), position du curseur et de la fenêtre d'Alex. Paramètre : domaine (all/geo/cursor/window).")
def get_position(domaine: str = "all") -> str:
    """Donne la position actuelle (géolocalisation, curseur, fenêtre).

    Args:
        domaine: Quelle position renvoyer (all, geo, cursor, window).
    """
    geo = _fmt_geo() if domaine in ("all", "geo") else None
    cursor = _state.get("cursor")
    window = _state.get("window")
    parts = []
    if geo is not None:
        parts.append(f"📍 Géolocalisation : {geo}")
    if domaine in ("all", "cursor"):
        if cursor:
            cursor_text = (f"{cursor['x']}, {cursor['y']} px"
                           f" (écran {cursor.get('display', '?')})")
            parts.append(f"🖱️ Curseur : {cursor_text}")
        else:
            parts.append("🖱️ Curseur : inconnu (rapport non reçu).")
    if domaine in ("all", "window"):
        if window:
            parts.append(
                f"🪟 Fenêtre Alex : x={window.get('x')}, y={window.get('y')}, "
                f"{window.get('width')}×{window.get('height')}, mode {window.get('mode', '?')}"
            )
        else:
            parts.append("🪟 Fenêtre Alex : inconnue (rapport non reçu).")
    return "\n".join(p for p in parts if p) or "Aucune information de position."
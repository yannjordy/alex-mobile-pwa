"""Outil « carte » : Alex peut repérer des lieux, dessiner des itinéraires
et ajouter des légendes sur le widget carte de l'interface.

Les données sont stockées côté serveur et synchronisées avec le widget
via l'endpoint /map/data (le frontend relit à l'ouverture)."""
import json
import os
import re
from pathlib import Path

from . import tool

ALEX_ROOT = Path(__file__).resolve().parent.parent.parent
MAP_DB = ALEX_ROOT / "data" / "map_data.json"

# Lieux connus (géolocalisés) pour résoudre un nom de ville → coordonnées
CITIES = {
    "douala": (4.0511, 9.7679),
    "yaoundé": (3.8480, 11.5021),
    "yaounde": (3.8480, 11.5021),
    "paris": (48.8566, 2.3522),
    "lyon": (45.7640, 4.8357),
    "marseille": (43.2965, 5.3698),
    "bruxelles": (50.8503, 4.3517),
    "londres": (51.5074, -0.1278),
    "new york": (40.7128, -74.0060),
    "los angeles": (34.0522, -118.2437),
    "tokyo": (35.6762, 139.6503),
    "dakar": (14.7167, -17.4677),
    "abidjan": (5.3600, -4.0083),
    "kinshasa": (-4.4419, 15.2663),
    "genève": (46.2044, 6.1432),
    "geneve": (46.2044, 6.1432),
    "montréal": (45.5017, -73.5673),
    "montreal": (45.5017, -73.5673),
    "cameroun": (7.3697, 12.3547),
    "france": (46.2276, 2.2137),
    "afrique": (8.7832, 17.6150),
}

_mem: dict = {"markers": [], "routes": [], "legends": []}


def _load() -> dict:
    try:
        if MAP_DB.exists():
            return json.loads(MAP_DB.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {"markers": [], "routes": [], "legends": []}


def _save(data: dict) -> None:
    try:
        MAP_DB.parent.mkdir(parents=True, exist_ok=True)
        MAP_DB.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[carte] Échec sauvegarde : {e}")


def _sync(data: dict) -> None:
    _mem.clear()
    _mem.update(data)


def save_data(data: dict) -> None:
    """Sauvegarde des données complètes envoyées par le frontend."""
    data = {
        "markers": data.get("markers") or [],
        "routes": data.get("routes") or [],
        "legends": data.get("legends") or [],
    }
    _save(data)
    _sync(data)


def get_data() -> dict:
    """Données carte actuelles (pour l'endpoint /map/data)."""
    return _load()


def _resolve_coords(loc: str) -> tuple[float, float] | None:
    """Tente de résoudre une localisation en coordonnées.
    Accepte « lat,lng » explicite ou un nom de ville connu."""
    m = re.match(r"^\s*([-+]?\d+\.?\d*)\s*,\s*([-+]?\d+\.?\d*)\s*$", loc)
    if m:
        return (float(m.group(1)), float(m.group(2)))
    key = loc.strip().lower().rstrip(".")
    return CITIES.get(key)


@tool("carte",
      "Manipule le widget carte du monde d'Alex. Action : ajouter_lieu (lieu/label), "
      "itineraire (lieux séparés par ->), legende (label), lister, effacer. "
      "Les lieux peuvent être des noms de villes ou des coordonnées 'lat,lng'.")
def carte(action: str = "lister", lieu: str = "", lieux: str = "", label: str = "") -> str:
    """Ajoute des lieux, itinéraires ou légendes sur la carte.

    Args:
        action: opération (ajouter_lieu, itineraire, legende, lister, effacer).
        lieu: ville ou 'lat,lng' pour un point.
        lieux: points d'un itinéraire séparés par ' -> '.
        label: nom/légende à afficher.
    """
    data = _load()
    _sync(data)
    action = (action or "lister").lower()

    if action == "lister":
        if not data["markers"] and not data["routes"] and not data["legends"]:
            return "🗺️ La carte est vide pour l'instant. Dis-moi d'ajouter un lieu, un itinéraire ou une légende."
        parts = []
        if data["markers"]:
            parts.append("📍 Lieux :\n" + "\n".join(f"  • {m['label']} ({m['lat']:.3f}, {m['lng']:.3f})" for m in data["markers"]))
        if data["routes"]:
            parts.append("🛣️ Itinéraires :\n" + "\n".join(f"  • {r.get('label') or 'Itinéraire'} ({len(r['points'])} points)" for r in data["routes"]))
        if data["legends"]:
            parts.append("🏷️ Légendes :\n" + "\n".join(f"  • {l['label']}" for l in data["legends"]))
        return "🗺️ Contenu de la carte :\n" + "\n\n".join(parts)

    if action == "effacer":
        data = {"markers": [], "routes": [], "legends": []}
        _save(data)
        _sync(data)
        return "🗺️ Carte effacée."

    if action in ("ajouter_lieu", "lieu"):
        if not lieu:
            return "Quel lieu veux-tu repérer ? (ville ou lat,lng)"
        coords = _resolve_coords(lieu)
        if not coords:
            return f"Je ne connais pas « {lieu} ». Donne une ville connue ou des coordonnées lat,lng."
        name = label or lieu.strip().title()
        data["markers"].append({"lat": coords[0], "lng": coords[1], "label": name, "color": "#ff9d3d"})
        _save(data)
        _sync(data)
        return f"📍 {name} ajouté sur la carte ({coords[0]:.4f}, {coords[1]:.4f})."

    if action in ("itineraire", "route"):
        if not lieux:
            return "Donne les lieux de l'itinéraire séparés par ' -> ' (ex : Douala -> Paris -> Dakar)."
        points = []
        for raw in re.split(r"\s*->\s*|,", lieux):
            raw = raw.strip()
            if not raw:
                continue
            coords = _resolve_coords(raw)
            if not coords:
                return f"Lieu inconnu dans l'itinéraire : « {raw} »."
            points.append(coords)
        if len(points) < 2:
            return "Un itinéraire a besoin d'au moins 2 points."
        data["routes"].append({"points": points, "color": "#4aa8ff", "label": label or ""})
        _save(data)
        _sync(data)
        return f"🛣️ Itinéraire ajouté ({len(points)} points) : " + " -> ".join(
            f"({p[0]:.3f}, {p[1]:.3f})" for p in points)

    if action in ("legende", "legend"):
        if not label:
            return "Quelle légende veux-tu ajouter ?"
        # Légende au centre de la vue actuelle (ou Douala par défaut)
        lat, lng = 4.0511, 9.7679
        data["legends"].append({"lat": lat, "lng": lng, "label": label, "color": "#7bd88a"})
        _save(data)
        _sync(data)
        return f"🏷️ Légende « {label} » ajoutée sur la carte."

    return f"Action carte inconnue : {action}. Utilise ajouter_lieu, itineraire, legende, lister ou effacer."

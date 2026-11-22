"""Alentoor : agenda de chaque commune, événements en JSON-LD schema.org (jusqu'à 6 pages de 30)."""
import re

from ..referentiel import CATEGORIES_ALENTOOR, COMMUNES, commune
from .outils import Http, date_heure, est_evenement, evenement, jsonld, nombre

NOM = "alentoor"


def convertir(o: dict) -> dict | None:
    lieu = o.get("location") if isinstance(o.get("location"), dict) else {}
    adr = lieu.get("address") if isinstance(lieu.get("address"), dict) else {}
    c = commune(adr.get("addressLocality"))
    if not c:
        return None
    debut, heure = date_heure(o.get("startDate"))
    fin, _ = date_heure(o.get("endDate"))
    images = o.get("image") or []
    image = images[0] if isinstance(images, list) and images else str(images)
    m = re.search(r"/default/([a-z-]+?)-(?:medium|large|small)", image or "")
    num = re.search(r"(\d+)$", str(o.get("@id") or o.get("url") or ""))
    geo = lieu.get("geo") or {}
    return evenement(
        uid=f"alentoor:{num.group(1) if num else o.get('url')}", source=NOM, titre=o.get("name"), commune=c,
        date_debut=debut, date_fin=fin, heure=heure, lieu=lieu.get("name", ""),
        adresse=adr.get("streetAddress", ""), description=o.get("description", ""), url=o.get("url", ""),
        lat=nombre(geo.get("latitude")), lon=nombre(geo.get("longitude")),
        indice_type=CATEGORIES_ALENTOOR.get(m.group(1)) if m else None,
    )


def collecter(http: Http, connus: set[str], journal: list[str]) -> list[dict]:
    vus: dict[str, dict] = {}
    for c in COMMUNES:
        for page in range(1, 7):
            url = f"https://www.alentoor.fr/{c['slug']}/agenda" + (f"?p={page}" if page > 1 else "")
            try:
                r = http.get(url)
            except Exception as e:  # réseau : on passe à la commune suivante
                journal.append(f"alentoor {c['slug']} : {e}")
                break
            if r.status_code == 404:
                break
            if r.status_code != 200:
                journal.append(f"alentoor {c['slug']} : HTTP {r.status_code}")
                break
            locaux = 0
            for o in filter(est_evenement, jsonld(r.text)):
                ev = convertir(o)
                if ev:
                    vus[ev["uid"]] = ev
                    locaux += ev["insee"] == c["insee"]
            # Page suivante seulement si la page est remplie par la commune elle-même.
            if locaux < 25 or f"p={page + 1}" not in r.text:
                break
    return list(vus.values())

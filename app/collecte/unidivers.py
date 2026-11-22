"""Unidivers : flux RSS des événements par ville, puis fiche de chaque nouvel événement (JSON-LD schema.org)."""
import xml.etree.ElementTree as ET

from ..referentiel import COMMUNES, commune
from .outils import Http, date_heure, est_evenement, evenement, jsonld, nombre

NOM = "unidivers"
MAX_FICHES = 200  # fiches lues par passage (les suivantes au prochain passage)


def convertir(o: dict, url: str) -> dict | None:
    lieu = o.get("location") if isinstance(o.get("location"), dict) else {}
    adr = lieu.get("address") if isinstance(lieu.get("address"), dict) else {}
    c = commune(adr.get("addressLocality"))
    if not c:
        return None
    debut, heure = date_heure(o.get("startDate"))
    fin, _ = date_heure(o.get("endDate"))
    geo = lieu.get("geo") or {}
    offre = o.get("offers") if isinstance(o.get("offers"), dict) else {}
    prix = offre.get("price")
    return evenement(
        uid=f"unidivers:{url}", source=NOM, titre=o.get("name"), commune=c, date_debut=debut, date_fin=fin,
        heure=heure, lieu=lieu.get("name", ""), adresse=adr.get("streetAddress", ""),
        description=o.get("description", ""), url=url, lat=nombre(geo.get("latitude")), lon=nombre(geo.get("longitude")),
        prix="" if prix in (None, "", "0.00") else f"{prix} €",
    )


def collecter(http: Http, connus: set[str], journal: list[str]) -> list[dict]:
    liens: dict[str, None] = {}
    for c in COMMUNES:
        try:
            r = http.get(f"https://unidivers.fr/events/categorie/{c['slug']}/feed/")
            if r.status_code != 200 or b"<rss" not in r.content[:500]:
                continue
            for item in ET.fromstring(r.content).iter("item"):
                lien = (item.findtext("link") or "").strip()
                if lien:
                    liens[lien] = None
        except Exception as e:
            journal.append(f"unidivers {c['slug']} : {e}")
    nouveaux = [l for l in liens if f"unidivers:{l}" not in connus][:MAX_FICHES]
    sortie = []
    for lien in nouveaux:
        try:
            r = http.get(lien)
        except Exception as e:
            journal.append(f"unidivers fiche : {e}")
            continue
        if r.status_code != 200:
            continue
        for o in filter(est_evenement, jsonld(r.text)):
            ev = convertir(o, lien)
            if ev:
                sortie.append(ev)
                break
    return sortie

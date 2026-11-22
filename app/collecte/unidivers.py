"""Unidivers : flux RSS des événements par ville, puis fiche de chaque nouvel événement (JSON-LD schema.org)."""
import html
import xml.etree.ElementTree as ET

from ..referentiel import COMMUNES, commune
from .outils import Http, date_heure, est_evenement, evenement, jsonld, nombre

NOM = "unidivers"
MAX_FICHES = 200  # fiches lues par passage (les suivantes au prochain passage)


PREPOSITIONS = {"de", "du", "des", "à", "a", "au", "aux", "en", "sur", "pour", "et", "le", "la", "les"}


def nettoyer_titre(titre: str, *suffixes: str) -> str:
    """Unidivers ajoute lieu, rue et commune à la fin du titre : on les retire (dans n'importe quel ordre)."""
    t = html.unescape(titre or "").strip()
    change = True
    while change:
        change = False
        for s in sorted({x.strip() for x in suffixes if x and x.strip()}, key=len, reverse=True):
            if len(t) > len(s) + 3 and t.lower().endswith(s.lower()):
                reste = t[: -len(s)].rstrip(" ,-–")
                dernier = reste.split()[-1].lower() if reste.split() else ""
                if dernier in PREPOSITIONS or dernier.endswith(("d'", "d’", "l'", "l’")):
                    continue  # « Marché de Noël de Lanmeur » : la commune fait partie du titre
                t, change = reste, True
    return t


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
        uid=f"unidivers:{url}", source=NOM,
        titre=nettoyer_titre(o.get("name"), adr.get("addressLocality", ""), c["nom"], html.unescape(lieu.get("name", "")),
                             adr.get("streetAddress", "")), commune=c, date_debut=debut, date_fin=fin,
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

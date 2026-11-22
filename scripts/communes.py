"""Régénère data/communes.json : communes de Lannion-Trégor Communauté + Trégor finistérien.

Usage : python3 scripts/communes.py
"""
import json
import pathlib
import re
import unicodedata
import urllib.request

LTC = "200065928"
FINISTERE = ["29133", "29073", "29113", "29188", "29251", "29182", "29067", "29014"]  # Locquirec, Guimaëc, Lanmeur, Plougasnou, Saint-Jean-du-Doigt, Plouégat-Guérand, Guerlesquin, Botsorhel
CHAMPS = "fields=nom,code,codesPostaux,centre"


def lire(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r)


def slug(nom):
    s = unicodedata.normalize("NFKD", nom).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


communes = lire(f"https://geo.api.gouv.fr/epcis/{LTC}/communes?{CHAMPS}")
for code in FINISTERE:
    communes.append(lire(f"https://geo.api.gouv.fr/communes/{code}?{CHAMPS}"))
sortie = [
    {
        "insee": c["code"],
        "nom": c["nom"],
        "slug": slug(c["nom"]),
        "cp": c["codesPostaux"][0],
        "lat": c["centre"]["coordinates"][1],
        "lon": c["centre"]["coordinates"][0],
    }
    for c in sorted(communes, key=lambda c: slug(c["nom"]))
]
chemin = pathlib.Path(__file__).resolve().parent.parent / "data" / "communes.json"
chemin.write_text(json.dumps(sortie, ensure_ascii=False, indent=1) + "\n")
print(len(sortie), "communes ->", chemin)

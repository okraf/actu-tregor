"""Crée la base NocoDB TREGOR et ses tables (une seule fois). Idempotent : ne recrée pas ce qui existe.

Usage : NOCODB_URL=https://nocodb.example.org NOCODB_TOKEN=... python3 scripts/nocodb_init.py
Affiche les id des tables à reporter dans config.toml.
"""
import json
import os
import urllib.request

URL = os.environ["NOCODB_URL"].rstrip("/")
TOKEN = os.environ["NOCODB_TOKEN"]
BASE = "TREGOR"

TYPES = ["Concert", "Spectacle", "Fest-noz et culture bretonne", "Exposition", "Festival", "Cinéma",
         "Conférence et rencontre", "Atelier et stage", "Enfants", "Sport", "Nature et balade",
         "Marché et brocante", "Foire et salon", "Fête et animation", "Visite et patrimoine", "Autre"]
SOURCES = ["alentoor", "openagenda", "unidivers", "actu.fr"]


def appel(methode, chemin, corps=None):
    req = urllib.request.Request(URL + chemin, method=methode, headers={"xc-token": TOKEN, "Content-Type": "application/json"},
                                 data=json.dumps(corps).encode() if corps is not None else None)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def options(valeurs):
    return {"options": [{"title": v} for v in valeurs]}


def texte(nom):
    return {"column_name": nom, "title": nom, "uidt": "SingleLineText"}


def col(nom, uidt, **extra):
    return {"column_name": nom, "title": nom, "uidt": uidt, **extra}


TABLES = {
    "evenements": [
        col("id", "ID"), texte("titre"), texte("uid"), col("type", "SingleSelect", colOptions=options(TYPES)),
        col("date_debut", "Date", meta={"date_format": "YYYY-MM-DD"}), col("date_fin", "Date", meta={"date_format": "YYYY-MM-DD"}),
        texte("heure"), texte("ville"), texte("insee"), texte("lieu"), texte("adresse"), col("lat", "Decimal"), col("lon", "Decimal"),
        col("description", "LongText"), col("url", "URL"), col("source", "SingleSelect", colOptions=options(SOURCES)),
        texte("prix"), texte("cle_doublon"), col("vu_le", "DateTime"), col("masque", "Checkbox"),
    ],
    "articles": [
        col("id", "ID"), texte("titre"), col("url", "URL"), col("publie_le", "DateTime"), texte("ville"), texte("categories"),
        col("statut", "SingleSelect", colOptions=options(["evenement", "autre", "a_analyser", "erreur"])),
        texte("evenement_uid"), col("description", "LongText"), col("analyse", "LongText"),
    ],
    "collectes": [
        col("id", "ID"), col("debut", "DateTime"), col("duree_s", "Number"), texte("source"),
        col("lus", "Number"), col("nouveaux", "Number"), col("mis_a_jour", "Number"), col("erreurs", "LongText"),
    ],
}

bases = {b["title"]: b["id"] for b in appel("GET", "/api/v2/meta/bases")["list"]}
base_id = bases.get(BASE) or appel("POST", "/api/v2/meta/bases", {"title": BASE})["id"]
print("base", BASE, base_id)
existantes = {t["title"]: t["id"] for t in appel("GET", f"/api/v2/meta/bases/{base_id}/tables")["list"]}
for nom, colonnes in TABLES.items():
    tid = existantes.get(nom) or appel("POST", f"/api/v2/meta/bases/{base_id}/tables", {"table_name": nom, "title": nom, "columns": colonnes})["id"]
    print(f"table_{nom} = \"{tid}\"")

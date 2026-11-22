"""Communes du Trégor et types d'événements : correspondance des noms, classement par mots-clés."""
import json
import re
import unicodedata
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"


def slug(texte: str) -> str:
    s = unicodedata.normalize("NFKD", texte or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


COMMUNES: list[dict] = json.loads((DATA / "communes.json").read_text())
PAR_SLUG = {c["slug"]: c for c in COMMUNES}
PAR_INSEE = {c["insee"]: c for c in COMMUNES}

# Communes déléguées, quartiers et lieux-dits souvent donnés comme « ville » par les sources.
ALIAS = {
    "la-roche-derrien": "la-roche-jaudy", "pommerit-jaudy": "la-roche-jaudy", "hengoat": "la-roche-jaudy",
    "pouldouran": "la-roche-jaudy", "locquemeau": "tredrez-locquemeau", "tredrez": "tredrez-locquemeau",
    "ploumanac-h": "perros-guirec", "ploumanach": "perros-guirec", "lanvezeac": "caouennec-lanvezeac",
    "caouennec": "caouennec-lanvezeac", "beg-leguer": "lannion", "servel": "lannion", "buhulien": "lannion",
    "brelevenez": "lannion", "loguivy-les-lannion": "lannion", "le-yaudet": "ploulec-h", "ploulech": "ploulec-h",
    "port-blanc": "penvenan", "landrellec": "pleumeur-bodou", "ile-grande": "pleumeur-bodou",
    "l-ile-grande": "pleumeur-bodou", "toul-an-hery": "plestin-les-greves", "plestin": "plestin-les-greves",
    "saint-efflam": "plestin-les-greves", "vieux-marche": "le-vieux-marche", "roche-jaudy": "la-roche-jaudy",
    "trevou": "trevou-treguignec", "treguignec": "trevou-treguignec", "kermaria": "kermaria-sulard",
    "plougrescant-22820": "plougrescant", "trestel": "trevou-treguignec",
}


def commune(nom: str | None) -> dict | None:
    """Commune du Trégor correspondant à un nom de ville libre, ou None si hors périmètre."""
    s = slug(nom or "")
    if not s:
        return None
    s = re.sub(r"-\d{5}$", "", s)
    s = ALIAS.get(s, s)
    return PAR_SLUG.get(s)


TYPES = [
    # (nom, slug, mots-clés cherchés dans le titre puis la description, couleur)
    ("Fest-noz et culture bretonne", "fest-noz", ["fest-noz", "fest noz", "festoù-noz", "fest-deiz", "fest deiz", "bagad", "kan ha diskan", "gouren", "breton", "brezhoneg", "pardon"]),
    ("Festival", "festival", ["festival", "festoù"]),
    ("Concert", "concert", ["concert", "chorale", "orchestre", "récital", "recital", "jazz", "rock", "musique", "chant", "symphon", "orgue", "musical", "dj set", "trio", "quartet", "quatuor", "cabaret"]),
    ("Spectacle", "spectacle", ["spectacle", "théâtre", "theatre", "danse", "humour", "cirque", "marionnette", "conte", "comédie", "ballet", "one man", "impro", "magie", "opéra", "opera"]),
    ("Cinéma", "cinema", ["cinéma", "cinema", "ciné", "cine-", "film", "projection", "documentaire", "court-métrage"]),
    ("Exposition", "exposition", ["exposition", "expo ", "expo:", "photographies", "peinture", "sculpture", "vernissage", "galerie", "œuvres", "oeuvres"]),
    ("Nature et balade", "nature", ["randonnée", "randonnee", "rando", "balade", "marche", "sortie nature", "oiseaux", "estran", "botanique", "découverte du littoral", "nature"]),
    ("Conférence et rencontre", "conference", ["conférence", "conference", "rencontre", "débat", "debat", "table ronde", "lecture", "dédicace", "causerie", "café ", "apéro", "soirée jeux", "forum"]),
    ("Atelier et stage", "atelier", ["atelier", "stage", "initiation", "cours ", "formation", "workshop"]),
    ("Enfants", "enfants", ["enfant", "jeune public", "famille", "bébé", "kids", "goûter", "heure du conte"]),
    ("Sport", "sport", ["trail", "course", "foot", "rugby", "handball", "basket", "tennis", "régate", "regate", "voile", "triathlon", "cyclo", "vélo", "velo", "marathon", "tournoi", "match", "kayak", "surf", "judo", "yoga"]),
    ("Marché et brocante", "marche", ["vide-grenier", "vide grenier", "brocante", "braderie", "bourse", "marché", "marche de noel", "puces", "troc", "foire aux"]),
    ("Foire et salon", "salon", ["salon", "foire", "fête de la", "exposants", "créateurs", "artisans"]),
    ("Visite et patrimoine", "visite", ["visite", "patrimoine", "chapelle", "musée", "musee", "distillerie", "phare", "château", "chateau", "circuit", "découverte"]),
    ("Fête et animation", "fete", ["fête", "fete", "animation", "carnaval", "loto", "repas", "soirée", "soiree", "bal", "kermesse", "téléthon", "telethon", "noël", "noel", "feu d'artifice", "crêpes", "concours"]),
    ("Autre", "autre", []),
]
TYPE_PAR_SLUG = {t[1]: t[0] for t in TYPES}
SLUG_PAR_TYPE = {t[0]: t[1] for t in TYPES}

# Image par défaut d'Alentoor (…/event/default/<catégorie>-medium.jpg) → type.
CATEGORIES_ALENTOOR = {
    "concert": "Concert", "spectacle": "Spectacle", "theatre": "Spectacle", "exposition": "Exposition",
    "festival": "Festival", "conference": "Conférence et rencontre", "brocante-vide-grenier": "Marché et brocante",
    "marche": "Marché et brocante", "foire-salon": "Foire et salon", "sport": "Sport", "festivites": "Fête et animation",
    "activites-enfants": "Enfants", "activites-loisirs": "Atelier et stage", "cinema": "Cinéma",
    "visite": "Visite et patrimoine", "nature": "Nature et balade", "randonnee": "Nature et balade",
}


# Mots trop génériques (« soirée », « animation ») : la catégorie donnée par la source passe avant.
FAIBLES = {"Fête et animation"}


def classer(titre: str, description: str = "", indice: str | None = None) -> str:
    """Type d'un événement : mots-clés du titre d'abord, puis indice de la source, puis description."""
    t = f" {(titre or '').lower()} "
    for nom, _, mots in TYPES:
        if nom not in FAIBLES and any(m in t for m in mots):
            return nom
    if indice and indice in SLUG_PAR_TYPE:
        return indice
    for nom, _, mots in TYPES:
        if nom in FAIBLES and any(m in t for m in mots):
            return nom
    d = f" {(description or '').lower()[:400]} "
    for nom, _, mots in TYPES:
        if any(m in d for m in mots):
            return nom
    return "Autre"


def cle_doublon(titre: str, date_debut: str, insee: str) -> str:
    """Même événement vu par deux sources : titre simplifié + date + commune."""
    mots = [m for m in slug(titre).split("-") if len(m) > 2][:5]
    return f"{'-'.join(mots)}|{date_debut}|{insee}"

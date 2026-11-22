"""Outils communs aux collecteurs : client HTTP poli, JSON-LD, dates, construction d'un événement."""
import html
import json
import re
import time
from datetime import date, datetime
from zoneinfo import ZoneInfo

import httpx

from ..referentiel import COMMUNES, classer, cle_doublon

PARIS = ZoneInfo("Europe/Paris")
UA = "Mozilla/5.0 (compatible; agenda-tregor/1.0; +https://tregor.perceval.sh)"


class Http:
    """Client HTTP avec une pause minimale entre deux requêtes vers le même site."""

    def __init__(self, pause: float = 0.6):
        self.client = httpx.Client(headers={"User-Agent": UA, "Accept-Language": "fr-FR,fr"}, timeout=30, follow_redirects=True)
        self.pause = pause
        self.dernier: dict[str, float] = {}

    def get(self, url: str, **kw) -> httpx.Response:
        hote = httpx.URL(url).host
        attente = self.pause - (time.monotonic() - self.dernier.get(hote, 0))
        if attente > 0:
            time.sleep(attente)
        try:
            return self.client.get(url, **kw)
        finally:
            self.dernier[hote] = time.monotonic()


def jsonld(page: str) -> list[dict]:
    """Objets JSON-LD d'une page HTML, @graph et listes aplatis."""
    objets = []
    for bloc in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', page, re.S):
        try:
            d = json.loads(bloc)
        except ValueError:
            continue
        pile = d if isinstance(d, list) else [d]
        for o in pile:
            if isinstance(o, dict) and "@graph" in o:
                objets += [x for x in o["@graph"] if isinstance(x, dict)]
            elif isinstance(o, dict):
                objets.append(o)
    return objets


def est_evenement(o: dict) -> bool:
    t = o.get("@type")
    types = t if isinstance(t, list) else [t]
    return any(isinstance(x, str) and x.endswith("Event") for x in types)


def texte(s: str | None, limite: int = 1200) -> str:
    """Texte brut : balises retirées, entités décodées, espaces normalisés."""
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = html.unescape(html.unescape(s))
    s = re.sub(r"[ \t\r\f\v]+", " ", s)
    s = re.sub(r"\n\s*\n+", "\n", s).strip()
    return s[:limite].rsplit(" ", 1)[0] + "…" if len(s) > limite else s


def date_heure(valeur: str | None) -> tuple[str | None, str | None]:
    """'2026-11-24T20:00:00+01:00' → ('2026-11-24', '20:00') à l'heure de Paris ; '2026-11-24' → (…, None)."""
    if not valeur:
        return None, None
    v = valeur.strip()
    if len(v) == 10:
        try:
            return date.fromisoformat(v).isoformat(), None
        except ValueError:
            return None, None
    try:
        dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        return None, None
    if dt.tzinfo:
        dt = dt.astimezone(PARIS)
    heure = dt.strftime("%H:%M")
    return dt.date().isoformat(), (None if heure == "00:00" else heure)


def evenement(*, uid, source, titre, commune, date_debut, date_fin=None, heure=None, lieu="", adresse="",
              description="", url="", lat=None, lon=None, prix="", indice_type=None) -> dict | None:
    """Événement normalisé (colonnes de la table NocoDB evenements), ou None s'il est incomplet."""
    titre = casse(texte(titre, 250))
    if not (titre and commune and date_debut):
        return None
    date_fin = date_fin if date_fin and date_fin >= date_debut else date_debut
    description = texte(description)
    return {
        "uid": uid, "source": source, "titre": titre, "type": classer(titre, description, indice_type),
        "date_debut": date_debut, "date_fin": date_fin, "heure": heure or "",
        "ville": commune["nom"], "insee": commune["insee"], "lieu": texte(lieu, 200), "adresse": texte(adresse, 250),
        "lat": lat if lat is not None else commune["lat"], "lon": lon if lon is not None else commune["lon"],
        "description": description, "url": url, "prix": texte(prix, 120),
        "cle_doublon": cle_doublon(titre, date_debut, commune["insee"]),
    }


def casse(t: str) -> str:
    """Titre saisi tout en majuscules → casse de phrase ('VERNISSAGE EXPOSITION' → 'Vernissage exposition')."""
    lettres = [c for c in t if c.isalpha()]
    if len(lettres) > 4 and sum(c.isupper() for c in lettres) / len(lettres) > 0.8:
        t = t[:1].upper() + t[1:].lower()
        for c in COMMUNES:  # les noms de communes gardent leur majuscule
            t = re.sub(rf"\b{re.escape(c['nom'].lower())}\b", c["nom"], t)
    return t


def nombre(v) -> float | None:
    try:
        return round(float(v), 6)
    except (TypeError, ValueError):
        return None

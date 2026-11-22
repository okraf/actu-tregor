"""actu.fr Le Trégor : flux RSS d'articles. Chaque nouvel article est enregistré (table articles) puis
analysé par l'IA (API Ollama) : s'il annonce un événement daté dans le Trégor, l'événement est créé."""
import json
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from email.utils import parsedate_to_datetime

import httpx

from ..config import config
from ..referentiel import TYPES, commune
from .outils import PARIS, Http, evenement, texte

NOM = "actu.fr"
FLUX = ["https://actu.fr/le-tregor/rss.xml"]
MAX_ANALYSES = 40
JOURS_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]

CONSIGNE = """Tu lis un article de presse locale du Trégor (Bretagne). Dis s'il annonce un événement public à venir
(concert, spectacle, fête, marché, exposition, conférence, sortie, compétition ouverte au public…) avec une date.
Un fait divers, un portrait, une décision politique, le résultat d'un match, le compte rendu ou le bilan d'un événement
passé ne sont PAS des événements : réponds alors {{"evenement": false}}.
Article publié le {jour} {date}.
Titre : {titre}
Résumé : {resume}
Communes citées : {communes}
Réponds uniquement en JSON :
{{"evenement": true|false, "titre": "nom court de l'événement", "date_debut": "AAAA-MM-JJ", "date_fin": "AAAA-MM-JJ ou vide",
"heure": "HH:MM ou vide", "ville": "commune", "lieu": "lieu précis ou vide", "type": "un de : {types}"}}"""


def lire_flux(http: Http, journal: list[str]) -> list[dict]:
    articles = []
    for url in FLUX:
        try:
            r = http.get(url)
            r.raise_for_status()
            racine = ET.fromstring(r.content)
        except Exception as e:
            journal.append(f"actu.fr flux {url} : {e}")
            continue
        for item in racine.iter("item"):
            cats = [c.text.strip() for c in item.findall("category") if c.text]
            try:
                publie = parsedate_to_datetime(item.findtext("pubDate")).astimezone(PARIS)
            except Exception:
                publie = datetime.now(PARIS)
            villes = [c for c in cats if commune(c)]
            articles.append({
                "titre": texte(item.findtext("title"), 250), "url": (item.findtext("link") or "").strip(),
                "publie_le": publie, "categories": ", ".join(cats), "ville": villes[0] if villes else "",
                "description": texte(item.findtext("description"), 1500),
            })
    return articles


def analyser(article: dict) -> dict:
    """Appel à l'IA. Lève une exception si l'IA ne répond pas."""
    ia = config().get("ia", {})
    if not ia.get("url"):
        raise RuntimeError("IA non configurée")
    p = article["publie_le"]
    invite = CONSIGNE.format(jour=JOURS_FR[p.weekday()], date=p.date().isoformat(), titre=article["titre"],
                             resume=article["description"], communes=article["categories"],
                             types=", ".join(t[0] for t in TYPES))
    with httpx.Client(verify=ia.get("ca") or True, timeout=180) as h:
        r = h.post(ia["url"].rstrip("/") + "/api/chat", headers={"Authorization": f"Bearer {ia['cle']}"}, json={
            "model": ia["modele"], "stream": False, "think": False, "format": "json",
            "options": {"temperature": 0}, "messages": [{"role": "user", "content": invite}]})
    r.raise_for_status()
    return json.loads(r.json()["message"]["content"])


def vers_evenement(article: dict, a: dict) -> dict | None:
    if not a.get("evenement"):
        return None
    # Ville donnée par l'IA hors du Trégor : rejet (pas de repli sur la commune de l'article).
    c = commune(a.get("ville")) if a.get("ville") else commune(article["ville"])
    try:
        debut = date.fromisoformat(str(a.get("date_debut"))[:10])
    except ValueError:
        return None
    p = article["publie_le"]
    # Garde-fous : un événement annoncé se tient après la publication (le jour même seulement si l'article
    # est paru le matin), et dans l'année.
    premier = p.date() if p.hour < 13 else p.date() + timedelta(days=1)
    if not (premier <= debut <= p.date() + timedelta(days=365)):
        return None
    try:
        fin = date.fromisoformat(str(a.get("date_fin"))[:10]).isoformat()
    except ValueError:
        fin = None
    heure = str(a.get("heure") or "")
    heure = heure if len(heure) == 5 and heure[2] == ":" else None
    type_ia = a.get("type") if a.get("type") in {t[0] for t in TYPES} else None
    return evenement(uid=f"actu.fr:{article['url']}", source=NOM, titre=a.get("titre") or article["titre"], commune=c,
                     date_debut=debut.isoformat(), date_fin=fin, heure=heure, lieu=a.get("lieu") or "",
                     description=article["description"], url=article["url"], indice_type=type_ia)


def collecter(http: Http, nocodb, journal: list[str]) -> tuple[list[dict], int]:
    """Renvoie (événements trouvés, nombre d'articles lus). Écrit les articles dans NocoDB."""
    articles = lire_flux(http, journal)
    existants = {l["url"]: l for l in nocodb.lister("articles", champs="Id,url,statut")}
    nouveaux = [a for a in articles if a["url"] and a["url"] not in existants]
    if nouveaux:
        nocodb.creer("articles", [{
            "titre": a["titre"], "url": a["url"], "publie_le": a["publie_le"].isoformat(), "ville": a["ville"],
            "categories": a["categories"], "description": a["description"], "statut": "a_analyser"} for a in nouveaux])
        existants = {l["url"]: l for l in nocodb.lister("articles", champs="Id,url,statut")}
    a_faire = [a for a in articles if existants.get(a["url"], {}).get("statut") in ("a_analyser", "erreur")][:MAX_ANALYSES]
    evenements, maj = [], []
    for art in a_faire:
        try:
            resultat = analyser(art)
        except Exception as e:
            journal.append(f"actu.fr IA : {type(e).__name__} {e}"[:300])
            maj.append({"Id": existants[art["url"]]["Id"], "statut": "erreur"})
            if "non configurée" in str(e) or isinstance(e, httpx.ConnectError):
                break  # inutile d'insister : on reprendra au prochain passage
            continue
        ev = vers_evenement(art, resultat)
        if ev:
            evenements.append(ev)
        maj.append({"Id": existants[art["url"]]["Id"], "statut": "evenement" if ev else "autre",
                    "evenement_uid": ev["uid"] if ev else "", "analyse": json.dumps(resultat, ensure_ascii=False)[:2000]})
    if maj:
        nocodb.modifier("articles", maj)
    return evenements, len(articles)

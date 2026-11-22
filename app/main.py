"""Site tregor : agenda des événements du Trégor."""
import json
import logging
import threading
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlencode

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import donnees
from .collecte import passage
from .config import config
from .referentiel import COMMUNES, PAR_SLUG, SLUG_PAR_TYPE, TYPE_PAR_SLUG, TYPES, slug

ICI = Path(__file__).resolve().parent
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=ICI / "static"), name="static")
gabarits = Jinja2Templates(directory=ICI / "templates")

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
JOURS_COURTS = ["lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim."]
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
QUAND = {"aujourdhui": "Aujourd'hui", "demain": "Demain", "weekend": "Ce week-end", "semaine": "Les 7 prochains jours",
         "mois": "Les 30 prochains jours"}
LONG = 3  # au-delà de 3 jours, un événement va dans « En ce moment » (expositions, visites…)


def date_fr(d: date, annee: bool = False) -> str:
    return f"{JOURS[d.weekday()]} {d.day}{'er' if d.day == 1 else ''} {MOIS[d.month - 1]}" + (f" {d.year}" if annee else "")


gabarits.env.filters["date_fr"] = date_fr
gabarits.env.globals.update(url_site=config()["site"]["url"].rstrip("/"), CONTACT="https://perceval.sh/#contact", TYPES=TYPES, SLUG_PAR_TYPE=SLUG_PAR_TYPE, slug=slug,
                            NOMS_SOURCES={"alentoor": "Alentoor", "openagenda": "OpenAgenda", "unidivers": "Unidivers", "actu.fr": "actu.fr"})


class SansSante(logging.Filter):
    """Les sondes /sante ne remplissent pas les logs d'accès."""

    def filter(self, record):
        return "/sante" not in record.getMessage()


logging.getLogger("uvicorn.access").addFilter(SansSante())


def fenetre(quand: str | None, jour: str | None) -> tuple[date, date, str]:
    auj = date.today()
    if jour:
        try:
            d = date.fromisoformat(jour)
            return d, d, date_fr(d).capitalize()
        except ValueError:
            pass
    if quand == "aujourdhui":
        return auj, auj, QUAND[quand]
    if quand == "demain":
        return auj + timedelta(days=1), auj + timedelta(days=1), QUAND[quand]
    if quand == "weekend":
        samedi = auj + timedelta(days=(5 - auj.weekday()) % 7) if auj.weekday() < 5 else auj
        return samedi, auj + timedelta(days=6 - auj.weekday()), QUAND[quand]
    if quand == "mois":
        return auj, auj + timedelta(days=29), QUAND[quand]
    return auj, auj + timedelta(days=6), QUAND["semaine"]


def filtrer(evs: list[dict], type_: str | None, ville: str | None, q: str | None) -> list[dict]:
    nom_type = TYPE_PAR_SLUG.get(type_ or "")
    nom_ville = PAR_SLUG[ville]["nom"] if ville in PAR_SLUG else None
    mots = slug(q or "").split("-") if q else []
    sortie = []
    for e in evs:
        if nom_type and e.get("type") != nom_type:
            continue
        if nom_ville and e.get("ville") != nom_ville:
            continue
        if mots and not all(m in slug(f"{e.get('titre')} {e.get('lieu')} {e.get('ville')} {e.get('description', '')[:300]}") for m in mots):
            continue
        sortie.append(e)
    return sortie


def lien(base: str = "/", **params) -> str:
    p = {k: v for k, v in params.items() if v}
    return base + ("?" + urlencode(p) if p else "")


def page_agenda(request: Request, type_: str | None = None, ville: str | None = None, quand: str | None = None,
                jour: str | None = None, q: str | None = None, canonique: str = "/"):
    if type_ and type_ not in TYPE_PAR_SLUG or ville and ville not in PAR_SLUG:
        raise HTTPException(404)
    try:
        tous = donnees.a_venir()
        indispo = False
    except Exception:
        tous, indispo = [], True
    choisis = filtrer(tous, type_, ville, q)
    debut, fin, libelle = fenetre(quand, jour)
    d0, d1 = debut.isoformat(), fin.isoformat()
    dans = [e for e in choisis if e["date_debut"] <= d1 and e["date_fin"] >= d0]
    courts = [e for e in dans if (date.fromisoformat(e["date_fin"]) - date.fromisoformat(e["date_debut"])).days < LONG]
    longs = [e for e in dans if e not in courts]
    jours: dict[str, list] = {}
    for e in courts:
        jours.setdefault(max(e["date_debut"], d0), []).append(e)
    jours = {date.fromisoformat(k): sorted(v, key=lambda e: (e.get("heure") or "99", e["titre"])) for k, v in sorted(jours.items())}
    def url(**changes) -> str:
        """Lien qui garde les filtres courants (sauf celui porté par le chemin) en changeant ceux donnés."""
        etat = {"type": type_, "ville": ville, "q": q, "quand": None, "jour": None, **changes}
        etat.pop("ville" if canonique.startswith("/ville/") else "type" if canonique.startswith("/type/") else "", None)
        return lien(canonique, **etat)

    # Ruban des 14 prochains jours : nombre d'événements ce jour-là (y compris en cours), mêmes filtres.
    auj = date.today()
    ruban = []
    for i in range(14):
        d = auj + timedelta(days=i)
        di = d.isoformat()
        n = sum(1 for e in choisis if e["date_debut"] <= di <= e["date_fin"])
        ruban.append({"date": d, "n": n, "actif": jour == di, "lien": url(jour=di)})
    maxi = max([r["n"] for r in ruban] + [1])
    nom_ville = PAR_SLUG[ville]["nom"] if ville in PAR_SLUG else None
    nom_type = TYPE_PAR_SLUG.get(type_ or "")
    sujet = (nom_type or "Sorties et événements") + (f" à {nom_ville}" if nom_ville else " dans le Trégor")
    titre = f"{sujet} : {libelle.lower()}" if (quand or jour) else f"{sujet} : l'agenda"
    villes_actives = sorted({e["ville"] for e in tous})
    contexte = {
        "request": request, "jours": jours, "longs": longs, "ruban": ruban, "maxi": maxi, "libelle": libelle,
        "type_": type_ or "", "ville": ville or "", "quand": quand or ("" if jour else "semaine"), "jour": jour or "",
        "q": q or "", "titre": titre, "sujet": sujet, "nb": len(courts) + len(longs), "indispo": indispo,
        "communes": [c for c in COMMUNES if c["nom"] in villes_actives] or COMMUNES, "QUAND": QUAND,
        "canonique": config()["site"]["url"].rstrip("/") + canonique, "aujourdhui": auj,
        "lien_quand": lambda k: url(quand=k), "url": url,
        "description": f"{sujet} : concerts, fest-noz, expositions, marchés, sorties nature. Filtrez par jour, par commune et par type d'événement.",
    }
    return gabarits.TemplateResponse(request, "agenda.html", contexte, status_code=503 if indispo else 200)


@app.get("/", response_class=HTMLResponse)
def accueil(request: Request, type: str | None = None, ville: str | None = None, quand: str | None = None,
            jour: str | None = None, q: str | None = None):
    return page_agenda(request, type or None, ville or None, quand, jour, q)


@app.get("/ville/{ville}", response_class=HTMLResponse)
def par_ville(request: Request, ville: str, type: str | None = None, quand: str | None = None, jour: str | None = None, q: str | None = None):
    return page_agenda(request, type or None, ville, quand, jour, q, canonique=f"/ville/{ville}")


@app.get("/type/{type_}", response_class=HTMLResponse)
def par_type(request: Request, type_: str, ville: str | None = None, quand: str | None = None, jour: str | None = None, q: str | None = None):
    return page_agenda(request, type_, ville or None, quand, jour, q, canonique=f"/type/{type_}")


@app.get("/evenement/{ident}", response_class=HTMLResponse)
def fiche(request: Request, ident: str):
    try:
        e = donnees.un(int(ident.split("-", 1)[0]))
    except ValueError:
        e = None
    if not e:
        raise HTTPException(404)
    base = config()["site"]["url"].rstrip("/")
    chemin = f"/evenement/{e['Id']}-{slug(e['titre'])[:80]}"
    ld = {"@context": "https://schema.org", "@type": "Event", "name": e["titre"],
          "startDate": e["date_debut"] + (f"T{e['heure']}:00" if e.get("heure") else ""), "endDate": e["date_fin"],
          "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode", "eventStatus": "https://schema.org/EventScheduled",
          "location": {"@type": "Place", "name": e.get("lieu") or e["ville"],
                       "address": {"@type": "PostalAddress", "streetAddress": e.get("adresse") or "", "addressLocality": e["ville"],
                                   "addressRegion": "Bretagne", "addressCountry": "FR"}},
          "description": (e.get("description") or "")[:500], "url": base + chemin}
    voisins = [x for x in donnees.a_venir() if x["ville"] == e["ville"] and x["Id"] != e["Id"]][:8]
    return gabarits.TemplateResponse(request, "evenement.html", {
        "request": request, "e": e, "ld": json.dumps(ld, ensure_ascii=False).replace("</", "<\\/"), "canonique": base + chemin,
        "debut": date.fromisoformat(e["date_debut"]), "fin": date.fromisoformat(e["date_fin"]), "voisins": voisins,
        "titre": f"{e['titre']} à {e['ville']}", "description": (e.get("description") or e["titre"])[:155],
        "slug_ville": slug(e["ville"])})


@app.get("/api/evenements")
def api_evenements(type: str | None = None, ville: str | None = None, quand: str | None = None, jour: str | None = None, q: str | None = None):
    debut, fin, _ = fenetre(quand or "mois", jour)
    evs = [e for e in filtrer(donnees.a_venir(), type, ville, q) if e["date_debut"] <= fin.isoformat() and e["date_fin"] >= debut.isoformat()]
    champs = ["Id", "titre", "type", "date_debut", "date_fin", "heure", "ville", "insee", "lieu", "adresse", "lat", "lon", "url", "source", "prix"]
    return {"evenements": [{k: e.get(k) for k in champs} for e in evs]}


_collecte_en_cours = threading.Lock()


@app.post("/api/collecte")
def collecte(x_cle_collecte: str = Header(default=""), source: str | None = None):
    cle = config()["site"].get("cle_collecte")
    if not cle or x_cle_collecte != cle:
        raise HTTPException(401)
    if not _collecte_en_cours.acquire(blocking=False):
        return JSONResponse({"ok": False, "erreur": "collecte déjà en cours"}, status_code=409)
    try:
        rapport = passage.lancer([source] if source else None)
    finally:
        _collecte_en_cours.release()
    donnees.vider()
    return rapport


FAQ = [
    ("D'où viennent les événements ?",
     "Ils sont relevés automatiquement toutes les six heures sur Alentoor, OpenAgenda et Unidivers, et dans les articles du Trégor publiés par actu.fr, lus par une intelligence artificielle qui repère les annonces datées. Chaque fiche renvoie vers l'annonce d'origine."),
    ("Comment ajouter mon événement ?",
     "Publiez-le sur OpenAgenda ou Alentoor, gratuitement : il apparaîtra ici au passage suivant, en moins de six heures. Pensez à indiquer la commune, la date et l'heure."),
    ("Un événement est annulé ou contient une erreur, que faire ?",
     "Corrigez-le d'abord à la source (le site de l'annonce d'origine) : la mise à jour suivra ici. Si l'erreur vient de ce site, écrivez-nous depuis la page contact avec le lien de la fiche."),
    ("Quelles communes sont couvertes ?",
     "Les 57 communes de Lannion-Trégor Communauté, de Tréguier à Plestin-les-Grèves et de Perros-Guirec à Plouaret, et le Trégor finistérien : Locquirec, Guimaëc, Lanmeur, Plougasnou, Saint-Jean-du-Doigt, Plouégat-Guérand, Guerlesquin et Botsorhel."),
    ("Les horaires et les tarifs sont-ils fiables ?",
     "Ils sont repris tels que les organisateurs les publient. Un horaire peut changer au dernier moment : vérifiez sur l'annonce d'origine avant de vous déplacer."),
    ("Le site est-il gratuit ? Y a-t-il de la publicité ?",
     "Oui, il est gratuit, sans publicité, sans compte et sans cookie. Son code est ouvert sur GitHub."),
]


def page_simple(request: Request, gabarit: str, titre: str, description: str, chemin: str, **extra):
    base = config()["site"]["url"].rstrip("/")
    return gabarits.TemplateResponse(request, gabarit, {"request": request, "titre": titre, "description": description,
                                                        "canonique": base + chemin, **extra})


@app.get("/faq", response_class=HTMLResponse)
def faq(request: Request):
    ld = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": r}} for q, r in FAQ]}
    return page_simple(request, "faq.html", "Questions fréquentes", "D'où viennent les événements, comment ajouter le vôtre, "
                       "quelles communes sont couvertes : les réponses.", "/faq", faq=FAQ,
                       ld=json.dumps(ld, ensure_ascii=False).replace("</", "<\\/"))


@app.get("/mentions-legales", response_class=HTMLResponse)
def mentions(request: Request):
    return page_simple(request, "mentions.html", "Mentions légales", "Éditeur, hébergeur, données personnelles et sources de "
                       "l'agenda du Trégor.", "/mentions-legales")


@app.middleware("http")
async def cache_statique(request: Request, call_next):
    reponse = await call_next(request)
    if request.url.path.startswith("/static/") and reponse.status_code == 200:
        reponse.headers["Cache-Control"] = "public, max-age=604800"
    return reponse


@app.get("/sante")
def sante():
    return PlainTextResponse("ok")


@app.get("/robots.txt")
def robots():
    base = config()["site"]["url"].rstrip("/")
    return PlainTextResponse(f"User-agent: *\nDisallow: /api/\nDisallow: /*?*q=\n\nSitemap: {base}/sitemap.xml\n")


@app.get("/sitemap.xml")
def sitemap():
    base = config()["site"]["url"].rstrip("/")
    try:
        evs = donnees.a_venir()
    except Exception:
        evs = []
    urls = [f"{base}/", f"{base}/faq", f"{base}/mentions-legales"] + [f"{base}/type/{t[1]}" for t in TYPES if any(e.get("type") == t[0] for e in evs)]
    urls += [f"{base}/ville/{c['slug']}" for c in COMMUNES if any(e["ville"] == c["nom"] for e in evs)]
    urls += [f"{base}/evenement/{e['Id']}-{slug(e['titre'])[:80]}" for e in evs]
    corps = "".join(f"<url><loc>{u}</loc></url>" for u in urls)
    return Response(f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{corps}</urlset>',
                    media_type="application/xml")


@app.exception_handler(404)
def introuvable(request: Request, exc):
    return gabarits.TemplateResponse(request, "introuvable.html", {"request": request, "titre": "Page introuvable", "description": "",
                                                                   "canonique": ""}, status_code=404)

"""OpenAgenda : export open data quotidien (public.opendatasoft.com), filtré sur les codes INSEE du Trégor."""
from datetime import datetime, timezone

from ..referentiel import COMMUNES, PAR_INSEE, commune
from .outils import Http, date_heure, evenement, nombre

NOM = "openagenda"
API = "https://public.opendatasoft.com/api/explore/v2.1/catalog/datasets/evenements-publics-openagenda/records"
# Agendas hors loisirs (ateliers emploi des agences France Travail…).
AGENDAS_EXCLUS = ("france travail", "francetravail")


def convertir(o: dict, maintenant: str) -> dict | None:
    if any(x in (o.get("originagenda_title") or "").lower() for x in AGENDAS_EXCLUS):
        return None
    c = PAR_INSEE.get(o.get("location_insee") or "") or commune(o.get("location_city"))
    if not c:
        return None
    # Première séance à venir (les événements récurrents ont plusieurs séances).
    seances = sorted((t.get("begin") for t in (o.get("timings") or []) if isinstance(t, dict) and t.get("begin")))
    prochaine = next((s for s in seances if s >= maintenant), None) or o.get("firstdate_begin")
    debut, heure = date_heure(prochaine)
    fin, _ = date_heure(o.get("lastdate_end"))
    geo = o.get("location_coordinates") or {}
    mots = " ".join(o.get("keywords_fr") or [])
    return evenement(
        uid=f"openagenda:{o.get('uid')}", source=NOM, titre=o.get("title_fr"), commune=c,
        date_debut=debut, date_fin=fin, heure=heure, lieu=o.get("location_name") or "",
        adresse=o.get("location_address") or "",
        description=" ".join(filter(None, [o.get("description_fr"), o.get("longdescription_fr")])) + (f"\n{mots}" if mots else ""),
        url=o.get("canonicalurl") or "", lat=nombre(geo.get("lat")), lon=nombre(geo.get("lon")),
        prix=o.get("conditions_fr") or "",
    )


def collecter(http: Http, connus: set[str], journal: list[str]) -> list[dict]:
    codes = ",".join(f'"{c["insee"]}"' for c in COMMUNES)
    villes = ",".join(f'"{c["nom"]}"' for c in COMMUNES)
    where = f"(location_insee in ({codes}) or location_city in ({villes})) and lastdate_end >= now()"
    maintenant = datetime.now(timezone.utc).isoformat()
    resultats, offset = [], 0
    while offset < 9900:
        r = http.get(API, params={"where": where, "limit": 100, "offset": offset, "order_by": "firstdate_begin"})
        if r.status_code != 200:
            journal.append(f"openagenda : HTTP {r.status_code} {r.text[:200]}")
            break
        lot = r.json().get("results", [])
        resultats += lot
        if len(lot) < 100:
            break
        offset += 100
    return [ev for ev in (convertir(o, maintenant) for o in resultats) if ev]

"""Événements à venir lus dans NocoDB, gardés en mémoire quelques minutes."""
import threading
import time
from datetime import date

from .nocodb import NocoDB

DUREE_CACHE = 180
_verrou = threading.Lock()
_cache: dict = {"t": 0.0, "liste": [], "par_id": {}}


def a_venir() -> list[dict]:
    with _verrou:
        if time.monotonic() - _cache["t"] > DUREE_CACHE:
            try:
                aujourd_hui = date.today().isoformat()
                lignes = NocoDB().lister("evenements", where=f"(date_fin,ge,exactDate,{aujourd_hui})~and(masque,neq,true)",
                                         tri="date_debut,heure")
                for l in lignes:
                    l["date_fin"] = l.get("date_fin") or l["date_debut"]
                _cache.update(t=time.monotonic(), liste=lignes, par_id={l["Id"]: l for l in lignes})
            except Exception:
                if not _cache["liste"]:
                    raise  # aucune donnée à servir : erreur visible
                _cache["t"] = time.monotonic() - DUREE_CACHE + 30  # NocoDB indisponible : on réessaie dans 30 s
        return _cache["liste"]


def un(id_: int) -> dict | None:
    a_venir()
    if id_ in _cache["par_id"]:
        return _cache["par_id"][id_]
    l = NocoDB().lire("evenements", id_)
    if l and not l.get("masque"):
        l["date_fin"] = l.get("date_fin") or l["date_debut"]
        return l
    return None


def vider():
    _cache["t"] = 0.0

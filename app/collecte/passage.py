"""Un passage de collecte : toutes les sources, fusion, écriture dans NocoDB (evenements + collectes)."""
import time
from datetime import datetime, timezone

from ..nocodb import NocoDB
from . import actu, alentoor, openagenda, unidivers
from .outils import Http

# Ordre = priorité en cas de doublon (la première source qui a vu l'événement le garde).
SOURCES = [alentoor, openagenda, unidivers]
CHAMPS_SUIVIS = ["titre", "type", "date_debut", "date_fin", "heure", "ville", "insee", "lieu", "adresse",
                 "description", "url", "prix", "cle_doublon"]


def lancer(seulement: list[str] | None = None) -> dict:
    debut = time.monotonic()
    debut_iso = datetime.now(timezone.utc).isoformat()
    noco = NocoDB()
    http = Http()
    existants = {l["uid"]: l for l in noco.lister("evenements", champs="Id,uid," + ",".join(CHAMPS_SUIVIS)) if l.get("uid")}
    cles = {l["cle_doublon"]: uid for uid, l in existants.items() if l.get("cle_doublon")}
    rapport = {"debut": debut_iso, "sources": {}}
    for module in SOURCES + [actu]:
        if seulement and module.NOM not in seulement:
            continue
        t0, journal = time.monotonic(), []
        try:
            if module is actu:
                trouves, lus = actu.collecter(http, noco, journal)
            else:
                trouves = module.collecter(http, set(existants), journal)
                lus = len(trouves)
        except Exception as e:
            trouves, lus = [], 0
            journal.append(f"{module.NOM} : échec {type(e).__name__} {e}"[:500])
        creer, modifier = [], []
        maintenant = datetime.now(timezone.utc).isoformat()
        for ev in trouves:
            ancien = existants.get(ev["uid"])
            if ancien:
                diff = {k: ev[k] for k in CHAMPS_SUIVIS if (ancien.get(k) or "") != (ev[k] or "")}
                modifier.append({"Id": ancien["Id"], "vu_le": maintenant, **diff})
                if diff:
                    ancien.update(diff)
                continue
            if ev["cle_doublon"] in cles:  # déjà vu par une autre source
                continue
            ev["vu_le"] = maintenant
            creer.append(ev)
            existants[ev["uid"]] = ev
            cles[ev["cle_doublon"]] = ev["uid"]
        try:
            noco.creer("evenements", creer)
            noco.modifier("evenements", modifier)
        except Exception as e:
            journal.append(f"{module.NOM} : écriture NocoDB {e}"[:500])
        stats = {"lus": lus, "nouveaux": len(creer), "mis_a_jour": sum(len(m) > 2 for m in modifier),
                 "duree_s": round(time.monotonic() - t0), "erreurs": journal}
        rapport["sources"][module.NOM] = stats
        try:
            noco.creer("collectes", [{"debut": debut_iso, "source": module.NOM, "lus": lus, "nouveaux": stats["nouveaux"],
                                      "mis_a_jour": stats["mis_a_jour"], "duree_s": stats["duree_s"],
                                      "erreurs": "\n".join(journal)[:5000]}])
        except Exception:
            pass
    rapport["duree_s"] = round(time.monotonic() - debut)
    rapport["nouveaux"] = sum(s["nouveaux"] for s in rapport["sources"].values())
    rapport["ok"] = all(s["lus"] > 0 for s in rapport["sources"].values())
    return rapport


if __name__ == "__main__":
    import json
    import sys
    print(json.dumps(lancer(sys.argv[1:] or None), ensure_ascii=False, indent=1))

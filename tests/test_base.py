from datetime import date, datetime

from app.collecte import actu, alentoor
from app.collecte.outils import PARIS, casse, date_heure
from app.referentiel import classer, cle_doublon, commune


def test_commune_alias_et_hors_perimetre():
    assert commune("LANNION")["insee"] == "22113"
    assert commune("Ploumanac'h")["nom"] == "Perros-Guirec"
    assert commune("La Roche-Derrien")["nom"] == "La Roche-Jaudy"
    assert commune("Lannion 22300")["nom"] == "Lannion"
    assert commune("Rennes") is None


def test_classer():
    assert classer("Fest-noz avec les Frères Morvan") == "Fest-noz et culture bretonne"
    assert classer("Vide grenier de Noël") == "Marché et brocante"
    assert classer("Apéro des randonneurs") == "Nature et balade"
    assert classer("Soirée", indice="Concert") == "Concert"
    assert classer("Truc") == "Autre"


def test_dates_et_casse():
    assert date_heure("2026-11-24T20:00:00+01:00") == ("2026-11-24", "20:00")
    assert date_heure("2026-11-24T19:00:00+00:00") == ("2026-11-24", "20:00")
    assert date_heure("2026-11-24") == ("2026-11-24", None)
    assert casse("VERNISSAGE À LANNION") == "Vernissage à Lannion"
    assert casse("Concert de Noël") == "Concert de Noël"
    assert cle_doublon("Le grand Fest-Noz !", "2026-11-28", "22113") == cle_doublon("GRAND FEST NOZ", "2026-11-28", "22113")


def test_alentoor_convertir():
    o = {"@type": "Event", "@id": "https://www.alentoor.fr/agenda/6479995", "name": "Escale Armoricaine",
         "url": "https://www.alentoor.fr/lannion/agenda/6479995-escale-armoricaine", "description": "Concert",
         "image": ["https://www.alentoor.fr/assets/img/event/default/concert-medium.jpg"],
         "location": {"name": "Eglise", "address": {"addressLocality": "Lannion"}}, "startDate": "2026-11-22", "endDate": "2026-11-22"}
    ev = alentoor.convertir(o)
    assert ev["uid"] == "alentoor:6479995" and ev["type"] == "Concert" and ev["ville"] == "Lannion"
    o["location"]["address"]["addressLocality"] = "Brest"
    assert alentoor.convertir(o) is None


def test_actu_garde_fous():
    art = {"titre": "Match", "url": "u", "ville": "Lannion", "description": "", "categories": "Lannion",
           "publie_le": datetime(2026, 11, 21, 22, 33, tzinfo=PARIS)}
    # Paru le soir : un événement du jour même est forcément passé.
    assert actu.vers_evenement(art, {"evenement": True, "date_debut": "2026-11-21", "ville": "Lannion"}) is None
    ev = actu.vers_evenement(art, {"evenement": True, "date_debut": "2026-11-28", "ville": "Lannion", "type": "Concert", "titre": "Concert"})
    assert ev["date_debut"] == "2026-11-28" and ev["type"] == "Concert"
    assert actu.vers_evenement(art, {"evenement": False}) is None

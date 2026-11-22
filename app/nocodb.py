"""Client minimal de l'API v2 de NocoDB (enregistrements)."""
import httpx

from .config import config


class NocoDB:
    def __init__(self):
        c = config()["nocodb"]
        self.tables = {k.removeprefix("table_"): v for k, v in c.items() if k.startswith("table_")}
        self.http = httpx.Client(base_url=c["url"].rstrip("/"), headers={"xc-token": c["token"]}, timeout=60)

    def _chemin(self, table: str) -> str:
        return f"/api/v2/tables/{self.tables[table]}/records"

    def lister(self, table: str, where: str | None = None, champs: str | None = None, tri: str | None = None) -> list[dict]:
        """Toutes les lignes (pagination par 1000)."""
        lignes, offset = [], 0
        while True:
            params = {"limit": 1000, "offset": offset}
            if where:
                params["where"] = where
            if champs:
                params["fields"] = champs
            if tri:
                params["sort"] = tri
            r = self.http.get(self._chemin(table), params=params)
            r.raise_for_status()
            d = r.json()
            lignes += d["list"]
            if d["pageInfo"].get("isLastPage", True) or not d["list"]:
                return lignes
            offset += len(d["list"])

    def lire(self, table: str, id_: int) -> dict | None:
        r = self.http.get(f"{self._chemin(table)}/{id_}")
        if r.status_code == 404:
            return None
        r.raise_for_status()
        d = r.json()
        return d if d.get("Id") else None

    def creer(self, table: str, lignes: list[dict]) -> None:
        for i in range(0, len(lignes), 100):
            self.http.post(self._chemin(table), json=lignes[i:i + 100]).raise_for_status()

    def modifier(self, table: str, lignes: list[dict]) -> None:
        """lignes : dicts avec la clé Id."""
        for i in range(0, len(lignes), 100):
            self.http.patch(self._chemin(table), json=lignes[i:i + 100]).raise_for_status()

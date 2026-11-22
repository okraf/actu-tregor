"""Configuration statique : /config/config.toml dans le conteneur, ./config.toml sur le poste de dev."""
import tomllib
from functools import lru_cache
from pathlib import Path

CHEMINS = [Path("/config/config.toml"), Path("config.toml")]


@lru_cache
def config() -> dict:
    for chemin in CHEMINS:
        if chemin.exists():
            return tomllib.loads(chemin.read_text())
    raise FileNotFoundError("config.toml introuvable (copier config.example.toml)")

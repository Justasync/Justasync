#!/usr/bin/env python3
"""Récupère les données « vivantes » du profil et les écrit dans outils/donnees/vivant.json.

Uniquement des données PUBLIQUES : dépôts publics de GitHub (tout dépôt privé est écarté,
même si le jeton y a accès) et l'écoute de la semaine sur Last.fm (Spotify → Last.fm).

Variables d'environnement (toutes facultatives) :
  GITHUB_TOKEN    jeton GitHub (dans l'Action : celui du dépôt, qui ne voit pas les dépôts privés)
  LASTFM_API_KEY  clé de l'API Last.fm
  LASTFM_USER     nom d'utilisateur Last.fm
Sans Last.fm, la ligne de musique n'apparaît simplement pas.
"""
import datetime as dt
import json
import os
import pathlib
import urllib.parse
import urllib.request
from collections import Counter

UTILISATEUR = "Justasync"
DEPOT_PROFIL = "Justasync/Justasync"  # le dépôt du profil ne compte pas (code du générateur)
SORTIE = pathlib.Path(__file__).resolve().parent / "donnees/vivant.json"


def api(url, github=True):
    entetes = {"User-Agent": "profil-readme", "Accept": "application/vnd.github+json"} if github else {"User-Agent": "profil-readme"}
    if github and os.environ.get("GITHUB_TOKEN"):
        entetes["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=entetes), timeout=30) as r:
        return json.load(r)


def commits(depuis):
    """Commits publics de l'utilisateur depuis une date (API de recherche), hors dépôt du profil."""
    q = urllib.parse.quote(f"author:{UTILISATEUR} committer-date:>={depuis}")
    liste, page = [], 1
    while True:
        r = api(f"https://api.github.com/search/commits?q={q}&per_page=100&page={page}")
        liste += [c for c in r["items"] if not c["repository"].get("private")
                  and c["repository"]["full_name"] != DEPOT_PROFIL]
        if len(r["items"]) < 100 or page == 10:
            return liste
        page += 1


def github(aujourdhui):
    depots = [d for d in api(f"https://api.github.com/users/{UTILISATEUR}/repos?type=owner&per_page=100")
              if not d["private"] and not d["fork"]]
    # langages : octets de code de chaque dépôt public (hors dépôt du profil)
    octets = Counter()
    for d in depots:
        if d["full_name"] != DEPOT_PROFIL:
            octets.update(api(d["languages_url"]))
    total = sum(octets.values()) or 1
    langages = [[nom, round(n * 100 / total)] for nom, n in octets.most_common(4)]
    # commits de l'année et dépôt le plus actif des 7 derniers jours
    de_lannee = commits(f"{aujourdhui.year}-01-01")
    annee = len(de_lannee)
    recent = max(de_lannee, key=lambda c: c["commit"]["committer"]["date"], default=None)
    actifs = Counter(c["repository"]["name"] for c in commits((aujourdhui - dt.timedelta(days=7)).isoformat()))
    semaine_top = list(actifs.most_common(1)[0]) if actifs else None
    return {
        "depots_publics": len([d for d in depots if d["full_name"] != DEPOT_PROFIL]),
        "commits_annee": annee,
        "langages": langages,
        "semaine": semaine_top,  # [dépôt, nombre de commits] ou null
        "dernier": [recent["repository"]["name"], recent["commit"]["committer"]["date"][:10]] if recent else None,
        "pousse": {d["name"]: d["pushed_at"][:10] for d in depots},  # dernière mise à jour de chaque dépôt
    }


def lastfm():
    cle, nom = os.environ.get("LASTFM_API_KEY"), os.environ.get("LASTFM_USER")
    if not (cle and nom):
        return None
    p = urllib.parse.urlencode({"method": "user.gettoptracks", "user": nom, "period": "7day",
                                "limit": 1, "api_key": cle, "format": "json"})
    titres = api(f"https://ws.audioscrobbler.com/2.0/?{p}", github=False)["toptracks"]["track"]
    if not titres:
        return None
    t = titres[0]
    return {"titre": t["name"], "artiste": t["artist"]["name"], "ecoutes": int(t["playcount"])}


def main():
    aujourdhui = dt.date.today()
    donnees = {"date": aujourdhui.isoformat(), **github(aujourdhui), "musique": lastfm()}
    SORTIE.parent.mkdir(exist_ok=True)
    SORTIE.write_text(json.dumps(donnees, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(donnees, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

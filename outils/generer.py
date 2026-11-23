#!/usr/bin/env python3
"""Génère le README de profil GitHub et ses images SVG (thème sombre et thème clair).

Tout vient de l'identité Justasync : couleurs de tokens/web.css, polices Fraunces 600,
Source Sans 3 et JetBrains Mono (intégrées en sous-ensemble dans chaque SVG) et la veta
(fissure kintsugi) de tokens/movimiento.js, portée ici en Python.

Les données « vivantes » (GitHub public, Last.fm) viennent de outils/donnees/vivant.json,
écrit par outils/actualiser.py. Sur mon PC, les polices, l'emblème et voz.md sont copiés dans
outils/ à chaque génération, pour que l'Action GitHub (qui n'a pas mon PC) produise la même chose.

Usage : python3 outils/generer.py [--branche main] [--apercu]
  --branche  branche GitHub utilisée dans les liens des images (main par défaut)
  --apercu   écrit aussi apercu-sombre.html / apercu-clair.html pour vérifier en local
"""
import argparse
import base64
import datetime as dt
import hashlib
import html
import io
import json
import math
import pathlib
import shutil
from collections import defaultdict

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

RACINE = pathlib.Path(__file__).resolve().parent.parent
ASSETS = RACINE / "assets"
OUTILS = RACINE / "outils"
IDENTITE = pathlib.Path.home() / "Documents/identidad"
FONTES = pathlib.Path.home() / ".local/share/fonts"
SOURCE_SANS = pathlib.Path("/usr/share/fonts/adobe-source-sans-pro-fonts")


def source(original, nom):
    """Fichier de mon PC s'il existe (copié dans outils/ quand il change), sinon la copie du dépôt."""
    copie = OUTILS / nom
    if original.exists():
        if not copie.exists() or copie.read_bytes() != original.read_bytes():
            copie.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original, copie)
    return copie
UTILISATEUR = "Justasync"
DEPOT = "Justasync/Justasync"

# ---------------------------------------------------------------- polices
POLICES = {  # polices libres (OFL), copiées dans outils/polices/
    "JaTitre": (FONTES / "fraunces/Fraunces-variable.ttf", {"opsz": 56, "wght": 600, "SOFT": 0, "WONK": 0}),
    "JaTitreM": (FONTES / "fraunces/Fraunces-variable.ttf", {"opsz": 30, "wght": 600, "SOFT": 0, "WONK": 0}),
    "JaTexte": (SOURCE_SANS / "SourceSans3-Regular.otf", None),
    "JaTexteG": (SOURCE_SANS / "SourceSans3-Semibold.otf", None),
    "JaTexteI": (SOURCE_SANS / "SourceSans3-It.otf", None),
    "JaCode": (FONTES / "JetBrainsMonoNerd/JetBrainsMonoNerdFontMono-Regular.ttf", None),
    "JaCodeM": (FONTES / "JetBrainsMonoNerd/JetBrainsMonoNerdFontMono-Medium.ttf", None),
}
SECOURS = {"JaTitre": "Georgia, serif", "JaTitreM": "Georgia, serif", "JaTexte": "system-ui, sans-serif",
           "JaTexteG": "system-ui, sans-serif", "JaTexteI": "system-ui, sans-serif",
           "JaCode": "ui-monospace, monospace", "JaCodeM": "ui-monospace, monospace"}
_octets = {}


def octets_police(fam):
    """Police complète (instanciée si variable), gardée en mémoire sous forme d'octets."""
    if fam not in _octets:
        chemin, axes = POLICES[fam]
        f = TTFont(source(chemin, "polices/" + chemin.name), recalcTimestamp=False)  # même date à chaque génération : fichiers identiques
        if axes:
            f = instancer.instantiateVariableFont(f, axes)
        b = io.BytesIO()
        f.save(b)
        _octets[fam] = b.getvalue()
    return _octets[fam]


_metriques = {}


def mesure(txt, fam, taille, espacement=0.0):
    """Largeur du texte en pixels (avances des glyphes, sans crénage)."""
    if fam not in _metriques:
        f = TTFont(io.BytesIO(octets_police(fam)))
        _metriques[fam] = (f.getBestCmap(), f["hmtx"].metrics, f["head"].unitsPerEm)
    cmap, hmtx, upm = _metriques[fam]
    total = 0
    for c in txt:
        g = cmap.get(ord(c))
        total += hmtx[g][0] if g in hmtx else upm * 0.5
    return total / upm * taille + espacement * max(0, len(txt) - 1)


def couper(txt, fam, taille, largeur_max):
    lignes, courante = [], ""
    for mot in txt.split(" "):
        essai = (courante + " " + mot).strip()
        if mesure(essai, fam, taille) <= largeur_max or not courante:
            courante = essai
        else:
            lignes.append(courante)
            courante = mot
    if courante:
        lignes.append(courante)
    return lignes


def css_police(fam, texte):
    """@font-face avec un sous-ensemble WOFF de la police, limité aux caractères utilisés."""
    f = TTFont(io.BytesIO(octets_police(fam)), recalcTimestamp=False)
    opts = subset.Options()
    opts.flavor = "woff"
    opts.layout_features = ["kern"] if fam.startswith("JaCode") else ["kern", "liga", "calt"]
    opts.name_IDs = []
    opts.notdef_outline = True
    s = subset.Subsetter(opts)
    s.populate(text=texte + " ")
    s.subset(f)
    b = io.BytesIO()
    f.flavor = "woff"
    f.save(b)
    donnees = base64.b64encode(b.getvalue()).decode()
    return f"@font-face{{font-family:'{fam}';src:url(data:font/woff;base64,{donnees}) format('woff');}}"


# ---------------------------------------------------------------- thèmes (tokens/web.css)
THEMES = {
    "sombre": dict(fond="#1A1917", surface="#262420", texte="#EAE8DC", doux="#B3ADA3", oro="#D9BC6A",
                   firma="#E6A23E", az="#74AFC0", ac="#F2A04C", bien="#4FD18B", bord="rgb(234 232 220 / .16)",
                   bord_fort="rgb(217 188 106 / .45)", scene=("#3A3631", "#262420", "#1A1917"),
                   komorebi=("116 175 192", .40), brillo="#FFF3CC", halo="255 216 120", trait_brillo=.9,
                   ombre_veta="drop-shadow(0 0 2.5px rgb(217 188 106 / .55))", vidrio="rgb(26 25 23 / .55)",
                   texte_bouton="#1A1917", puce="rgb(234 232 220 / .05)"),
    "clair": dict(fond="#FAF6EC", surface="#FFFFFF", texte="#1F1D1A", doux="#5E584F", oro="#8C6A18",
                  firma="#8C6A18", az="#1F6E80", ac="#A85414", bien="#1B7F4B", bord="rgb(31 29 26 / .14)",
                  bord_fort="rgb(140 106 24 / .45)", scene=("#F3EDDC", "#F8F4E8", "#FBF8F0"),
                  komorebi=("242 160 76", .31), brillo="#D08A00", halo="245 140 30", trait_brillo=1.7,
                  ombre_veta="drop-shadow(0 .6px .5px rgb(70 50 0 / .3))", vidrio="rgb(255 255 255 / .55)",
                  texte_bouton="#FAF6EC", puce="rgb(31 29 26 / .03)"),
}
COURBE = "cubic-bezier(.22,.8,.24,1)"


# ---------------------------------------------------------------- veta (port de tokens/movimiento.js)
def aleatoire(graine):
    s = graine & 0xFFFFFFFF

    def r():
        nonlocal s
        s = (s + 0x6D2B79F5) & 0xFFFFFFFF
        t = s
        t = ((t ^ (t >> 15)) * (t | 1)) & 0xFFFFFFFF
        t ^= (t + (((t ^ (t >> 7)) * (t | 61)) & 0xFFFFFFFF)) & 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296
    return r


def trazar(r, x, y, rumbo, largo, paso_min=2.5, paso_max=8, guide=None):
    """guide = (amplitude) : rappel doux vers la droite de départ, pour que la veta garde ses
    quiebros mais reste dans une bande (ajout au port de movimiento.js)."""
    puntos = [(x, y)]
    x0, y0 = x, y
    nx, ny = -math.sin(rumbo), math.cos(rumbo)
    a, deriva, recorrido = rumbo, 0.0, 0.0
    while recorrido < largo:
        paso = paso_min + r() * (paso_max - paso_min)
        deriva = deriva * 0.86 + (r() - 0.5) * 0.2
        a += deriva + (r() - 0.5) * 0.5
        if r() < 0.06:
            a += (-1 if r() < 0.5 else 1) * (0.45 + r() * 0.7)
        cible = rumbo
        if guide:
            ecart = (x - x0) * nx + (y - y0) * ny
            cible = rumbo - math.atan(ecart / guide) * 0.45
        a += (cible - a) * 0.13
        if guide:
            a = max(rumbo - 1.2, min(rumbo + 1.2, a))
        x += math.cos(a) * paso
        y += math.sin(a) * paso
        recorrido += paso
        puntos.append((x, y))
    return puntos


def ruido(r, cantidad, cada):
    nodos = [r() for _ in range(math.ceil(cantidad / cada) + 2)]

    def f(i):
        q = i / cada
        k = int(q)
        t = q - k
        s = t * t * (3 - 2 * t)
        return nodos[k] * (1 - s) + nodos[k + 1] * s
    return f


def contorno(puntos, ancho):
    iz, de = [], []
    n = len(puntos)
    for i, q in enumerate(puntos):
        a, b = puntos[max(0, i - 1)], puntos[min(n - 1, i + 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        l = math.hypot(dx, dy) or 1
        dx, dy = dx / l, dy / l
        w = ancho(i, n) / 2
        iz.append((q[0] - dy * w, q[1] + dx * w))
        de.append((q[0] + dy * w, q[1] - dx * w))
    return "M" + "L".join(f"{x:.1f} {y:.1f}" for x, y in iz + de[::-1]) + "Z"


def gota(r, x, y, radio):
    pts = []
    for k in range(9):
        a = k / 9 * math.pi * 2
        d = radio * (0.6 + r() * 0.6)
        pts.append((x + math.cos(a) * d * 1.4, y + math.sin(a) * d))
    return "M" + "L".join(f"{a:.1f} {b:.1f}" for a, b in pts) + "Z"


def guider(points, x0, y0, x1, y1, amplitude):
    """Garde la veta dans une bande : l'écart à la droite est borné (tanh) et le tracé est
    étiré pour finir exactement au point d'arrivée. Le détail irrégulier reste le même."""
    L = math.hypot(x1 - x0, y1 - y0) or 1
    ux, uy = (x1 - x0) / L, (y1 - y0) / L
    nx, ny = -uy, ux
    proj, avance = [], -1e9
    for px, py in points:
        t, e = (px - x0) * ux + (py - y0) * uy, (px - x0) * nx + (py - y0) * ny
        if t > avance + .5:  # jamais de retour en arrière (sinon le contour se replie sur lui-même)
            proj.append((t, e))
            avance = t
    tmax = max(t for t, _ in proj) or 1
    return [(x0 + ux * t / tmax * L + nx * amplitude * math.tanh(e / amplitude),
             y0 + uy * t / tmax * L + ny * amplitude * math.tanh(e / amplitude)) for t, e in proj]


def veta(graine, x0, y0, x1, y1, grosor, ramas=None, longueur_rama=260, amplitude=None):
    """Formes (chemins) d'une veta de (x0, y0) à (x1, y1) et les points du tracé principal."""
    r = aleatoire(graine)
    rumbo = math.atan2(y1 - y0, x1 - x0)
    largo = math.hypot(x1 - x0, y1 - y0) * 1.08
    principal = trazar(r, x0, y0, rumbo, largo, guide=amplitude * 2 if amplitude else None)
    if amplitude:
        principal = guider(principal, x0, y0, x1, y1, amplitude * 3)
    n = len(principal)
    onda = ruido(r, n, 8)

    def ancho_en(i, _n=None):
        return grosor * (0.3 + 1.2 * onda(i))
    formes = [contorno(principal, ancho_en)]
    nb = (2 + int(r() * 3)) if ramas is None else ramas
    for k in range(nb):
        i = int(n * (0.08 + r() * 0.8))
        q = principal[i]
        rama = trazar(r, q[0], q[1], rumbo + (-1 if r() < 0.5 else 1) * (0.5 + r() * 0.8),
                      min(largo * (0.07 + r() * 0.2), longueur_rama))
        m, base = len(rama), ancho_en(i) * 0.75
        formes.append(contorno(rama, lambda j, _m, base=base, m=m: base * (1 - j / m) ** 0.7))
        if k % 3 == 0:
            formes.append(gota(r, q[0], q[1], grosor * (1 + r() * 0.8)))
    return formes, principal


def y_sur(points, x):
    """Hauteur du tracé principal à l'abscisse x (pour poser les jalons sur la fissure)."""
    meilleur = min(points, key=lambda p: abs(p[0] - x))
    return meilleur[1]


# ---------------------------------------------------------------- construction d'un SVG
def esc(t):
    return html.escape(t, quote=True)


class Svg:
    def __init__(self, largeur, hauteur, theme, titre):
        self.l, self.h, self.th, self.titre = largeur, hauteur, THEMES[theme], titre
        self.nom_theme = theme
        self.defs, self.corps, self.css = [], [], []
        self.textes = defaultdict(str)
        self.n = 0

    def id(self, prefixe):
        self.n += 1
        return f"{prefixe}{self.n}"

    def texte(self, x, y, txt, fam, taille, couleur, ancre="start", espacement=0, classe="", extra=""):
        self.textes[fam] += txt
        ls = f' letter-spacing="{espacement}"' if espacement else ""
        cl = f' class="{classe}"' if classe else ""
        return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="{fam}, {SECOURS[fam]}" font-size="{taille}" '
                f'fill="{couleur}" text-anchor="{ancre}"{ls}{cl}{extra}>{esc(txt)}</text>')

    def scene(self, rayon=23, komorebi_x=0.92, intensite=1.0):
        """Fond « verre » de la marque : dégradé de scène, lumière komorebi et bord fin."""
        th, ids, idk, idc = self.th, self.id("sc"), self.id("ko"), self.id("cl")
        a, b, c = th["scene"]
        rgb, alpha = th["komorebi"]
        self.defs.append(
            f'<linearGradient id="{ids}" x1=".38" y1="0" x2=".62" y2="1">'
            f'<stop offset="0" stop-color="{a}"/><stop offset=".55" stop-color="{b}"/><stop offset="1" stop-color="{c}"/></linearGradient>'
            f'<radialGradient id="{idk}" cx="{komorebi_x}" cy="0" r=".9" gradientTransform="translate({komorebi_x} 0) scale(1 {self.l / self.h * .55:.3f}) translate(-{komorebi_x} 0)">'
            f'<stop offset="0" stop-color="rgb({rgb} / {alpha * intensite:.2f})"/>'
            f'<stop offset=".45" stop-color="rgb({rgb} / {alpha * intensite * .35:.2f})"/>'
            f'<stop offset="1" stop-color="rgb({rgb} / 0)"/></radialGradient>'
            f'<clipPath id="{idc}"><rect x=".5" y=".5" width="{self.l - 1}" height="{self.h - 1}" rx="{rayon}"/></clipPath>')
        self.corps.append(f'<g clip-path="url(#{idc})"><rect width="{self.l}" height="{self.h}" fill="url(#{ids})"/>'
                          f'<rect width="{self.l}" height="{self.h}" fill="url(#{idk})"/>')
        return idc

    def fin_scene(self, rayon=23):
        self.corps.append("</g>")
        self.corps.append(f'<rect x=".5" y=".5" width="{self.l - 1}" height="{self.h - 1}" rx="{rayon}" fill="none" stroke="{self.th["bord"]}"/>')

    def veta(self, graine, x0, y0, x1, y1, grosor, revele="auto", delai=0.3, duree=1.8, reflet=True,
             periode=8.0, delai_reflet=1.6, opacite=1.0, ramas=None, longueur_rama=260, amplitude=None):
        """Ajoute une veta : elle se dessine à l'arrivée, puis une lueur la parcourt doucement."""
        th = self.th
        formes, pts = veta(graine, x0, y0, x1, y1, grosor, ramas, longueur_rama, amplitude)
        d = "".join(f'<path d="{f}"/>' for f in formes)
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        bx0, by0, bx1, by1 = min(xs) - 60, min(ys) - 60, max(xs) + 60, max(ys) + 60
        vertical = abs(y1 - y0) > abs(x1 - x0)
        idr, idm = self.id("rv"), self.id("rf")
        corps = f'<g fill="{th["oro"]}" style="filter:{th["ombre_veta"]}">{d}</g>'
        if reflet:
            bande = 260
            idg = self.id("gb")
            if vertical:
                grad = f'<linearGradient id="{idg}" x1="0" y1="0" x2="0" y2="1">'
                rect = f'<rect class="{idm}" x="{bx0:.0f}" y="{by0 - bande:.0f}" width="{bx1 - bx0:.0f}" height="{bande}" fill="url(#{idg})"/>'
                course = f"translateY({by1 - by0 + bande:.0f}px)"
            else:
                grad = f'<linearGradient id="{idg}" x1="0" y1="0" x2="1" y2="0">'
                rect = f'<rect class="{idm}" x="{bx0 - bande:.0f}" y="{by0:.0f}" width="{bande}" height="{by1 - by0:.0f}" fill="url(#{idg})"/>'
                course = f"translateX({bx1 - bx0 + bande:.0f}px)"
            self.defs.append(grad + '<stop offset="0" stop-color="#000"/><stop offset=".5" stop-color="#fff"/>'
                             '<stop offset="1" stop-color="#000"/></linearGradient>'
                             f'<mask id="m{idm}" maskUnits="userSpaceOnUse" x="{bx0 - bande:.0f}" y="{by0 - bande:.0f}" '
                             f'width="{bx1 - bx0 + 2 * bande:.0f}" height="{by1 - by0 + 2 * bande:.0f}">{rect}</mask>')
            self.css.append(f"@keyframes k{idm}{{0%{{transform:none}}38%,100%{{transform:{course}}}}}"
                            f".{idm}{{animation:k{idm} {periode}s {COURBE} {delai_reflet}s infinite both}}")
            corps += (f'<g mask="url(#m{idm})" opacity=".6"><g fill="{th["brillo"]}" stroke="{th["brillo"]}" stroke-width="{th["trait_brillo"]}" '
                      f'stroke-linejoin="round" style="filter:drop-shadow(0 0 3px rgb({th["halo"]} / .8)) '
                      f'drop-shadow(0 0 8px rgb({th["halo"]} / .45))">{d}</g></g>')
        if revele:
            sens = ("Y" if vertical else "X") if revele == "auto" else revele
            origine = "top" if sens == "Y" else "left"
            self.defs.append(f'<mask id="m{idr}" maskUnits="userSpaceOnUse" x="{bx0:.0f}" y="{by0:.0f}" width="{bx1 - bx0:.0f}" height="{by1 - by0:.0f}">'
                             f'<rect class="{idr}" x="{bx0:.0f}" y="{by0:.0f}" width="{bx1 - bx0:.0f}" height="{by1 - by0:.0f}" fill="#fff"/></mask>')
            self.css.append(f"@keyframes k{idr}{{from{{transform:scale{sens}(0)}}to{{transform:none}}}}"
                            f".{idr}{{transform-box:fill-box;transform-origin:{origine};animation:k{idr} {duree}s {COURBE} {delai}s both}}")
            corps = f'<g mask="url(#m{idr})">{corps}</g>'
        self.corps.append(f'<g opacity="{opacite}">{corps}</g>')
        return pts

    def rendu(self):
        polices = "".join(css_police(f, t) for f, t in self.textes.items() if t)
        mouvement = "@media (prefers-reduced-motion: reduce){*{animation:none!important}.anime{display:none}.fixe{display:inline!important}}"
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.l}" height="{self.h}" viewBox="0 0 {self.l} {self.h}" '
                f'role="img" aria-label="{esc(self.titre)}"><title>{esc(self.titre)}</title>'
                f'<style>{polices}{"".join(self.css)}{mouvement}</style><defs>{"".join(self.defs)}</defs>'
                f'{"".join(self.corps)}</svg>')


def puce(svg, x, y, txt, fam="JaCode", taille=13, couleur=None, fond=None, bord=None, icone_l=0, hauteur=30):
    """Étiquette arrondie ; renvoie (svg_fragment, largeur)."""
    th = svg.th
    l = mesure(txt, fam, taille) + 28 + icone_l
    frag = (f'<rect x="{x:.1f}" y="{y:.1f}" width="{l:.1f}" height="{hauteur}" rx="{hauteur / 2}" fill="{fond or th["puce"]}" '
            f'stroke="{bord or th["bord"]}"/>' +
            svg.texte(x + 14 + icone_l, y + hauteur / 2 + taille * .36, txt, fam, taille, couleur or th["texte"]))
    return frag, l


# ---------------------------------------------------------------- contenu (CV, voz.md et dépôts : rien d'inventé)
# Chaque bloc a UN rôle : en-tête = qui + accroche ; fiche = ce qui n'est nulle part ailleurs
# + chiffres vivants ; parcours = le passé ; projets = ce que j'ai fait + l'appel (stage).
PHRASE = "I build tools that make life simpler."

PARCOURS = [  # (année, titre, sous-titre) — dates du CV ; le stage 2027 est dans la carte « Your team? »
    ("2017", "CUJAE, Havana", "Telecommunications & Electronics Engineering"),
    ("2018", "Cristallerie de Saint-Louis", "Automation internship · Hermès Group"),
    ("2021", "PRINTJAS, Havana", "Founded my printing & phone repair business"),
    ("2024", "IUT de Bayonne", "BUT Informatique · Computer Science"),
    ("2025", "CROUS, Anglet", "Student referent"),
    ("2026", "Madaré, Toulouse", "Web developer internship · built AuthMIA"),
]

PROJETS = [  # (fichier, étiquette, titre, description, technos, lien, dépôt public ou None)
    ("justsae", "PERSONAL PROJECT · LIVE", "JustSAE",
     "App to organize and track team projects: planning, Gantt charts and mind maps.",
     ["React", "Express", "Prisma", "PostgreSQL"], "https://justsae.cloud", None),
    ("paaxio", "IUT TEAM PROJECT · 7 STUDENTS", "Paaxio",
     "Music platform where new artists can get discovered without competing with big names.",
     ["PHP", "Twig", "JavaScript", "SCSS"], f"https://github.com/{UTILISATEUR}/SAEPaaxio", "SAEPaaxio"),
    ("authmia", "INTERNSHIP · MADARÉ, TOULOUSE", "AuthMIA",
     "Automates internal processes and checks production pages against their mockups.",
     ["Private code"], None, None),
    ("pokebagarre", "IUT LAB · SOFTWARE QUALITY", "PokeBagarre",
     "Java app used for software quality lab work, with unit tests.",
     ["Java", "Gradle"], f"https://github.com/{UTILISATEUR}/PokeBagarre_IUT", "PokeBagarre_IUT"),
    ("lecteurcd", "IUT PROJECT · DESKTOP APP", "CD player",
     "Desktop CD player interface: play, next and previous, shuffle, repeat and volume.",
     ["C++", "Qt"], f"https://github.com/{UTILISATEUR}/SAE-Qt", "SAE-Qt"),
]
LINKEDIN = "https://www.linkedin.com/in/christopher-cecilia-urra-26a78722a/"

FICHE_FIXE = [  # (icône Nerd Font, clé, valeur) — sans ce qui est déjà dans le parcours ou l'en-tête
    ("\U000f0474", "study", "BUT Informatique, 3rd year · IUT de Bayonne"),
    ("\U000f099d", "into", "Cybersecurity · automating everything I can"),
    ("\U000f03d8", "custom", "Everything: my Linux/Windows PC, my own brand"),
    ("\uee32", "music", "Drums & vocals · CROUS student band"),
    ("\U000f05ca", "speaks", "Spanish (native) · French (fluent) · English (B2)"),
]
PALETTE = ["#1A1917", "#F2A04C", "#D9BC6A", "#EAE8DC", "#74AFC0"]  # couleurs de la marque

SECTIONS = {"apropos": ("01", "About me"), "parcours": ("02", "Journey"),
            "projets": ("03", "Projects"), "technos": ("04", "Tech stack")}


def vivant():
    """Données publiques écrites par outils/actualiser.py (vide si le fichier n'existe pas)."""
    f = OUTILS / "donnees/vivant.json"
    return json.loads(f.read_text()) if f.exists() else {}


def il_y_a(date, ref):
    """« today », « 3 days ago », « 2 months ago »… calculé à la date des données (reproductible)."""
    j = (dt.date.fromisoformat(ref) - dt.date.fromisoformat(date)).days
    if j <= 0:
        return "today"
    if j == 1:
        return "yesterday"
    if j < 14:
        return f"{j} days ago"
    if j < 60:
        return f"{j // 7} weeks ago"
    if j < 365:
        return f"{j // 30} months ago"
    return "over a year ago"


def fiche_lignes(v):
    lignes = list(FICHE_FIXE)
    if v.get("depots_publics") is not None:
        lignes.append(("\U000f02a2", "code", f"{v['depots_publics']} public repos · "
                       f"{v['commits_annee']} commits in {v['date'][:4]}"))
    if v.get("langages"):
        lignes.append(("\U000f0169", "langs", " · ".join(f"{n} {p}%" for n, p in v["langages"])))
    return lignes


def en_ce_moment(v):
    """Carte « This week » : ce que je construis + le dépôt public de la semaine + ma musique."""
    lignes = [("\U000f06a9", "Building an AI agent for home automation")]
    if v.get("semaine"):
        depot, n = v["semaine"]
        lignes.append(("\U000f02a2", f"Most commits: {depot} ({n})"))
    elif v.get("dernier"):
        depot, date = v["dernier"]
        lignes.append(("\U000f02a2", f"Last commit: {depot}, {il_y_a(date, v['date'])}"))
    if v.get("musique"):
        m = v["musique"]
        lignes.append(("\U000f04c7", f"On repeat: {m['titre']} · {m['artiste']}"))
    return lignes


TECHNOS = [  # groupes : (titre, [(nom, logo simple-icons)]) — compétences techniques du CV
    ("WEB", [("PHP", "php"), ("Laravel", "laravel"), ("Angular", "angular"), ("React", "react"),
             ("JavaScript", "javascript"), ("HTML", "html5"), ("CSS", "css")]),
    ("LANGUAGES", [("Java", "openjdk"), ("Python", "python"), ("C++", "cplusplus"), ("C", "c"), ("SQL", "")]),
    ("TOOLS & METHODS", [("Docker", "docker"), ("BPMN", "")]),
]


# ---------------------------------------------------------------- pièces
def entete(theme, v):
    """Qui je suis + l'accroche : nom, phrase, une seule étiquette (stage) et la carte « This week »."""
    s = Svg(1000, 300, theme, f"Christopher Cecilia Urra — {PHRASE}")
    th = s.th
    s.scene(komorebi_x=.95)
    s.veta(11, 640, -8, 1012, 150, 3.0, ramas=2, longueur_rama=80, delai=.2, duree=2.0, periode=9,
           delai_reflet=2.4, amplitude=20)
    c = s.corps
    c.append(s.texte(48, 74, "HELLO, I'M", "JaCodeM", 13, th["oro"], espacement=2.6))
    c.append(s.texte(46, 132, "Christopher Cecilia Urra", "JaTitre", 50, th["texte"]))
    c.append(s.texte(48, 176, PHRASE, "JaTexte", 22, th["doux"]))
    # une seule étiquette : le stage (les dates exactes sont dans la carte « Your team? »)
    x, y = 48, 226
    frag, l = puce(s, x, y, "Open to a dev internship · 2027", icone_l=18, bord=th["bord_fort"],
                   fond=f'rgb({th["komorebi"][0]} / .06)' if theme == "sombre" else "rgb(242 160 76 / .08)")
    c.append(frag)
    s.css.append("@keyframes pouls{0%{transform:scale(1);opacity:.75}100%{transform:scale(3);opacity:0}}"
                 ".pouls{transform-box:fill-box;transform-origin:center;animation:pouls 2.4s ease-out infinite}")
    c.append(f'<circle class="pouls" cx="{x + 22}" cy="{y + 15}" r="4" fill="{th["bien"]}"/><circle cx="{x + 22}" cy="{y + 15}" r="4" fill="{th["bien"]}"/>')
    # carte « This week » : mise à jour chaque jour par l'Action
    lignes = en_ce_moment(v)
    cx, cl = 580, 372
    ch = 52 + len(lignes) * 27
    cy = 250 - ch
    c.append(f'<rect x="{cx}" y="{cy}" width="{cl}" height="{ch}" rx="18" fill="{th["vidrio"]}" stroke="{th["bord"]}"/>')
    c.append(s.texte(cx + 22, cy + 30, "THIS WEEK", "JaCodeM", 11.5, th["oro"], espacement=2.2))
    for i, (icone, txt) in enumerate(lignes):
        yy = cy + 60 + i * 27
        txt = couper(txt, "JaTexte", 16, cl - 66)[0] if mesure(txt, "JaTexte", 16) > cl - 66 else txt
        c.append(s.texte(cx + 20, yy + 1, icone, "JaCode", 17, th["az"]))
        c.append(s.texte(cx + 46, yy, txt, "JaTexte", 16, th["texte"]))
    s.fin_scene()
    return s.rendu()


def titre_section(cle, theme):
    """Numéro + titre + filet fin : la veta est réservée à l'en-tête, au parcours et au pied."""
    num, en = SECTIONS[cle]
    s = Svg(1000, 84, theme, en)
    th, c = s.th, s.corps
    c.append(s.texte(2, 52, num, "JaCodeM", 15, th["oro"], espacement=1.5))
    c.append(s.texte(38, 54, en, "JaTitreM", 32, th["texte"]))
    l = mesure(en, "JaTitreM", 32)
    c.append(f'<line x1="{38 + l + 20:.1f}" y1="44" x2="998" y2="44" stroke="{th["bord"]}" stroke-width="1"/>')
    return s.rendu()


def parcours(theme):
    s = Svg(1000, 320, theme, "Journey: " + " · ".join(f"{a} {t} ({st})" for a, t, st in PARCOURS))
    th, c = s.th, s.corps
    pts = s.veta(21, 14, 150, 930, 150, 2.6, ramas=2, longueur_rama=40, duree=2.6, periode=9, delai_reflet=3,
                 amplitude=7)
    # la suite reste ouverte : pointillés + chevron, sans texte (l'appel est dans « Your team? »)
    yf = pts[-1][1]
    c.append(f'<g class="suite"><line x1="940" y1="{yf:.1f}" x2="978" y2="{yf:.1f}" stroke="{th["oro"]}" '
             f'stroke-width="2" stroke-dasharray="3 5" stroke-linecap="round"/>'
             f'<path d="M974 {yf - 7:.1f}L984 {yf:.1f}L974 {yf + 7:.1f}" fill="none" stroke="{th["oro"]}" '
             f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></g>')
    s.css.append(f"@keyframes suite{{from{{opacity:0}}to{{opacity:1}}}}.suite{{animation:suite 1s {COURBE} 2.6s both}}")
    n = len(PARCOURS)
    s.css.append("@keyframes jalon{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}")
    for i, (annee, titre, sous) in enumerate(PARCOURS):
        x = 100 + i * (770 / (n - 1))
        y = y_sur(pts, x)
        coul = th["firma"]
        haut = i % 2 == 0
        idc = s.id("j")
        s.css.append(f".{idc}{{animation:jalon .9s {COURBE} {.5 + i * .3:.2f}s both}}")
        g = [f'<g class="{idc}">']
        ly = y - 30 if haut else y + 30
        g.append(f'<line x1="{x:.1f}" y1="{y + (-12 if haut else 12):.1f}" x2="{x:.1f}" y2="{ly:.1f}" stroke="{th["bord_fort"]}" stroke-dasharray="2 3"/>')
        lignes = couper(sous, "JaTexte", 15, 168)
        if haut:
            base = ly - 12 - (len(lignes) - 1) * 19
            g.append(s.texte(x, base - 46, annee, "JaCodeM", 14, coul, "middle", 1.5))
            g.append(s.texte(x, base - 22, titre, "JaTexteG", 17, th["texte"], "middle"))
            for k, li in enumerate(lignes):
                g.append(s.texte(x, base + k * 19, li, "JaTexte", 15, th["doux"], "middle"))
        else:
            base = ly + 24
            g.append(s.texte(x, base, annee, "JaCodeM", 14, coul, "middle", 1.5))
            g.append(s.texte(x, base + 24, titre, "JaTexteG", 17, th["texte"], "middle"))
            for k, li in enumerate(lignes):
                g.append(s.texte(x, base + 46 + k * 19, li, "JaTexte", 15, th["doux"], "middle"))
        g.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="12" fill="{th["fond"]}" stroke="{coul}" stroke-opacity=".55"/>')
        g.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="6" fill="{coul}" style="filter:drop-shadow(0 0 4px {coul})"/>')
        g.append("</g>")
        c.extend(g)
    return s.rendu()


def carte(projet, theme, v):
    """Carte de projet, sans veta ; « updated … » vient du dépôt public (si il y en a un)."""
    fichier, etiquette, titre, desc, technos, lien, depot = projet
    maj = v.get("pousse", {}).get(depot) if depot else None
    s = Svg(500, 260, theme, f"{titre} — {desc} ({', '.join(technos)})")
    th, c = s.th, s.corps
    s.scene(rayon=20, komorebi_x=1.0, intensite=.8)
    c.append(s.texte(28, 44, etiquette, "JaCodeM", 11.5, th["oro"], espacement=2.2))
    if lien:
        c.append(f'<path transform="translate(458 30)" d="M0 12L12 0M3 0H12V9" fill="none" stroke="{th["doux"]}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>')
    if maj:
        c.append(s.texte(472, 92, f"updated {il_y_a(maj, v['date'])}", "JaCode", 12, th["doux"], "end"))
    c.append(s.texte(27, 92, titre, "JaTitreM", 32, th["texte"]))
    for k, li in enumerate(couper(desc, "JaTexte", 17.5, 440)[:3]):
        c.append(s.texte(28, 126 + k * 24, li, "JaTexte", 17.5, th["doux"]))
    x = 28
    for tech in technos:
        frag, l = puce(s, x, 206, tech, taille=12.5, hauteur=28)
        c.append(frag)
        x += l + 8
    s.fin_scene(rayon=20)
    return s.rendu()


def carte_appel(theme):
    s = Svg(500, 260, theme, "Your team? I'm looking for a development internship from March 1 to June 18, 2027.")
    th, c = s.th, s.corps
    s.scene(rayon=20, komorebi_x=1.0, intensite=1.6)
    c.append(s.texte(28, 44, "NEXT · 2027", "JaCodeM", 11.5, th["ac"], espacement=2.2))
    c.append(s.texte(27, 92, "Your team?", "JaTitreM", 32, th["texte"]))
    lignes = ["I'm looking for a development internship", "from March 1 to June 18, 2027."]
    for k, li in enumerate(lignes):
        c.append(s.texte(28, 126 + k * 24, li, "JaTexte", 17.5, th["doux"]))
    texte_bouton = "Let's talk on LinkedIn  →"
    lb = mesure(texte_bouton, "JaTexteG", 16) + 40
    c.append(f'<rect x="28" y="196" width="{lb:.1f}" height="38" rx="19" fill="{th["ac"]}"/>')
    c.append(s.texte(48, 220.5, texte_bouton, "JaTexteG", 16, th["texte_bouton"]))
    s.fin_scene(rayon=20)
    return s.rendu()


def embleme_colore(couleur, taille):
    """Emblème officiel d'une couleur (PNG avec transparence) recoloré, en data URI."""
    from PIL import Image
    im = Image.open(source(IDENTITE / "logo/aplicado/emblema_un_color_crema.png",
                           "medias/emblema_un_color_crema.png")).convert("RGBA")
    im = im.crop(im.getbbox()).resize((taille, taille), Image.LANCZOS)
    plein = Image.new("RGBA", im.size, couleur)
    plein.putalpha(im.split()[3])
    b = io.BytesIO()
    plein.save(b, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(b.getvalue()).decode()


def fiche(theme, v):
    """« About me » façon fastfetch : mon invite Starship, l'emblème et des lignes clé / valeur."""
    lignes = fiche_lignes(v)
    alt = "christopher@justasync — " + " · ".join(f"{k}: {val}" for _, k, val in lignes)
    s = Svg(1000, 430, theme, alt)
    th, c = s.th, s.corps
    s.scene(komorebi_x=.05, intensite=.8)
    # emblème
    c.append(f'<image x="52" y="88" width="236" height="236" href="{embleme_colore(th["oro"], 708)}"/>')
    # invite Starship : îlot or (Fedora + utilisateur), îlot bleu-vert (dossier), ❯ ambre
    x, y, h = 334, 40, 28
    l1 = mesure(" christopher", "JaCodeM", 13.5) + 46
    l2 = mesure("~", "JaCodeM", 13.5) + 24
    c.append(f'<path d="M{x + h / 2} {y}H{x + l1}V{y + h}H{x + h / 2}A{h / 2} {h / 2} 0 0 1 {x + h / 2} {y}Z" fill="{th["oro"]}"/>')
    c.append(s.texte(x + 11, y + 21, "\uf30a", "JaCode", 19, th["fond"]))
    c.append(s.texte(x + 32, y + 19, " christopher", "JaCodeM", 13.5, th["fond"]))
    c.append(f'<path d="M{x + l1} {y}H{x + l1 + l2 - h / 2}A{h / 2} {h / 2} 0 0 1 {x + l1 + l2 - h / 2} {y + h}H{x + l1}Z" fill="{th["az"]}"/>')
    c.append(s.texte(x + l1 + 11, y + 19, "~", "JaCodeM", 13.5, th["fond"]))
    xp = x + l1 + l2 + 12
    c.append(s.texte(xp, y + 20, "\u276f", "JaCodeM", 17, th["ac"]))
    c.append(s.texte(xp + 22, y + 19.5, "fastfetch", "JaCode", 16, th["texte"]))
    # titre + ligne de tirets, comme le vrai fastfetch
    c.append(s.texte(x, 112, "christopher", "JaCodeM", 22, th["oro"]))
    lt = mesure("christopher", "JaCodeM", 22)
    c.append(s.texte(x + lt, 112, "@", "JaCodeM", 22, th["doux"]))
    c.append(s.texte(x + lt + mesure("@", "JaCodeM", 22), 112, "justasync", "JaCodeM", 22, th["oro"]))
    c.append(s.texte(x, 138, "-" * len("christopher@justasync"), "JaCodeM", 22, th["doux"]))
    # lignes clé / valeur, qui s'affichent l'une après l'autre
    s.css.append("@keyframes ligne{from{opacity:0;transform:translateX(-6px)}to{opacity:1;transform:none}}")
    for i, (icone, cle, valeur) in enumerate(lignes):
        yy = 172 + i * 28.5
        idl = s.id("l")
        s.css.append(f".{idl}{{animation:ligne .5s {COURBE} {.9 + i * .12:.2f}s both}}")
        c.append(f'<g class="{idl}">' + s.texte(x - 1, yy + 2, icone, "JaCode", 21, th["az"])
                 + s.texte(x + 28, yy, cle, "JaCodeM", 15, th["az"])
                 + s.texte(x + 120, yy, valeur, "JaCode", 15, th["texte"]) + "</g>")
    # palette, comme le module « colors » de fastfetch
    idp = s.id("l")
    s.css.append(f".{idp}{{animation:ligne .5s {COURBE} {.9 + len(lignes) * .12:.2f}s both}}")
    pastilles = "".join(f'<circle cx="{x + 9 + k * 26}" cy="400" r="8" fill="{coul}" stroke="{th["bord"]}"/>'
                        for k, coul in enumerate(PALETTE))
    c.append(f'<g class="{idp}">{pastilles}</g>')
    s.fin_scene()
    return s.rendu()


def pied(theme):
    """Une veta qui traverse, puis le nom (l'emblème est dans la fiche)."""
    s = Svg(1000, 150, theme, "Justasync — Christopher Cecilia Urra · Anglet, France")
    th, c = s.th, s.corps
    s.veta(41, 0, 40, 1000, 40, 1.9, ramas=3, longueur_rama=40, duree=2.0, periode=10, delai_reflet=2, amplitude=7)
    c.append(s.texte(500, 104, "Justasync", "JaTitreM", 24, th["texte"], "middle"))
    c.append(s.texte(500, 130, "CHRISTOPHER CECILIA URRA · ANGLET, FRANCE", "JaCodeM", 11.5, th["doux"], "middle", 2.2))
    return s.rendu()


# ---------------------------------------------------------------- README
def lire_voz():
    v = source(IDENTITE / "voz.md", "textes/voz.md").read_text()

    def paragraphe(section):
        bloc = v.split("## " + section)[1]
        return bloc.split("**", 4)[4].strip().split("\n\n")[0].strip()
    en = paragraphe("English").replace("I'm currently looking for an internship from",
                                       "I'm currently looking for a development internship from")
    fr = paragraphe("Français").replace("un stage en entreprise du", "un stage en développement du")
    return en, fr


def ecrire(nom, contenu):
    (ASSETS / nom).write_text(contenu)
    return hashlib.sha1(contenu.encode()).hexdigest()[:8]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--branche", default="main")
    ap.add_argument("--apercu", action="store_true")
    args = ap.parse_args()
    ASSETS.mkdir(exist_ok=True)
    brut = f"https://raw.githubusercontent.com/{DEPOT}/{args.branche}/assets"
    versions = {}

    def pieces(nom, fonction, *a):
        for theme in THEMES:
            versions[f"{nom}-{theme}"] = ecrire(f"{nom}-{theme}.svg", fonction(*a, theme) if a else fonction(theme))

    v = vivant()
    pieces("entete", lambda th: entete(th, v))
    for cle in SECTIONS:
        pieces(f"titre-{cle}", lambda th, cle=cle: titre_section(cle, th))
    pieces("parcours", parcours)
    for p in PROJETS:
        pieces(f"projet-{p[0]}", lambda th, p=p: carte(p, th, v))
    pieces("projet-suivant", carte_appel)
    pieces("fiche", lambda th: fiche(th, v))
    pieces("pied", pied)

    def image(nom, alt, largeur="100%"):
        u = lambda th: f"{brut}/{nom}-{th}.svg?v={versions[f'{nom}-{th}']}"
        return (f'<picture><source media="(prefers-color-scheme: dark)" srcset="{u("sombre")}">'
                f'<source media="(prefers-color-scheme: light)" srcset="{u("clair")}">'
                f'<img src="{u("sombre")}" alt="{esc(alt)}" width="{largeur}"></picture>')

    def titre(cle):
        return f'<p>{image(f"titre-{cle}", SECTIONS[cle][1])}</p>'

    def badge(nom, logo, theme):
        n = nom.replace("-", "--").replace(" ", "%20").replace("+", "%2B")
        if theme == "sombre":
            u = f"https://img.shields.io/badge/{n}-262420?style=for-the-badge"
            u += f"&logo={logo}&logoColor=E6A23E" if logo else ""
        else:
            u = f"https://img.shields.io/badge/{n}-FFFFFF?style=for-the-badge"
            u += f"&logo={logo}&logoColor=8C6A18" if logo else ""
        return u

    en, fr = lire_voz()
    projets = [(p[0], p[5], f"{p[2]} — {p[3]}") for p in PROJETS] + [("suivant", LINKEDIN, "Your team? Development internship 01/03 → 18/06/2027")]
    lignes_projets = []
    for k in range(0, len(projets), 2):
        cellule = []
        for fichier, lien, alt in projets[k:k + 2]:
            img = image(f"projet-{fichier}", alt, "49%")
            cellule.append(f'<a href="{lien}">{img}</a>' if lien else img)
        lignes_projets.append('<p align="center">\n' + "\n".join(cellule) + "\n</p>")

    groupes = []
    for nom_groupe, liste in TECHNOS:
        badges = "\n".join(
            f'<picture><source media="(prefers-color-scheme: dark)" srcset="{badge(n, l, "sombre")}">'
            f'<source media="(prefers-color-scheme: light)" srcset="{badge(n, l, "clair")}">'
            f'<img src="{badge(n, l, "sombre")}" alt="{esc(n)}"></picture>' for n, l in liste)
        groupes.append(f'<p align="center"><sub><b>{esc(nom_groupe)}</b></sub><br>\n{badges}\n</p>')

    social = "\n".join(
        f'<a href="{u}"><picture><source media="(prefers-color-scheme: dark)" srcset="https://img.shields.io/badge/{n}-262420?style=for-the-badge&logo={l}&logoColor=E6A23E">'
        f'<source media="(prefers-color-scheme: light)" srcset="https://img.shields.io/badge/{n}-FFFFFF?style=for-the-badge&logo={l}&logoColor=8C6A18">'
        f'<img src="https://img.shields.io/badge/{n}-262420?style=for-the-badge&logo={l}&logoColor=E6A23E" alt="{n}"></picture></a>'
        for n, l, u in [("LinkedIn", "linkedin", LINKEDIN), ("X", "x", "https://x.com/Justasync01"),
                        ("Instagram", "instagram", "https://www.instagram.com/justasync/")])

    readme = f"""<!-- Généré par outils/generer.py : modifier le script, pas ce fichier. -->
<p align="center"><img src="{brut}/banner.png" alt="Justasync" width="100%"></p>

<p>{image("entete", f"Christopher Cecilia Urra — {PHRASE}")}</p>

{titre("apropos")}

<p>{image("fiche", "christopher@justasync — " + " · ".join(f"{k}: {val}" for _, k, val in fiche_lignes(v)))}</p>

<details>
<summary><b>Read my full story</b></summary>

{en}

</details>

<details>
<summary><b>🇫🇷 Version française</b></summary>

{fr}

</details>

{titre("parcours")}

<p align="center">{image("parcours", "Journey: " + " · ".join(f"{a} {t} ({st})" for a, t, st in PARCOURS))}</p>

{titre("projets")}

{chr(10).join(lignes_projets)}

{titre("technos")}

{chr(10).join(groupes)}

<p>{image("pied", "Justasync — Christopher Cecilia Urra · Anglet, France")}</p>

<p align="center">
{social}
</p>
"""
    (RACINE / "README.md").write_text(readme)

    if args.apercu:
        for theme, fond, texte in (("sombre", "#0d1117", "#e6edf3"), ("clair", "#ffffff", "#1f2328")):
            page = readme.replace(brut + "/", "assets/")
            import re
            page = re.sub(r'<picture><source media="\(prefers-color-scheme: dark\)" srcset="([^"]+)">\s*'
                          r'<source media="\(prefers-color-scheme: light\)" srcset="([^"]+)">\s*<img src="[^"]+"',
                          lambda m: f'<picture><img src="{m.group(1) if theme == "sombre" else m.group(2)}"', page)
            corps = page
            try:
                import subprocess
                corps = subprocess.run(["gh", "api", "markdown", "-f", f"text={page}", "-f", "mode=gfm"],
                                       capture_output=True, text=True, check=True).stdout
            except Exception:
                pass
            (RACINE / f"apercu-{theme}.html").write_text(
                f'<!doctype html><meta charset="utf-8"><title>Aperçu {theme}</title>'
                f'<style>body{{background:{fond};color:{texte};font:16px/1.5 -apple-system,"Segoe UI",sans-serif;margin:0}}'
                f'main{{max-width:854px;margin:24px auto;padding:24px;border:1px solid #3d444d55;border-radius:6px}}'
                f'img{{max-width:100%}}a{{color:#4493f8}}details{{margin:8px 0}}</style><main>{corps}</main>')


if __name__ == "__main__":
    main()

# ruff: noqa: E501
"""Ilustrações vetoriais originais do portal (SVG, independentes de resolução).

Paleta derivada do logotipo NAPI Energia Zero-Carbono: verde-floresta,
verde-folha e amarelo-sol. Nenhuma ilustração reproduz marca de terceiros.
"""

from __future__ import annotations

import base64

FOREST = "#2f4a33"
GREEN = "#455b40"
MOSS = "#5b8a3a"
LEAF = "#73a535"
LIME = "#a8cf5f"
SUN = "#fcc817"
CREAM = "#f6f8f3"
INK = "#1f2a24"


def data_uri(svg: str) -> str:
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def _turbine(x: float, y: float, s: float, rot: float) -> str:
    blade = (
        f'<path d="M0 0 C {4*s} {-10*s}, {5*s} {-34*s}, 0 {-46*s} '
        f'C {-3*s} {-34*s}, {-3*s} {-10*s}, 0 0 Z" fill="#ffffff"/>'
    )
    blades = "".join(
        f'<g transform="rotate({rot + k * 120})">{blade}</g>' for k in range(3)
    )
    return (
        f'<g transform="translate({x} {y})">'
        f'<path d="M{-2.2*s} 0 L{2.2*s} 0 L{1.2*s} {70*s} L{-1.2*s} {70*s} Z" '
        f'fill="#f1f5ef"/>{blades}<circle r="{3.2*s}" fill="#ffffff"/></g>'
    )


def _panel(x: float, y: float, s: float) -> str:
    w, h, skew = 74 * s, 40 * s, 16 * s
    cells = "".join(
        f'<line x1="{skew - skew * t + w * c / 4}" y1="{h * t}" '
        f'x2="{skew - skew * t + w * c / 4}" y2="{h * t}"/>'
        for t in (0,)
        for c in (0,)
    )
    grid = ""
    for c in range(1, 4):
        grid += (
            f'<line x1="{skew + w * c / 4}" y1="0" x2="{w * c / 4}" y2="{h}" '
            'stroke="#9fd0ff" stroke-opacity="0.55" stroke-width="1"/>'
        )
    for r in range(1, 3):
        t = r / 3
        grid += (
            f'<line x1="{skew - skew * t}" y1="{h * t}" '
            f'x2="{skew - skew * t + w}" y2="{h * t}" '
            'stroke="#9fd0ff" stroke-opacity="0.55" stroke-width="1"/>'
        )
    return (
        f'<g transform="translate({x} {y})">{cells}'
        f'<path d="M{skew} 0 L{skew + w} 0 L{w} {h} L0 {h} Z" fill="#17324a"/>'
        f'<path d="M{skew} 0 L{skew + w} 0 L{skew + w - 5 * s} {8 * s} '
        f'L{skew - 3 * s} {8 * s} Z" fill="#2b5b82" fill-opacity="0.75"/>'
        f"{grid}"
        f'<path d="M{w * 0.5} {h} L{w * 0.5} {h + 12 * s}" stroke="#dfe7da" '
        f'stroke-width="{2.4 * s}"/></g>'
    )


def _araucaria(x: float, y: float, s: float, fill: str = "#1f3b27") -> str:
    """Pinheiro-do-paraná estilizado: copa em taça sobre tronco longo."""

    tiers = ""
    for i, (dy, half) in enumerate(((0, 26), (9, 20), (17, 13))):
        tiers += (
            f'<path d="M{-half * s} {(dy - 4) * s} '
            f'Q0 {(dy + 9) * s} {half * s} {(dy - 4) * s} '
            f'Q0 {(dy + 2 - i) * s} {-half * s} {(dy - 4) * s} Z" fill="{fill}"/>'
        )
    return (
        f'<g transform="translate({x} {y})">'
        f'<rect x="{-1.6 * s}" y="{-2 * s}" width="{3.2 * s}" height="{58 * s}" '
        f'fill="{fill}"/>{tiers}</g>'
    )


def hero_landscape() -> str:
    """Paisagem do Paraná com sol, eólicas, painéis solares e lavoura."""

    rows = "".join(
        f'<path d="M{-40 + i * 46} 420 Q{250 + i * 22} 318 {470 + i * 30} 300" '
        f'fill="none" stroke="{LIME}" stroke-opacity="0.34" stroke-width="2"/>'
        for i in range(0, 13)
    )
    rays = "".join(
        f'<line x1="0" y1="-62" x2="0" y2="-80" stroke="{SUN}" stroke-width="5" '
        f'stroke-linecap="round" transform="rotate({k * 30})"/>'
        for k in range(12)
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 760 420"
 role="img" aria-label="Ilustração: paisagem do Paraná com energia solar e eólica">
<defs>
 <radialGradient id="glow" cx="50%" cy="50%" r="50%">
  <stop offset="0" stop-color="{SUN}" stop-opacity="0.55"/>
  <stop offset="1" stop-color="{SUN}" stop-opacity="0"/>
 </radialGradient>
 <linearGradient id="h1" x1="0" y1="0" x2="0" y2="1">
  <stop offset="0" stop-color="#86b84a"/><stop offset="1" stop-color="{MOSS}"/>
 </linearGradient>
 <linearGradient id="h2" x1="0" y1="0" x2="0" y2="1">
  <stop offset="0" stop-color="#5f9137"/><stop offset="1" stop-color="#3f6a2f"/>
 </linearGradient>
 <linearGradient id="h3" x1="0" y1="0" x2="0" y2="1">
  <stop offset="0" stop-color="#3d6a2e"/><stop offset="1" stop-color="#274725"/>
 </linearGradient>
</defs>
<circle cx="560" cy="120" r="150" fill="url(#glow)"/>
<g transform="translate(560 120)"><circle r="46" fill="{SUN}"/>{rays}</g>
<g fill="none" stroke="#ffffff" stroke-opacity="0.16" stroke-width="1.4">
 <path d="M40 70 q60 -30 120 0 t120 0"/><path d="M70 104 q50 -22 100 0 t100 0"/>
 <path d="M300 46 q40 -18 80 0 t80 0"/>
</g>
<path d="M0 262 Q130 196 280 236 T560 214 T760 240 L760 420 L0 420 Z" fill="url(#h1)"/>
{_turbine(214, 150, 1.25, 12)}{_turbine(312, 172, 0.95, 58)}{_turbine(120, 186, 0.8, 96)}
<path d="M0 316 Q170 250 360 292 T760 268 L760 420 L0 420 Z" fill="url(#h2)"/>
{_araucaria(642, 214, 1.15)}{_araucaria(694, 232, 0.85)}{_araucaria(598, 240, 0.7)}
<path d="M430 296 q38 -10 66 6 t60 4" fill="none" stroke="#cfe8f5"
 stroke-opacity="0.75" stroke-width="7" stroke-linecap="round"/>
<path d="M0 372 Q210 300 430 340 T760 320 L760 420 L0 420 Z" fill="url(#h3)"/>
{rows}
{_panel(388, 318, 1.0)}{_panel(478, 326, 1.0)}{_panel(568, 334, 1.0)}
{_panel(430, 362, 1.12)}{_panel(532, 372, 1.12)}
<g transform="translate(96 300)">
 <path d="M0 0 C-16 -22 -16 -44 0 -52 C16 -44 16 -22 0 0 Z" fill="{SUN}"/>
 <circle cy="-33" r="7" fill="{FOREST}"/>
 <ellipse cy="4" rx="13" ry="4" fill="#12261a" fill-opacity="0.35"/>
</g>
</svg>"""


def _frame(inner: str, label: str) -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 220 150" '
        f'role="img" aria-label="{label}">'
        f'<circle cx="150" cy="62" r="74" fill="#ffffff" fill-opacity="0.10"/>'
        f'<circle cx="60" cy="118" r="44" fill="{SUN}" fill-opacity="0.16"/>'
        f"{inner}</svg>"
    )


def spot(kind: str) -> str:
    """Ilustração pequena do cabeçalho de cada página."""

    if kind == "solar":
        inner = (
            f'<circle cx="160" cy="46" r="24" fill="{SUN}"/>'
            + _panel(38, 62, 1.25)
            + _panel(96, 84, 1.05)
        )
        return _frame(inner, "Painéis solares")
    if kind == "grid":
        inner = (
            '<g stroke="#ffffff" stroke-width="3" fill="none" stroke-linecap="round">'
            '<path d="M82 132 L104 30 L126 132"/><path d="M90 96 L118 96"/>'
            '<path d="M95 70 L113 70"/><path d="M78 52 L130 52"/>'
            '<path d="M70 76 L138 76"/><path d="M18 60 Q50 84 78 52"/>'
            '<path d="M130 52 Q170 84 206 58"/></g>'
            f'<path d="M168 76 L150 108 L164 108 L154 138 L186 98 L170 98 L180 76 Z" '
            f'fill="{SUN}"/>'
        )
        return _frame(inner, "Rede de transmissão")
    if kind == "agro":
        stalks = ""
        for x, h in ((70, 78), (104, 96), (138, 82), (170, 66)):
            grains = "".join(
                f'<ellipse cx="{x + (9 if k % 2 else -9)}" cy="{136 - h + 10 + k * 9}" '
                f'rx="8" ry="4.5" fill="{SUN}" '
                f'transform="rotate({35 if k % 2 else -35} '
                f'{x + (9 if k % 2 else -9)} {136 - h + 10 + k * 9})"/>'
                for k in range(5)
            )
            stalks += (
                f'<path d="M{x} 138 L{x} {136 - h}" stroke="#ffffff" '
                f'stroke-width="3" stroke-linecap="round"/>{grains}'
            )
        return _frame(stalks, "Lavoura")
    if kind == "forest":
        inner = (
            _araucaria(84, 44, 1.35, "#ffffff")
            + _araucaria(140, 62, 1.05, LIME)
            + _araucaria(186, 78, 0.8, "#ffffff")
            + f'<path d="M20 136 Q110 112 206 136" fill="none" stroke="{LIME}" '
            'stroke-width="3" stroke-linecap="round"/>'
        )
        return _frame(inner, "Araucárias")
    if kind == "satellite":
        inner = (
            '<ellipse cx="110" cy="80" rx="92" ry="34" fill="none" stroke="#ffffff" '
            'stroke-opacity="0.45" stroke-width="2" stroke-dasharray="5 6" '
            'transform="rotate(-18 110 80)"/>'
            f'<circle cx="92" cy="92" r="30" fill="{LEAF}"/>'
            f'<path d="M70 86 q14 -16 30 -6 t22 14 q-12 14 -28 8 t-24 -16 Z" '
            f'fill="{FOREST}" fill-opacity="0.55"/>'
            '<g transform="translate(168 44) rotate(28)">'
            '<rect x="-9" y="-9" width="18" height="18" rx="3" fill="#ffffff"/>'
            '<rect x="-38" y="-6" width="24" height="12" fill="#17324a"/>'
            '<rect x="14" y="-6" width="24" height="12" fill="#17324a"/>'
            f'<path d="M0 9 L0 20" stroke="{SUN}" stroke-width="3"/>'
            f'<circle cy="23" r="4" fill="{SUN}"/></g>'
        )
        return _frame(inner, "Satélite de observação")
    if kind == "tools":
        keys = "".join(
            f'<rect x="{78 + c * 22}" y="{72 + r * 18}" width="16" height="12" rx="3" '
            f'fill="{SUN if (r, c) == (2, 2) else "#ffffff"}" '
            f'fill-opacity="{1 if (r, c) == (2, 2) else 0.85}"/>'
            for r in range(3)
            for c in range(3)
        )
        inner = (
            '<rect x="66" y="22" width="88" height="112" rx="12" fill="#17324a"/>'
            f'<rect x="78" y="34" width="64" height="26" rx="5" fill="{LIME}"/>{keys}'
        )
        return _frame(inner, "Calculadora")
    if kind == "docs":
        inner = (
            '<rect x="60" y="20" width="84" height="110" rx="8" fill="#ffffff"/>'
            + "".join(
                f'<rect x="74" y="{40 + i * 16}" width="{56 - (i % 3) * 12}" '
                f'height="6" rx="3" fill="{GREEN}" fill-opacity="0.45"/>'
                for i in range(5)
            )
            + f'<circle cx="150" cy="98" r="24" fill="none" stroke="{SUN}" '
            'stroke-width="7"/>'
            f'<path d="M167 116 L190 140" stroke="{SUN}" stroke-width="9" '
            'stroke-linecap="round"/>'
        )
        return _frame(inner, "Documento e lupa")
    # padrão: território
    inner = (
        '<g fill="none" stroke="#ffffff" stroke-opacity="0.55" stroke-width="2">'
        '<path d="M22 112 Q70 70 118 100 T206 84"/>'
        '<path d="M22 132 Q74 96 122 122 T206 108"/>'
        '<path d="M40 86 Q84 52 128 76 T200 58"/></g>'
        f'<path d="M110 118 C78 76 78 36 110 22 C142 36 142 76 110 118 Z" '
        f'fill="{SUN}"/><circle cx="110" cy="60" r="14" fill="{FOREST}"/>'
    )
    return _frame(inner, "Marcador no mapa")

"""Estilo público do NDVI. Aplica-se só à visualização.

A escala é fixa. O GeoTIFF científico não é regravado e o nodata permanece
transparente. Amarelo e verde separam valores baixos e altos da escala; a
legenda não classifica saúde nem produtividade.
"""

from __future__ import annotations

from typing import Any

STYLE_ID = "ndvi-yellow-green-v1"
DISPLAY_MIN = 0.0
DISPLAY_MAX = 0.8
NODATA_VALUE = -9999.0

# A inspeção no QGIS usou uma rampa com vermelho abaixo de zero para leitura
# técnica. O PNG público fica em amarelo → verde, no intervalo em que o mapa
# aprovado separa campos e vegetação, sem alterar o valor armazenado.
STOPS: tuple[tuple[float, str, str], ...] = (
    (0.0, "#F4E04D", "0,0"),
    (0.2, "#C5D63D", "0,2"),
    (0.4, "#7CB342", "0,4"),
    (0.6, "#2E7D32", "0,6"),
    (0.8, "#1B5E20", "0,8"),
)

PHYSICAL_MIN = -1.0
PHYSICAL_MAX = 1.0
OUTSIDE_PHYSICAL_HEX = "#7A7A7A"

RENDER_STRATEGY = (
    "ler o GeoTIFF em modo somente leitura",
    "nodata -9999 fica transparente antes de qualquer cor",
    "NDVI abaixo de -1 ou acima de 1 fica cinza neutro",
    "NDVI de -1 até 0 recebe o amarelo inicial",
    "NDVI de 0,8 até 1 recebe o verde final",
    "entre 0,0 e 0,8 a rampa é linear",
    "gravar PNG apenas numa etapa posterior, fora do GeoTIFF",
    "repetir as mesmas regras no MapLibre",
)


def ndvi_style() -> dict[str, Any]:
    """Contrato reproduzível da rampa amarelo → verde."""

    return {
        "id": STYLE_ID,
        "legend_title": "NDVI",
        "resolution_label": "10 m",
        "display_min": DISPLAY_MIN,
        "display_max": DISPLAY_MAX,
        "interpolation": "linear",
        "nodata_value": NODATA_VALUE,
        "nodata_display": "transparent",
        "source_values_modified": False,
        "below_display_min": {
            "from": PHYSICAL_MIN,
            "until": DISPLAY_MIN,
            "display": "endpoint_yellow",
            "hex": STOPS[0][1],
        },
        "above_display_max": {
            "from": DISPLAY_MAX,
            "until": PHYSICAL_MAX,
            "display": "endpoint_green",
            "hex": STOPS[-1][1],
            "denser_vegetation": False,
        },
        "outside_physical_interval": {
            "minimum": PHYSICAL_MIN,
            "maximum": PHYSICAL_MAX,
            "display": "neutral",
            "hex": OUTSIDE_PHYSICAL_HEX,
            "denser_vegetation": False,
            "source_values_modified": False,
        },
        "stops": [
            {"value": value, "hex": color, "label": label}
            for value, color, label in STOPS
        ],
        "render": list(RENDER_STRATEGY),
        "legend_note_pt": (
            "Escala fixa de visualização, de 0,0 a 0,8. "
            "Abaixo de 0,0 e até -1, a cor é o amarelo inicial. "
            "Acima de 0,8 e até 1, a cor é o verde final, sem indicar "
            "vegetação mais densa. Abaixo de -1 ou acima de 1, a cor é "
            "cinza neutro. Pixels sem dado ficam transparentes."
        ),
    }

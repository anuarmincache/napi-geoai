"""Mapa offline na grade do PNG. Não há rotação nem mapa-base externo."""

from __future__ import annotations

import base64
import html
import json
import re
from typing import Any

_PAGE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta http-equiv="Content-Security-Policy"
      content="default-src 'none'; img-src data:; style-src 'unsafe-inline';
               script-src 'unsafe-inline'">
<style>
  html, body { margin: 0; height: 100%; background: #e8eef5;
    color: #0b2545; font-family: "Segoe UI", sans-serif; }
  .wrap { display: grid; grid-template-columns: minmax(0, 1fr) 280px;
    height: 100%; }
  .stage { display: flex; flex-direction: column; min-width: 0; min-height: 0; }
  canvas { flex: 1; width: 100%; min-height: 0; background: #d5ddd4;
    cursor: grab; touch-action: none; }
  #readout { min-height: 2.2rem; padding: 0.35rem 0.7rem;
    font-size: 0.78rem; color: #334155; }
  aside { padding: 0.75rem 0.85rem; background: #fff;
    border-left: 1px solid #d5deea; overflow: auto; }
  h2 { margin: 0; font-size: 0.95rem; }
  .meta { margin: 0.2rem 0 0.55rem; color: #475569; font-size: 0.75rem; }
  .bar { height: 16px; border-radius: 4px; margin: 0.15rem 0 0.55rem; }
  .item { display: grid; grid-template-columns: 16px minmax(0, 1fr);
    gap: 0.4rem; margin: 0 0 0.45rem; }
  .chip { width: 16px; height: 16px; border-radius: 3px; margin-top: 1px; }
  .clear { background:
    linear-gradient(45deg, #d9e2ec 25%, transparent 25%, transparent 75%,
    #d9e2ec 75%),
    linear-gradient(45deg, #d9e2ec 25%, #fff 25%, #fff 75%, #d9e2ec 75%);
    background-size: 8px 8px; background-position: 0 0, 4px 4px;
    border: 1px solid #cbd5e1; }
  .name { font-size: 0.75rem; font-weight: 700; line-height: 1.2; }
  .desc { font-size: 0.72rem; line-height: 1.25; color: #334155; }
  .caveat { margin: 0.35rem 0 0; color: #64748b; font-size: 0.68rem; }
  button { margin: 0 0.35rem 0 0; border: 1px solid #c5d0de;
    background: #fff; color: #0b2545; border-radius: 6px;
    padding: 0.28rem 0.7rem; font: 600 0.78rem "Segoe UI", sans-serif;
    cursor: pointer; }
  .tools { padding: 0.45rem 0.7rem 0.35rem; }
  @media (max-width: 860px) {
    .wrap { grid-template-columns: 1fr; }
    aside { border-left: 0; border-top: 1px solid #d5deea; }
  }
</style>
</head>
<body>
<div class="wrap">
  <div class="stage">
    <div class="tools">
      <button id="zoom-in" type="button">Ampliar</button>
      <button id="zoom-out" type="button">Reduzir</button>
      <button id="fit" type="button">Município inteiro</button>
    </div>
    <canvas id="map" width="1100" height="820"></canvas>
    <div id="readout">Passe o cursor sobre o mapa.</div>
  </div>
  <aside id="legend"></aside>
</div>
<script id="spec" type="application/json">__SPEC__</script>
<script>
const spec = JSON.parse(document.getElementById("spec").textContent);
const canvas = document.getElementById("map");
const ctx = canvas.getContext("2d");
const view = { scale: 1, x: 0, y: 0 };
const image = new Image();
image.onload = fit;
image.src = spec.image;

function fit() {
  view.scale = Math.min(canvas.width / spec.width, canvas.height / spec.height);
  view.x = (canvas.width - spec.width * view.scale) / 2;
  view.y = (canvas.height - spec.height * view.scale) / 2;
  draw();
}

function draw() {
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = "#e4ece4";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.setTransform(view.scale, 0, 0, view.scale, view.x, view.y);
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(image, 0, 0);
}

function zoomAt(next, anchorX, anchorY) {
  const scale = Math.min(32, Math.max(view.scale * 0.25, next));
  const imageX = (anchorX - view.x) / view.scale;
  const imageY = (anchorY - view.y) / view.scale;
  view.scale = scale;
  view.x = anchorX - imageX * scale;
  view.y = anchorY - imageY * scale;
  draw();
}

function canvasPoint(event) {
  const rect = canvas.getBoundingClientRect();
  return [
    (event.clientX - rect.left) * (canvas.width / rect.width),
    (event.clientY - rect.top) * (canvas.height / rect.height)
  ];
}

canvas.addEventListener("wheel", function (event) {
  event.preventDefault();
  const point = canvasPoint(event);
  const factor = event.deltaY < 0 ? 1.2 : 1 / 1.2;
  zoomAt(view.scale * factor, point[0], point[1]);
}, { passive: false });

let drag = null;
canvas.addEventListener("pointerdown", function (event) {
  drag = { x: event.clientX, y: event.clientY, vx: view.x, vy: view.y };
  canvas.setPointerCapture(event.pointerId);
});
canvas.addEventListener("pointermove", function (event) {
  const point = canvasPoint(event);
  const col = Math.floor((point[0] - view.x) / view.scale);
  const row = Math.floor((point[1] - view.y) / view.scale);
  const readout = document.getElementById("readout");
  if (col < 0 || row < 0 || col >= spec.width || row >= spec.height) {
    readout.textContent = "Fora da grade. A linha 0 do mapa é o norte.";
  } else {
    const gt = spec.geotransform;
    const x = gt[0] + (col + 0.5) * gt[1] + (row + 0.5) * gt[2];
    const y = gt[3] + (col + 0.5) * gt[4] + (row + 0.5) * gt[5];
    readout.textContent = "Linha " + row + ", coluna " + col
      + " · X " + x.toFixed(1) + " m · Y " + y.toFixed(1)
      + " m · EPSG:" + spec.epsg + " · linha 0 = norte";
  }
  if (!drag) return;
  const rect = canvas.getBoundingClientRect();
  view.x = drag.vx + (event.clientX - drag.x) * (canvas.width / rect.width);
  view.y = drag.vy + (event.clientY - drag.y) * (canvas.height / rect.height);
  draw();
});
canvas.addEventListener("pointerup", function () { drag = null; });
document.getElementById("zoom-in").onclick = function () {
  zoomAt(view.scale * 1.2, canvas.width / 2, canvas.height / 2);
};
document.getElementById("zoom-out").onclick = function () {
  zoomAt(view.scale / 1.2, canvas.width / 2, canvas.height / 2);
};
document.getElementById("fit").onclick = fit;

const aside = document.getElementById("legend");
aside.innerHTML = spec.legend;
</script>
</body>
</html>
"""


def _color(value: str) -> str:
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
        raise ValueError("cor_invalida")
    return value


_STOP_GUIDE = {
    0.0: (
        "0,0 · NDVI muito baixo",
        "Amarelo: pouca vegetação, solo exposto ou superfícies não vegetadas.",
    ),
    0.2: (
        "0,2 · NDVI baixo",
        "Amarelo-esverdeado: vegetação esparsa ou cobertura vegetal reduzida.",
    ),
    0.4: (
        "0,4 · NDVI intermediário",
        "Verde-claro: presença moderada de vegetação.",
    ),
    0.6: (
        "0,6 · NDVI elevado",
        "Verde: maior resposta espectral associada à vegetação.",
    ),
    0.8: (
        "0,8 · NDVI muito elevado",
        "Verde-escuro: resposta espectral muito elevada da vegetação.",
    ),
}


def _legend_item(color: str, title: str, description: str, chip_class: str = "") -> str:
    css = f"background:{color}" if not chip_class else ""
    return (
        "<div class='item'>"
        f"<span class='chip {chip_class}' style='{css}'></span>"
        "<div>"
        f"<div class='name'>{html.escape(title)}</div>"
        f"<div class='desc'>{html.escape(description)}</div>"
        "</div></div>"
    )


def _legend_html(spec: dict[str, Any]) -> str:
    stops = spec["stops"]
    gradient = ", ".join(_color(item["hex"]) for item in stops)
    rows = []
    for item in stops:
        guide = _STOP_GUIDE.get(round(float(item["value"]), 1))
        title, description = guide or (html.escape(item["label"]), "")
        if guide is None:
            title = str(item["label"])
        rows.append(_legend_item(_color(item["hex"]), title, description))
    body = "".join(rows)
    gray = _color(spec["gray"])
    return (
        f"<h2>{html.escape(spec['title'])}</h2>"
        f"<p class='meta'>{html.escape(spec['place'])}"
        f" · {html.escape(spec['date_label'])}"
        f" · {html.escape(spec['resolution'])}</p>"
        f"<div class='bar' style='background:linear-gradient(90deg,{gradient})'></div>"
        f"{body}"
        + _legend_item(
            gray,
            "Cinza · valor anômalo",
            "Fora de [-1, 1]. Não representa vegetação.",
        )
        + _legend_item(
            "",
            "Transparente · sem dado",
            "Ausência de observação válida, como nuvem ou falha.",
            "clear",
        )
        + "<p class='caveat'>De -1 até abaixo de 0, permanece o amarelo inicial. "
        "De 0,8 até 1, permanece o verde final. "
        "Leitura indicativa: não classifica o tipo de cobertura do solo.</p>"
    )


def build_map_html(png: bytes, spec: dict[str, Any]) -> str:
    """Monta o visualizador. A escala horizontal e vertical permanece positiva."""

    transform = spec["geotransform"]
    if transform[1] <= 0 or transform[5] >= 0 or transform[2] != 0 or transform[4] != 0:
        raise ValueError("orientacao_recusada")
    payload = {
        "image": "data:image/png;base64,"
        + base64.standard_b64encode(png).decode("ascii"),
        "width": spec["width"],
        "height": spec["height"],
        "geotransform": [float(value) for value in transform],
        "epsg": spec["epsg"],
        "legend": _legend_html(spec),
    }
    encoded = json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c")
    page = _PAGE.replace("__SPEC__", encoded)
    if "https://" in _PAGE or "http://" in _PAGE:
        raise RuntimeError("mapa_com_rede")
    return page

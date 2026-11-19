"""Lê o catálogo e só libera o mapa se os manifestos locais conferem."""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from geoai.catalog.entry import DOWNLOAD_FORMATS, download_menu, file_states
from geoai.catalog.integrity import product_availability, verify_integrity
from geoai.preview.ndvi_png import LEGEND_NAME, PREVIEW_NAME, STYLE_ID

SCIENCE_MANIFEST = "ndvi_local_manifest.json"
PNG_MANIFEST = "ndvi_png_manifest.json"
SCIENCE_SCHEMA = "napi-ndvi-local-manifest-1"
PNG_SCHEMA = "napi-ndvi-png-preview-1"

REASON_PT = {
    "configuracao_ausente": "Os diretórios locais não foram configurados.",
    "diretorio_ausente": "Um diretório configurado não existe.",
    "manifesto_cientifico_ausente": "O manifesto científico local não foi encontrado.",
    "manifesto_png_ausente": "O manifesto dos PNG não foi encontrado.",
    "manifesto_cientifico_divergente": "O manifesto científico diverge do catálogo.",
    "manifesto_png_divergente": "O manifesto dos PNG diverge do catálogo.",
    "grade_divergente": "A grade do PNG não é a grade do catálogo.",
    "orientacao_divergente": "A orientação norte-sul não foi confirmada.",
    "estilo_divergente": "O estilo do PNG não é o ndvi-yellow-green-v1.",
    "contagem_divergente": "As contagens do manifesto local divergem do catálogo.",
    "publicacao_inesperada": "Um manifesto local indica publicação.",
    "png_nao_validado": "O PNG do mapa não passou na conferência.",
    "cog_nao_validado": "O GeoTIFF científico não passou na conferência.",
    "catalogo_incompleto": "O catálogo público está incompleto.",
    "configuracao_incompleta": "A configuração local está incompleta.",
    "configuracao_invalida": "A configuração local é inválida.",
}

LOCAL_LABELS = {
    "png": "PNG colorido",
    "png_legend": "PNG com legenda",
    "geotiff": "GeoTIFF científico",
    "json": "JSON de metadados",
    "csv": "CSV",
}


@dataclass(frozen=True)
class FileView:
    key: str
    label: str
    exists: bool
    validated: bool
    published: bool
    public_download: bool
    filename: str | None
    sha256: str | None
    nbytes: int | None
    reason: str | None


@dataclass(frozen=True)
class ListedDate:
    acquisition_id: str
    image_date: str
    loaded: bool


@dataclass(frozen=True)
class MapSpec:
    png: bytes
    width: int
    height: int
    geotransform: tuple[float, ...]
    epsg: str
    stops: tuple[dict[str, str], ...]
    gray: str
    note: str
    title: str
    place: str
    date_label: str
    acquisition: str
    resolution: str


@dataclass(frozen=True)
class ProductView:
    ibge: str
    name: str
    uf: str
    product_type: str
    acquisition_id: str
    image_date: str
    date_label: str
    entry: dict[str, Any]
    dates: tuple[ListedDate, ...]
    catalog_files: dict[str, FileView]
    local_files: dict[str, FileView]
    download_paths: dict[str, Path]
    map_spec: MapSpec | None
    block_reasons: tuple[str, ...]
    warnings: tuple[str, ...]
    numbers_confirmed: bool

    @property
    def map_ready(self) -> bool:
        return self.map_spec is not None


@dataclass(frozen=True)
class ViewerIndex:
    products: tuple[ProductView, ...]
    errors: tuple[str, ...]


def _file_view(key: str, record: dict[str, Any], label: str | None = None) -> FileView:
    return FileView(
        key,
        label or LOCAL_LABELS[key],
        bool(record["exists"]),
        bool(record["validated"]),
        bool(record["published"]),
        bool(record["public_download"]),
        record.get("filename"),
        record.get("sha256"),
        record.get("bytes"),
        record.get("reason"),
    )


def _missing(key: str, reason: str) -> FileView:
    return FileView(
        key, LOCAL_LABELS[key], False, False, False, False, None, None, None, reason
    )


def _date_label(image_date: str) -> str:
    year, month, day = image_date.split("-")
    return f"{day}/{month}/{year}"


def _north_up(transform: list[float]) -> bool:
    return (
        len(transform) == 6
        and float(transform[1]) > 0
        and float(transform[5]) < 0
        and float(transform[2]) == 0
        and float(transform[4]) == 0
    )


def _same(left: Any, right: Any) -> bool:
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(
            _same(item, other) for item, other in zip(left, right, strict=True)
        )
    if isinstance(left, float | int) and isinstance(right, float | int):
        return float(left) == float(right)
    return left == right


def _stops(items: list[dict[str, Any]]) -> tuple[tuple[float, str], ...]:
    return tuple((float(item["value"]), str(item["hex"]).upper()) for item in items)


def _png_header(path: Path) -> tuple[int, int, int]:
    with path.open("rb") as handle:
        blob = handle.read(26)
    if len(blob) < 26 or blob[:8] != b"\x89PNG\r\n\x1a\n" or blob[12:16] != b"IHDR":
        raise ValueError("png_invalido")
    width, height = struct.unpack(">II", blob[16:24])
    return int(width), int(height), int(blob[25])


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("manifesto_invalido")
    return payload


def catalog_file_views(entry: dict[str, Any]) -> dict[str, FileView]:
    states = file_states(entry)
    views = {}
    for name in DOWNLOAD_FORMATS:
        item = entry["downloads"][name]
        record = {
            "exists": states[name]["exists"],
            "validated": states[name]["validated"],
            "published": states[name]["published"],
            "public_download": bool(item["public_download"]),
            "filename": item.get("filename"),
            "sha256": item.get("sha256"),
            "bytes": item.get("bytes"),
            "reason": item.get("reason"),
        }
        views[name] = _file_view(name, record, LOCAL_LABELS[name])
    return views


def scientific_panel(product: ProductView) -> dict[str, Any]:
    """Números exibidos, copiados do catálogo já verificado."""

    entry = product.entry
    outside = entry["quality"]["outside_unit_interval"]
    return {
        "satellite": entry["satellite"],
        "source": "Sentinel-2",
        "acquisition_id": entry["acquisition_id"],
        "image_date": entry["image_date"],
        "spatial_resolution_m": entry["spatial_resolution_m"],
        "crs": entry["crs"],
        "n_aoi": entry["counts"]["n_aoi"],
        "n_valid": entry["counts"]["n_valid"],
        "valid_pixel_fraction": entry["valid_pixel_fraction"],
        "anomalous": outside["count"],
        "quality_status": entry["quality"]["status"],
        "note_pt": entry["quality"]["note_pt"],
        "algorithm": entry["algorithm"]["version"],
        "rule": entry["algorithm"]["rule"],
        "pixel_equation": entry["counts"]["pixel_equation"],
        "gdal_version": entry["algorithm"]["gdal_version"],
        "peak_rss_status": entry["algorithm"]["peak_rss_status"],
        "numbers_confirmed": product.numbers_confirmed,
        "ndvi_published": entry["ndvi_published"],
        "public_downloads": download_menu(entry),
    }


def _dates(entry: dict[str, Any]) -> tuple[ListedDate, ...]:
    current = entry["acquisition_id"]
    return tuple(
        ListedDate(
            item["acquisition_id"],
            item["image_date"],
            item["acquisition_id"] == current,
        )
        for item in entry["acquisitions"]
    )


def _empty_local(reason: str) -> dict[str, FileView]:
    return {key: _missing(key, reason) for key in LOCAL_LABELS}


def _base_product(
    entry: dict[str, Any],
    *,
    catalog_path: Path,
    block_reasons: list[str],
    warnings: list[str],
    local_files: dict[str, FileView],
    download_paths: dict[str, Path],
    map_spec: MapSpec | None,
    numbers_confirmed: bool,
) -> ProductView:
    municipality = entry["municipality"]
    image_date = entry["image_date"]
    return ProductView(
        ibge=municipality["ibge"],
        name=municipality["name"],
        uf=municipality["uf"],
        product_type=entry["product_type"],
        acquisition_id=entry["acquisition_id"],
        image_date=image_date,
        date_label=_date_label(image_date),
        entry=entry,
        dates=_dates(entry),
        catalog_files=catalog_file_views(entry),
        local_files=local_files,
        download_paths=download_paths,
        map_spec=map_spec,
        block_reasons=tuple(block_reasons),
        warnings=tuple(warnings),
        numbers_confirmed=numbers_confirmed,
    )


def _json_view(catalog_path: Path) -> FileView:
    return FileView(
        "json",
        LOCAL_LABELS["json"],
        True,
        True,
        False,
        False,
        catalog_path.name,
        None,
        catalog_path.stat().st_size,
        None,
    )


def _unavailable(entry: dict[str, Any], catalog_path: Path, reason: str) -> ProductView:
    local_files = _empty_local(reason)
    local_files["json"] = _json_view(catalog_path)
    return _base_product(
        entry,
        catalog_path=catalog_path,
        block_reasons=[reason],
        warnings=[],
        local_files=local_files,
        download_paths={"json": catalog_path},
        map_spec=None,
        numbers_confirmed=False,
    )


def build_product(
    entry: dict[str, Any],
    *,
    catalog_path: Path,
    science_dir: Path | None,
    preview_dir: Path | None,
) -> ProductView:
    """Confere um município. Divergência bloqueia o mapa e não reescreve nada."""

    if science_dir is None or preview_dir is None:
        return _unavailable(entry, catalog_path, "configuracao_ausente")
    if not science_dir.is_dir() or not preview_dir.is_dir():
        return _unavailable(entry, catalog_path, "diretorio_ausente")

    reasons: list[str] = []
    warnings: list[str] = []
    science = _read_json(science_dir / SCIENCE_MANIFEST)
    preview = _read_json(preview_dir / PNG_MANIFEST)
    if science is None:
        reasons.append("manifesto_cientifico_ausente")
    if preview is None:
        reasons.append("manifesto_png_ausente")
    if science is None or preview is None:
        return _unavailable(entry, catalog_path, reasons[0])

    if (
        science.get("schema") != SCIENCE_SCHEMA
        or science.get("ndvi_published") is not False
    ):
        reasons.append("manifesto_cientifico_divergente")
    if (
        preview.get("schema") != PNG_SCHEMA
        or preview.get("ndvi_published") is not False
    ):
        reasons.append("manifesto_png_divergente")
    if (
        preview.get("public_download") is not False
        or preview.get("source_values_modified") is not False
    ):
        reasons.append("publicacao_inesperada")
    if entry.get("ndvi_published") is not False:
        reasons.append("publicacao_inesperada")

    grid = entry["grid"]
    cog = science["products"]["ndvi"]
    catalog_cog = entry["downloads"]["geotiff"]
    source = preview["source_cog"]
    if not _same(
        [science["rows"], science["cols"], science["geotransform"], science["epsg"]],
        [
            grid["rows"],
            grid["cols"],
            grid["geotransform"],
            int(entry["crs"].split(":")[1]),
        ],
    ):
        reasons.append("manifesto_cientifico_divergente")
    if not _same(
        [
            science["counts"]["n_aoi"],
            science["counts"]["n_valid"],
            science["counts"]["pixel_equation"],
        ],
        [
            entry["counts"]["n_aoi"],
            entry["counts"]["n_valid"],
            entry["counts"]["pixel_equation"],
        ],
    ):
        reasons.append("contagem_divergente")
    if science.get("algorithm") != entry["algorithm"]["version"]:
        reasons.append("manifesto_cientifico_divergente")
    if not _same(
        [cog["sha256"], cog["bytes"], cog["name"]],
        [catalog_cog["sha256"], catalog_cog["bytes"], catalog_cog["filename"]],
    ):
        reasons.append("cog_nao_validado")
    if not _same(
        [
            source["sha256"],
            source["bytes"],
            source["width"],
            source["height"],
            source["geotransform"],
            str(source["epsg"]),
            preview["acquisition_id"],
            preview["image_date"],
            preview["municipality"]["ibge"],
            preview.get("style_id"),
            preview.get("orientation"),
            preview["counts"]["anomalous"],
        ],
        [
            catalog_cog["sha256"],
            catalog_cog["bytes"],
            grid["cols"],
            grid["rows"],
            grid["geotransform"],
            entry["crs"].split(":")[1],
            entry["acquisition_id"],
            entry["image_date"],
            entry["municipality"]["ibge"],
            STYLE_ID,
            "norte_na_primeira_linha",
            entry["quality"]["outside_unit_interval"]["count"],
        ],
    ):
        reasons.append("manifesto_png_divergente")
    if _stops(preview["stops"]) != _stops(entry["style"]["stops"]):
        reasons.append("estilo_divergente")
    if not _north_up(grid["geotransform"]):
        reasons.append("orientacao_divergente")

    cog_path = science_dir / cog["name"]
    cog_record = product_availability(
        cog_path, expected_sha256=cog["sha256"], expected_bytes=cog["bytes"]
    )
    provenance = science["products"]["provenance"]
    provenance_record = product_availability(
        science_dir / provenance["name"],
        expected_sha256=provenance["sha256"],
        expected_bytes=provenance["bytes"],
    )
    if not provenance_record["validated"]:
        warnings.append("proveniencia_nao_validada")

    preview_image = preview["images"][PREVIEW_NAME]
    legend_image = preview["images"][LEGEND_NAME]
    preview_path = preview_dir / PREVIEW_NAME
    legend_path = preview_dir / LEGEND_NAME
    preview_record = product_availability(
        preview_path,
        expected_sha256=preview_image["sha256"],
        expected_bytes=preview_image["bytes"],
    )
    legend_record = product_availability(
        legend_path,
        expected_sha256=legend_image["sha256"],
        expected_bytes=legend_image["bytes"],
    )
    if not cog_record["validated"]:
        reasons.append("cog_nao_validado")
    if not preview_record["validated"]:
        reasons.append("png_nao_validado")

    header_ok = False
    if preview_record["validated"]:
        width, height, color_type = _png_header(preview_path)
        header_ok = width == grid["cols"] and height == grid["rows"] and color_type == 6
        if not header_ok:
            reasons.append("grade_divergente")
    if legend_record["validated"]:
        legend_width, legend_height, legend_type = _png_header(legend_path)
        if (
            legend_width != legend_image["width"]
            or legend_height != legend_image["height"]
            or legend_type != 6
            or legend_height != grid["rows"]
            or legend_width <= grid["cols"]
        ):
            warnings.append("legenda_divergente")
            legend_record = {
                **legend_record,
                "validated": False,
                "reason": "grade_divergente",
            }

    local_files = {
        "png": _file_view("png", preview_record),
        "png_legend": _file_view("png_legend", legend_record),
        "geotiff": _file_view("geotiff", cog_record),
        "json": _json_view(catalog_path),
        "csv": _missing("csv", "nao_gerado"),
    }
    unique_reasons = tuple(dict.fromkeys(reasons))
    numbers_confirmed = not any(
        code in unique_reasons
        for code in (
            "manifesto_cientifico_divergente",
            "contagem_divergente",
            "cog_nao_validado",
            "publicacao_inesperada",
        )
    )
    paths: dict[str, Path] = {"json": catalog_path}
    if not unique_reasons and local_files["png"].validated and header_ok:
        paths["png"] = preview_path
    if not unique_reasons and local_files["png_legend"].validated:
        paths["png_legend"] = legend_path
    if numbers_confirmed and local_files["geotiff"].validated:
        paths["geotiff"] = cog_path

    map_spec = None
    if not unique_reasons and header_ok:
        style = entry["style"]
        map_spec = MapSpec(
            png=preview_path.read_bytes(),
            width=grid["cols"],
            height=grid["rows"],
            geotransform=tuple(float(value) for value in grid["geotransform"]),
            epsg=entry["crs"].split(":")[1],
            stops=tuple(style["stops"]),
            gray=style["outside_physical_interval"]["hex"],
            note=style["legend_note_pt"],
            title=style["legend_title"],
            place=f"{entry['municipality']['name']} — {entry['municipality']['uf']}",
            date_label=_date_label(entry["image_date"]),
            acquisition=entry["acquisition_id"],
            resolution=f"{entry['spatial_resolution_m']:g} m",
        )
    return _base_product(
        entry,
        catalog_path=catalog_path,
        block_reasons=list(unique_reasons),
        warnings=warnings,
        local_files=local_files,
        download_paths=paths,
        map_spec=map_spec,
        numbers_confirmed=numbers_confirmed,
    )


def load_index(
    repo: Path, science_dir: Path | None, preview_dir: Path | None
) -> ViewerIndex:
    """Carrega cada JSON público que tenha sidecar de integridade válido."""

    public = repo / "catalog" / "public"
    products: list[ProductView] = []
    errors: list[str] = []
    for path in sorted(public.glob("*.json")):
        record_path = repo / "catalog" / "integrity" / path.name
        try:
            if not record_path.is_file():
                raise RuntimeError("catalogo_publico_divergente")
            record = json.loads(record_path.read_text(encoding="utf-8"))
            verify_integrity(path, record)
            entry = json.loads(path.read_text(encoding="utf-8"))
        except (
            OSError,
            json.JSONDecodeError,
            RuntimeError,
            KeyError,
            TypeError,
            ValueError,
        ):
            errors.append(path.name)
            continue
        try:
            products.append(
                build_product(
                    entry,
                    catalog_path=path,
                    science_dir=science_dir,
                    preview_dir=preview_dir,
                )
            )
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            products.append(
                _unavailable(entry, path, "manifesto_cientifico_divergente")
            )
    return ViewerIndex(tuple(products), tuple(errors))

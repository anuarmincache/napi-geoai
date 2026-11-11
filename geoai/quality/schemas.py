"""Schemas piloto reutilizando datasets já existentes (sem dados fictícios)."""

from __future__ import annotations

from geoai.quality.contracts import (
    DatasetSchema,
    FieldConstraint,
    GeometryKind,
)


def territorial_pr_uf_schema() -> DatasetSchema:
    """Schema do limite UF Paraná já ingerido (IBGE malhas + PostGIS).

    Campos alinhados a ``geoai.territorial_units`` / pipeline MVP 02–04.
    Não publica geometrias nem inventa atributos.

    Usado com ``validate_tabular_record``: valida atributos do registro,
    **não** a geometria PostGIS nem o GeoJSON em disco.
    """

    return DatasetSchema(
        dataset_id="geoai.territorial_units.pr_uf",
        source_id="ibge.malhas_municipais.pr_uf_2025",
        title="Unidade territorial — Paraná (UF)",
        geometry_kind=GeometryKind.MULTIPOLYGON,
        crs="EPSG:4674",
        spatial_resolution="unidade federativa (UF)",
        temporal_periodicity="edição da malha IBGE",
        edition="2025",
        license_note=(
            "IBGE — uso conforme termos do provedor; atribuição obrigatória."
        ),
        update_policy="revalidar quando houver nova edição da malha IBGE",
        fields=(
            FieldConstraint(
                name="ibge_code",
                required=True,
                nullable=False,
                notes="Código IBGE da UF (ex.: 41 para Paraná)",
            ),
            FieldConstraint(
                name="name",
                required=True,
                nullable=False,
            ),
            FieldConstraint(
                name="mesh_edition",
                required=True,
                nullable=False,
            ),
            FieldConstraint(
                name="srid",
                required=True,
                nullable=False,
                min_value=4674,
                max_value=4674,
                notes="SRID canônico do projeto (SIRGAS 2000)",
            ),
        ),
        integrity_notes=(
            "Geometria MultiPolygon válida; GiST em geom; "
            "UK (ibge_code, mesh_edition)."
        ),
        content_sha256_required=True,
    )

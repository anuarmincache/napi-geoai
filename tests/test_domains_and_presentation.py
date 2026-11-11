"""Testes do registro de domínios e metadados didáticos (MVP 06)."""

from __future__ import annotations

import pytest
from geoai.domains import (
    DomainId,
    get_domain,
    get_indicator,
    list_domains,
    list_indicators,
)
from geoai.presentation import (
    AudienceLevel,
    didactic_metadata_for_territorial_pr,
    list_expansion_requirements,
)


def test_all_four_domains_registered() -> None:
    domains = list_domains()
    assert {d.domain_id for d in domains} == {
        DomainId.ENERGY,
        DomainId.ENVIRONMENT,
        DomainId.AGRICULTURE,
        DomainId.ENTREPRENEURSHIP,
    }
    energy = get_domain("energy")
    assert "geoai.connectors" in energy.shared_infrastructure
    assert energy.out_of_scope_now


def test_indicator_catalog_decision_oriented() -> None:
    ind = get_indicator("energy.territorial_boundary.pr_uf")
    assert ind.domain_id == DomainId.ENERGY
    assert ind.question_pt
    assert ind.audience_pt
    assert "ibge.malhas_municipais.pr_uf_2025" in ind.source_ids
    assert ind.limitations_pt
    energy_only = list_indicators(domain_id=DomainId.ENERGY)
    assert all(i.domain_id == DomainId.ENERGY for i in energy_only)


def test_unknown_domain_and_indicator() -> None:
    with pytest.raises(ValueError):
        get_domain("finance")
    with pytest.raises(KeyError):
        get_indicator("missing.indicator")


def test_didactic_metadata_three_levels() -> None:
    meta = didactic_metadata_for_territorial_pr()
    assert meta.resource_id == "geoai.territorial_units.pr_uf"
    basic = meta.copy_for(AudienceLevel.BASIC)
    intermediate = meta.copy_for(AudienceLevel.INTERMEDIATE)
    tech = meta.copy_for(AudienceLevel.TECHNICAL)
    assert "Não diz onde instalar energia solar" in basic.description
    assert "reprojetada" not in intermediate.description.lower()
    assert "4674" in intermediate.description
    assert "4674" in tech.description
    assert meta.uncertainty_pt
    assert meta.update_policy
    assert meta.updated_at is None or "T" in meta.updated_at
    if meta.updated_at is not None:
        # proveniência real do artefato PR → ISO-8601
        assert meta.updated_at.startswith("20")
    assert meta.interactive_map_requirements
    payload = meta.to_dict()
    assert len(payload["copies"]) == 3
    assert "update_policy" in payload


def test_expansion_requirements_documented() -> None:
    reqs = list_expansion_requirements()
    ids = {r.requirement_id for r in reqs}
    assert "ux.three_levels" in ids
    assert "ux.interactive_map" in ids
    assert "quality.persist_reports" in ids
    persist = next(r for r in reqs if r.requirement_id == "quality.persist_reports")
    assert persist.blocked_by

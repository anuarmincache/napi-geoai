# Arquitetura modular — MVP 06

Complementa `docs/ARQUITETURA.md` e `docs/adr/0001-domain-modules.md`.
Reutiliza integralmente MVPs 01–05. **Não** introduz site, ML nem novos conectores.

## Inventário (estado herdado)

```text
geoai/
  connectors/     # SourceSpec, Provenance, IBGE, ANEEL, http_fetch (MVP 03)
  boundaries/     # limite PR + validação geométrica (MVP 02)
  db/             # PostGIS, migrate, import, doctor, backup (MVP 04–05)
geoai/quality/        # NEW — schema + QualityReport (MVP 06)
geoai/domains/        # NEW — registro temático + IndicatorSpec
geoai/presentation/   # NEW — DidacticMetadata + ExpansionRequirement
```

Banco: PostgreSQL 16 + PostGIS 3.4, DB `napi_geoai`, porta **5433**,
migração `0001_init_postgis` intacta. Ops: `scripts/db_ops.py`.

## Diagrama lógico

```text
                    Fontes oficiais (catálogo MVP 03)
                              |
                         connectors/
                              |
              +---------------+----------------+
              |               |                |
         provenance      quality/          boundaries/
         (MVP 03)     validate_record      (MVP 02)
              |               |                |
              +-------+-------+--------+-------+
                      |                |
                   geoai.db         domains/
                   (PostGIS)     IndicatorSpec
                      |                |
                      +--------+-------+
                               |
                        presentation/
                     DidacticMetadata
                     (contrato UX 3 níveis)
                               |
                     [futuro: API / site]
```

## Fronteiras

| Camada | Responsabilidade | Não faz |
|---|---|---|
| Infra compartilhada | catálogo, download, proveniência, PostGIS, qualidade | UI, ML |
| Domínio | pergunta/público/fontes/limites do indicador | ingestão própria |
| Apresentação (contrato) | textos didáticos, legenda, acessibilidade, mapa | renderizar site |

## Contratos de qualidade

Ver `geoai.quality`: `DatasetSchema`, `FieldConstraint`, `QualityReport`
(`valid` / `warning` / `rejected`). Grandezas energéticas
(`EnergyQuantityKind`) **não** misturam potência instalada, geração e
irradiação no mesmo schema.

Piloto: `territorial_pr_uf_schema()` — dataset PR já existente
(`ibge.malhas_municipais.pr_uf_2025` / `geoai.territorial_units`).

## Metadados didáticos (UX futura)

`DidacticMetadata` exige cópias `basic` / `intermediate` / `technical`,
unidade, legenda, atribuição, data, incerteza, link metodológico (opcional)
e requisitos de mapa/acessibilidade. Exemplo:
`didactic_metadata_for_territorial_pr()`.

## Expansão (sem stack extra)

`ExpansionRequirement` lista o que falta (persistir QualityReport, mapa,
UX 3 níveis). Alternativas pagas (Supabase remoto, Kafka, Airflow) —
**documentadas como não contratadas**; local/gratuito primeiro.

## Plano de evolução (próximos incrementos — issues separadas)

1. UX didática sobre o limite PR (Issue #9 / site).
2. Conectores catalogados (INPE, MapBiomas, ONS) quando houver escopo.
3. Aptidão solar com pesos/restrições explícitos (Marco 2 do ROADMAP).
4. Migração aditiva de qualidade **somente** se ops exigir histórico.

## Nomenclatura

- Código/API: inglês (`DomainId.ENERGY`, `QualityStatus.VALID`).
- Documentação de produto e textos didáticos: pt-BR.

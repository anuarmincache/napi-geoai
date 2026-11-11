# ADR 0001 — Organização modular por domínio

**Status:** aceito (MVP 06)  
**Data:** 2026-11-11  
**Issue:** #19

## Contexto

Os MVPs 01–05 entregaram pacote Python, conectores/contratos, limite PR,
PostGIS local (:5433) e operações (doctor/backup/restore). O NAPI GeoAI
precisa crescer para energia, meio ambiente, agricultura e empreendedorismo
sustentável **sem** duplicar banco, conectores ou infraestrutura.

## Alternativas consideradas

| Opção | Prós | Contras |
|---|---|---|
| **A. Monólito flat** (tudo em `geoai/connectors`) | Simples no curto prazo | Domínios se misturam; difícil UX temática |
| **B. Microsserviços / DBs por domínio** | Isolamento forte | Prematuro; custo ops; quebra MVP 05 |
| **C. Pacotes de domínio + infraestrutura compartilhada** | Extensível; reusa PostGIS/contratos; UI futura independente | Exige disciplina de fronteiras |

## Decisão

Adotar **C**:

- Infra compartilhada: `connectors`, `quality`, `db`, `boundaries`, `presentation` (contratos).
- Domínios: registro em `geoai.domains` (specs + indicadores-contrato), sem serviços separados.
- Um único PostgreSQL/`napi_geoai`; migrações **aditivas** só quando justificadas.
- Código em inglês; docs de produto em pt-BR.

## Consequências

- Novos conectores continuam em `geoai.connectors` + catálogo MVP 03.
- Qualidade e metadados didáticos são testáveis sem UI/ML.
- Persistência de `QualityReport` fica como requisito de expansão (não migrar agora).
- Site, ML, ingestão massiva e novos conectores permanecem fora do MVP 06.

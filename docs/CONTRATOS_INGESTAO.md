# Contratos de ingestão — MVP 03

Define interfaces Python e políticas comuns aos conectores. Implementação:
`geoai/connectors/contracts.py`, `http_fetch.py`, `errors.py`.

## Metadados da fonte (`SourceSpec`)

| Campo | Obrigatório | Descrição |
|---|---|---|
| `source_id` | sim | identificador estável |
| `organization` / `product` | sim | órgão e produto |
| `access_mode` | sim | mecanismo real de acesso |
| `entry_url` / `download_url` | sim / se houver | índice e URL direta |
| `formats` / `license_note` | sim | formatos e restrições de reuso |
| `official_update_cadence` | sim | periodicidade **declarada pelo provedor** |
| `verification_policy` | sim | política **nossa** de revalidação (TTL/ETag) |
| `catalogued_at` | sim | data da consulta ao portal (ISO date) |
| `spatial_coverage` / `crs_or_coords` / `granularity` | sim | cobertura espacial |
| `auth_required` / `status` | sim | credencial e maturidade |

`update_cadence` permanece como alias de `official_update_cadence` (compatibilidade).

## Proveniência (`ProvenanceRecord`)

| Campo | Significado |
|---|---|
| `retrieved_at` | quando o **conteúdo** foi baixado/substituído |
| `last_checked_at` | quando a **origem** foi consultada (pode ser 304) |
| `content_sha256` | integridade local — **não** implica atualidade |
| `cache_hit` / `not_modified` | reuso local / HTTP 304 |

## Cache e atualidade

1. Reuso sem rede: `url` + `source_id` + SHA-256 ok **e** TTL de `last_checked_at`.
2. Fora do TTL: conditional GET (`If-None-Match` / `If-Modified-Since`).
3. `force_refresh=True`: GET completo.
4. Integridade local ≠ dado atualizado na origem.

## Download atômico

1. Escreve em `destino.partial`.
2. Valida tamanho e `content_validator` (se houver).
3. `os.replace` só após sucesso.
4. Em falha, remove o partial e preserva o destino anterior.

## Retries

- Retenta: erros de transporte, 408, 429, 5xx (respeita `Retry-After` quando numérico).
- Não retenta: demais 4xx (ex.: 404).

## Validação ANEEL SIGA

Antes de promover ao cache: encoding, delimitador `;`, colunas obrigatórias completas.
`limit=0` → lista vazia (após validar cabeçalho); `limit<0` → erro.

## Prototypes

| Fonte | Módulo |
|---|---|
| IBGE malha UF | `geoai.connectors.ibge` (API MVP 02 preservada) |
| ANEEL SIGA CSV | `geoai.connectors.aneel` |

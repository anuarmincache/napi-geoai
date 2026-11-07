# Contratos de ingestão — MVP 03

Define interfaces Python e políticas comuns aos conectores. Implementação de
referência: `geoai/connectors/contracts.py`, `http_fetch.py`, `errors.py`.

## Metadados obrigatórios da fonte (`SourceSpec`)

| Campo | Obrigatório | Descrição |
|---|---|---|
| `source_id` | sim | identificador estável (`org.produto.recorte`) |
| `organization` | sim | órgão |
| `product` | sim | nome do produto |
| `access_mode` | sim | `http_file`, `ckan_resource`, `gee_asset`, etc. |
| `entry_url` | sim | página/índice oficial |
| `download_url` | se aplicável | URL direta verificável |
| `formats` | sim | formatos reais |
| `license_note` | sim | licença / restrições |
| `update_cadence` | sim | periodicidade declarada |
| `spatial_coverage` | sim | cobertura |
| `crs_or_coords` | sim | CRS ou convenção de coordenadas |
| `granularity` | sim | unidade mínima |
| `auth_required` | sim | se exige credencial |
| `status` | sim | `catalogued` / `prototype` / `stable` / `blocked` |

## Proveniência de artefato (`ProvenanceRecord`)

Campos mínimos após qualquer download:

`source_id`, `url`, `retrieved_at` (UTC ISO-8601), `content_sha256`,
`content_length`, `license_note`.

Recomendados: `http_etag`, `http_last_modified`, `local_path`, `extra`.

## Validação

1. HTTP 2xx e arquivo não vazio.
2. SHA-256 calculado e persistido.
3. Validação específica do conector (ex.: cabeçalho SIGA; CRS IBGE no pipeline de limites).
4. Falhas → `ValidationConnectorError` (não silenciar).

## Cache

- Arquivo local + sidecar `*.cache.json` com proveniência.
- Reuso se SHA-256 do arquivo = metadado em cache.
- Cache é local (`data/raw/`); **não** versionar artefatos grandes.

## Retries e erros de rede

- `download_http_file(..., retries=3, retry_backoff_s=0.5)`.
- Erros HTTP/transporte → `NetworkConnectorError` após esgotar tentativas.
- Testes usam `httpx.MockTransport` (offline).

## Resultado (`IngestResult`)

`source_id`, `local_path`, `provenance`, opcionalmente `records_parsed` e `warnings`.

## Prototypes priorizados

| Fonte | Módulo | Testes |
|---|---|---|
| IBGE malha UF | `geoai.connectors.ibge` | mock HTTP + integração opcional |
| ANEEL SIGA CSV | `geoai.connectors.aneel` | fixture `aneel_siga_mini.csv` + mock HTTP |

Fontes apenas catalogadas (INPE/LABREN, MapBiomas, ONS, MMGD) não possuem
download automático neste MVP.

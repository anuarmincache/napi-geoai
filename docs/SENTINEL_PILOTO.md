# Piloto Sentinel-2 — Maringá (Issue #42)

O catálogo atual seleciona uma passagem e não publica NDVI.

O diagnóstico de Pinhais está em `docs/evidence/sentinel/exploracao_pinhais_2026-11-14.json`, com `pilot_aoi: false`.

## AOI

Feição `CD_MUN=4115200` em `data/raw/ibge/PR_Municipios_2025.zip`.

- Nome: Maringá
- `AREA_KM2` oficial: 487,912
- CRS: EPSG:4674
- Geometria válida
- BBox: `[-52.1000868, -23.5583336, -51.8358064999999, -23.2539786999999]`
- Cobertura métrica: EPSG:31982

## Regra temporal

Um grupo é o mesmo satélite, o mesmo instante de aquisição gravado no identificador SAFE e a mesma órbita relativa. Tiles dessa passagem podem entrar no mosaico. Outra data, outro satélite ou outra órbita fica em outro grupo. Não há composição multitemporal.

O limiar geométrico é 99,9% da área municipal. A união anterior de uma cena por tile, misturando datas, não é mais o critério de aceite.

## Consulta

`--as-of 2026-11-14T17:56:56Z`. Consulta registrada em 2026-11-14T18:14:53Z. `stac_search_seconds` = 9,197 s, incluindo a busca de 7 dias e a interseção métrica. A sonda HTTPS fica fora desse relógio.

A janela de 7 dias devolveu 12 cenas em 3 passagens. Duas cobrem o município. A de 30 dias não foi consultada.

| Passagem | Órbita | Cobertura conjunta | Cobre 99,9% |
| --- | --- | ---: | --- |
| S2B 2026-11-12T13:31:49Z | R081 | 1,0 | sim |
| S2C 2026-11-10T13:38:31Z | R124 | 0,650595 | não |
| S2A 2026-11-09T13:32:31Z | R081 | 1,0 | sim |

A passagem escolhida é a mais recente que cobre: `S2B_20261112T133149_R081`.

## Mosaico candidato

Tiles da mesma passagem S2B, processamento `20261112T184116`:

| Tile | Cobertura | Nuvem do item | Entra no mosaico |
| --- | ---: | ---: | --- |
| 22KCV | 0,899308 | 29,81% | sim |
| 22KDV | 0,548641 | 9,29% | sim |
| 22KCU | 0,090778 | 44,88% | não |
| 22KDU | 0,003316 | 9,91% | não |

O menor conjunto é 22KCV + 22KDV. União 1,0, lacuna 0,0 e sobreposição 0,447949, na sexta casa decimal. `mosaic_required` é verdadeiro. `dates_combined` é falso. A nuvem do item não mede pixel válido na AOI. `valid_pixel_fraction` permanece nulo. `selection_status` é `mosaic_candidate`.

## Acesso

O método preparado é OIDC/OData, fora do Streamlit, em `geoai/sentinel/cdse_auth.py`.

- Token endpoint: `https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token`
- Cliente público documentado: `cdse-public`
- Variáveis locais, se existirem: `CDSE_USERNAME` e `CDSE_PASSWORD`, ou `CDSE_ACCESS_TOKEN`
- Host do asset: `download.dataspace.copernicus.eu`

Nenhuma dessas variáveis está definida. A requisição autorizada não foi enviada. `authorized_attempted` é falso e `bytes_read` é 0. Nenhum segredo foi gravado.

Para o B04 da tile 22KCV desta passagem, um GET sem `Authorization` e com `Range: bytes=0-0` respondeu HTTP 401. `WWW-Authenticate` veio vazio. O corpo não foi armazenado. `access_status` é `blocked_auth`.

S3 em `https://eodata.dataspace.copernicus.eu` continua declarado na coleção e não foi usado. O endpoint comercial com `requester_pays` não foi chamado.

## Processamento

`processing_status` é `not_evaluated`. Sem leitura autorizada de B04, B08 e SCL, não houve recorte, alinhamento, reflectância, máscara nem NDVI. `scripts/prepare_sentinel_pilot.py` continua terminando com código 2 e não publica raster, mesmo se três arquivos locais existirem. `ndvi_published` é falso.

## Interface

`app/pages/8_Sentinel_Piloto.py` lê `data/derived/sentinel_maringa_pilot.json`. Mostra a passagem, as tiles, a lacuna, a sobreposição e o bloqueio de acesso. Não baixa cena nem calcula NDVI.

## GDAL

QGIS 3.44.15-Solothurn, GDAL 3.13.3 e PROJ 9.8.1, pelo `python-qgis-ltr.bat`. O pytest do sistema não importa `osgeo`. O warp nearest sintético em `docs/evidence/sentinel/gdal_nearest_synthetic.json` tem `sentinel_scene: false`.

## Reproduzir

```powershell
py -3 scripts/search_sentinel_pilot.py --as-of 2026-11-14T17:56:56Z
```

A credencial, quando existir, fica só no ambiente do processo. Não entra no Git.

## Medições

- Busca STAC e cobertura da janela de 7 dias: 9,197 s
- Bytes de banda gravados: 0
- Bytes lidos na requisição autorizada: 0
- RSS do NDVI: não medido
- Leitura de preview no Streamlit: não medido

## Fora desta entrega

Raster, COG, fração válida por pixel, composição de datas, agendamento, Paraná inteiro, Cloud e Supabase.

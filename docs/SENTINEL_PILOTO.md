# Piloto Sentinel-2 — Maringá (Issue #42)

Esta entrega consulta o STAC oficial para Maringá e não publica NDVI.

O diagnóstico de Pinhais no commit `7a23c37` ficou em `docs/evidence/sentinel/exploracao_pinhais_2026-11-14.json`, com `pilot_aoi: false`. Aqueles números não descrevem Maringá.

## Por que Maringá

A Issue #42, atualizada em 14/11/2026, define Maringá como a AOI oficial do piloto. A feição foi lida de `data/raw/ibge/PR_Municipios_2025.zip`, `CD_MUN=4115200`.

- Nome: Maringá
- `AREA_KM2` oficial: 487,912
- CRS da malha: EPSG:4674
- Geometria válida
- BBox da feição: `[-52.1000868, -23.5583336, -51.8358064999999, -23.2539786999999]`
- CRS da cobertura métrica, pelo centroide: EPSG:31982 (SIRGAS 2000 / UTM 22S)

O GeoJSON simplificado da apresentação não entra no cálculo de cobertura.

## Critérios, definidos antes da escolha da cena

- Coleção `sentinel-2-l2a` em `https://stac.dataspace.copernicus.eu/v1/search`.
- `--as-of 2026-11-14T17:56:56Z`.
- Janela de 7 dias: `2026-11-07T17:56:56Z/2026-11-14T17:56:56Z`.
- Janela de 30 dias, usada porque a de 7 dias não teve tile com cobertura geométrica suficiente: `2026-10-15T17:56:56Z/2026-11-14T17:56:56Z`.
- Uma cena é candidata a NDVI só se o footprint cobre pelo menos 99,9% do polígono oficial. A fração é área no CRS métrico. A geometria STAC entra como EPSG:4326.
- `eo:cloud_cover` do item é triagem. Não mede pixel válido no município e não decide a troca de 7 para 30 dias.
- Aceite de NDVI exige fração de pixels válidos na AOI ≥ 0,70 depois da leitura de B04, B08 e SCL. Isso não foi medido.

## O que a consulta devolveu

Consulta em 2026-11-14T17:59:36Z. O campo `stac_search_seconds` (26,962 s) inclui as duas janelas e a interseção métrica. A sonda HTTPS e o GET da coleção ficam fora desse relógio.

- 7 dias: 12 cenas, 0 com cobertura ≥ 99,9%.
- 30 dias: 57 cenas, 0 com cobertura ≥ 99,9%. A resposta não foi truncada.

Tiles pelo `grid:code` STAC, máxima cobertura de cada uma:

| Tile | Cobertura do polígono | Cenas em 30 dias |
| --- | ---: | ---: |
| MGRS-22KCV | 0,899308 | 15 |
| MGRS-22KDV | 0,548641 | 15 |
| MGRS-22KCU | 0,090780 | 15 |
| MGRS-22KDU | 0,003316 | 12 |

A união de um footprint por tile, no mesmo CRS métrico, deu 1,0 na sexta casa decimal. O município exige mosaico. Nenhum mosaico foi montado. `candidate` permanece nulo. `mosaic_required` é verdadeiro.

## Inspeção de acesso, sem aceitar a cena

A cena de maior cobertura geométrica na janela de 30 dias foi usada só para ler o contrato do asset e fazer uma requisição sem `Authorization`. Ela não cobre Maringá e não está aceita.

`S2A_MSIL2A_20261020T133231_N0513_R081_T22KCV_20261020T195213`

- Aquisição: 2026-10-20T13:32:31.024Z, dentro dos 30 dias e fora dos 7 dias
- Tile: MGRS-22KCV
- Cobertura geométrica: 0,899308
- Nuvem do item: 0,0. Isso é metadado do item, não fração válida na AOI
- B04: EPSG:32722, GSD 10 m, escala 0,0001, offset −0,1, nodata 0
- Tamanho informado do JP2 B04: 49 672 747 bytes
- Bytes gravados: 0
- `accepted`: false
- `valid_pixel_fraction`: nulo

O href canônico é `s3`, bucket `eodata`, com `auth:refs: ["s3"]`. O alternativo HTTPS aponta para `download.dataspace.copernicus.eu`, caminho OData `.../B04_10m.jp2/$value`, com `auth:refs: ["oidc"]`. B08 e SCL declaram os mesmos esquemas. A query string não foi armazenada.

A coleção STAC declara dois esquemas:

- `s3`, plataforma `https://eodata.dataspace.copernicus.eu` (`requester_pays: false`)
- `oidc`, documento `https://identity.dataspace.copernicus.eu/auth/realms/CDSE/.well-known/openid-configuration`
- Emissor: `https://identity.dataspace.copernicus.eu/auth/realms/CDSE`
- Token endpoint: `https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token`

Há também `creodias-s3` em `https://eodata.cloudferro.com`, com `requester_pays: true`. Nenhuma credencial S3 foi carregada.

A requisição foi `GET` com `Range: bytes=0-0`, sem header `Authorization`, ao alternativo HTTPS de B04. Resposta: HTTP 401, `WWW-Authenticate` ausente, `Content-Type: application/json; charset=utf-8`. O corpo não foi gravado. A documentação OData do Copernicus Data Space descreve o download em `download.dataspace.copernicus.eu` com bearer obtido nesse token endpoint. O 401 descreve a requisição anônima ao href HTTPS. A coleção também oferece S3. O status não separa os dois esquemas.

## O que a interface mostra

`app/pages/8_Sentinel_Piloto.py` lê `data/derived/sentinel_maringa_pilot.json`. Com `ndvi_published: false` ela mostra a indisponibilidade, as tiles, a cena de inspeção e o HTTP 401. Não chama STAC, GDAL nem QGIS.

## Preparo

`scripts/prepare_sentinel_pilot.py` termina com código 2. Com os três arquivos locais presentes, o comando ainda não recorta, não alinha SCL, não calcula NDVI e não publica raster. Obter uma credencial não conclui este estágio.

## GDAL neste computador

QGIS 3.44.15-Solothurn, GDAL 3.13.3, PROJ 9.8.1, pelo `python-qgis-ltr.bat`. O pytest do sistema não tem `osgeo`. O warp nearest sintético 20 m → 10 m em EPSG:32722 está em `docs/evidence/sentinel/gdal_nearest_synthetic.json` e marca `sentinel_scene: false`.

## Reproduzir

```powershell
py -3 scripts/search_sentinel_pilot.py --as-of 2026-11-14T17:56:56Z
```

## Medições

- Busca STAC e cobertura métrica: 26,962 s
- Bytes de banda gravados: 0
- RSS do NDVI real: não medido
- Leitura de preview no Streamlit: não medido, porque não há raster
- Warp nearest sintético: 0,047 s, na evidência GDAL já versionada

## Fora desta entrega

Mapa de NDVI, mosaico das quatro tiles, agendamento, Paraná inteiro, Cloud e Supabase.

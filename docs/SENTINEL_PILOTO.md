# Piloto Sentinel-2 — Pinhais (Issue #42)

Esta entrega consulta o STAC oficial e não publica NDVI.

## Por que Pinhais

CD_MUN `4119152`. `AREA_KM2` oficial da malha IBGE 2025: **61,008 km²**, o menor do Paraná nesse atributo. As 399 geometrias passaram em `native:checkvalidity` no QGIS 3.44.15 (relatório `parana_municipios_2025_qgis_report.json`). O município está no fuso UTM 22S. O retângulo oficial, lido do ZIP e não do GeoJSON simplificado, é pequeno o bastante para uma tile Sentinel-2.

CRS da malha: EPSG:4674. A tile candidata declara EPSG:32722.

## Critérios, definidos antes da escolha

- Coleção `sentinel-2-l2a` em `https://stac.dataspace.copernicus.eu/v1/search`.
- Janela de 7 dias (2026-11-07 a 2026-11-14); 30 dias só se a primeira voltar vazia.
- O footprint precisa cobrir pelo menos 99,9% do polígono oficial.
- `eo:cloud_cover` do item é triagem. Não mede pixel válido dentro do município.
- Aceite exige fração de pixels válidos na AOI ≥ 0,70 depois da leitura de B04, B08 e SCL. Isso não foi medido.

## O que a consulta devolveu

Na janela de 7 dias, a cena de cobertura completa com menor nuvem de item é:

`S2C_MSIL2A_20261114T132231_N0513_R038_T22JFS_20261114T150804`

- Aquisição: 2026-11-14T13:22:31Z
- Nuvem do item: 20,69%
- Cobertura do polígono de Pinhais: 1
- Escala e offset declarados no asset B04: 0,0001 e −0,1
- Nodata declarado: 0
- Tamanho informado do JP2 B04: 124 724 203 bytes (não baixado)

O download HTTPS do mesmo asset respondeu **401**. Não há `CDSE_*` no ambiente. Nenhum byte de banda foi gravado. A cena não está aceita.

## O que a interface mostra

`app/pages/8_Sentinel_Piloto.py` lê `data/derived/sentinel_pinhais_pilot.json`. Com `ndvi_published: false` ela explica a indisponibilidade. Não chama STAC, GDAL nem QGIS.

## GDAL neste computador

QGIS 3.44.15-Solothurn, GDAL 3.13.3, PROJ 9.8.1, pelo `python-qgis-ltr.bat`. O pytest do sistema não tem `osgeo`. Um warp nearest de grade sintética 20 m → 10 m, em EPSG:32722, está em `docs/evidence/sentinel/gdal_nearest_synthetic.json`. Essa grade não é Sentinel.

## Reproduzir a consulta

```powershell
py -3 scripts/search_sentinel_pilot.py
```

O preparo das bandas para quando existirem JP2 locais e o Python do QGIS:

```powershell
& "C:\Program Files\QGIS 3.44.15\bin\python-qgis-ltr.bat" scripts/prepare_sentinel_pilot.py --b04 B04.jp2 --b08 B08.jp2 --scl SCL.jp2
```

Sem esses arquivos o comando termina com código 2 e não publica raster.

## Medições nesta máquina

- Consulta STAC: 2,73 s (`stac_search_seconds` no catálogo, 2026-11-14T17:46:42Z).
- Bytes baixados de banda: 0. O JP2 B04 informado tem 124 724 203 bytes e não foi gravado.
- Warp nearest sintético no Python do QGIS: 0,047 s. Pico de RSS do processamento real: não medido, porque as bandas não foram lidas.
- `py -3 -m ruff check .`: passou.
- `py -3 -m pytest -q`: 170 passed, 9 skipped, 28,54 s. O skip do PostGIS continua sem `DATABASE_URL`. O CI não executa QGIS.
- `scripts/prepare_sentinel_pilot.py` sem JP2: código de saída 2, `ndvi_published` falso.

## Fora desta entrega

Mapa de NDVI, agendamento, Paraná inteiro, Cloud e Supabase.

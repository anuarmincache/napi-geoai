# Piloto Sentinel-2 — Maringá (Issue #42)

O catálogo atual seleciona uma passagem e não publica NDVI.

O diagnóstico de Pinhais está em `docs/evidence/sentinel/exploracao_pinhais_2026-11-14.json`, com `pilot_aoi: false`.

## AOI

Feição `CD_MUN=4115200` em `data/raw/ibge/PR_Municipios_2025.zip`.

O GDAL abre esse ZIP por `/vsizip/` e o shapefile interno `PR_Municipios_2025.shp`, com barras normais. O mesmo caminho vale no Windows e no Linux. A leitura no QGIS 3.44.15 / GDAL 3.13.3 está em `docs/evidence/sentinel/ibge_mesh_gdal.json`: CRS igual a EPSG:4674, geometria válida e máscara 64×64 com o ponto interior dentro do município. Essa máscara é só da malha; não é NDVI.

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

O menor conjunto é 22KCV + 22KDV. União 1,0, lacuna 0,0 e sobreposição geométrica 0,447949, na sexta casa decimal. Essa sobreposição é área do footprint, não pixel válido e não entra duas vezes na fração municipal. `mosaic_required` é verdadeiro. `dates_combined` é falso. A nuvem do item não mede pixel válido na AOI. Na seleção, `valid_pixel_fraction` estava nulo e `quality_approved` era falso. A medição posterior da mesma S2B registrou fração 0,7311414776754075. A qualidade ficou aprovada e `ndvi_published` permanece falso.

Se a fração válida dessa passagem, depois da leitura de B04, B08 e SCL, ficar abaixo de 0,70, a reserva continua sendo a passagem `S2A_20261109T133231_R081`. Ela não entra na mesma medição. Exige autorização nova. As duas datas não se misturam.

## Regra de sobreposição

`first_valid_tile_in_declared_order`, em `geoai/sentinel/mosaic_rule.py`.

Na grade comum, cada pixel da AOI conta uma vez. A tile entra só se a SCL não está nas classes inválidas, o DN não é nodata e o NDVI tem denominador utilizável. Se as duas tiles são válidas no mesmo pixel, fica o valor da primeira na ordem declarada (22KCV, depois 22KDV). Não há média. A fração válida é o número de pixels escolhidos dividido pelo número de pixels da AOI. Na medição, 3.086.107 + 479.243 = 3.565.350. Os 2.034.052 pixels de sobreposição já estão nos 3.086.107 da 22KCV e não são subtraídos. O pico de memória dessa execução não foi medido: `peak_rss_mb` permanece nulo. Uma recontagem independente dos pixels não foi executada.

## Pipeline em blocos

A raiz que executa o pipeline é este repositório, `napi-geoai-mvp04`. O checkout `napi-geoai-app` só entra se a sessão definir `NAPI_VALIDATED_B04` com o caminho da B04 já conferida. Sem essa variável, e sem uma B04 válida dentro desta raiz, `download_allowed` fica falso para não baixar uma segunda cópia. O arquivo externo não é copiado nem apagado.

Cada JP2 efetivamente usado, inclusive o reutilizado, precisa ter o `file:size` da sua banda, o SHA3-256 publicado pelo STAC no multihash `1620` e a grade oficial: EPSG:32722, dimensões, resolução e origem. O catálogo não traz outra garantia criptográfica além desse multihash. Se o arquivo diverge, ele permanece no disco e o processamento para. Um JP2 criado na tentativa que falha é removido; um JP2 que já existia não é. Durante a transferência, cada banda só começa se o tamanho oficial couber no restante do teto de 750.000.000 bytes, e o corpo é interrompido antes de gravar além desse tamanho.

`scripts/run_maringa_sentinel.py --dry-run` não baixa JP2 e não publica NDVI. Confere as seis bandas da passagem S2B, tiles 22KCV e 22KDV, e separa o download do arquivo inteiro da leitura recortada. Os seis caminhos HTTPS são o `$value` OData do produto, da tile e da banda, sem query. O teto de transferência é 750.000.000 bytes e o teto de cada JP2 é 150.000.000 bytes. Os tamanhos oficiais do STAC somam 357.870.297 bytes. Se faltar o tamanho ou o endereço de uma banda, o plano não inventa um máximo e recusa a autorização. A memória de um bloco de 256 pixels é 3.342.336 bytes, mais 9.085.500 bytes da máscara da AOI. Manter as matrizes inteiras custaria 545.130.000 bytes e passa do limite de 512 MiB, por isso a medição percorre blocos e descarta cada janela. `download_started` ficou falso.

`--measure-only` calcula a fração válida e não grava COG. A escala 0,0001, o offset −0,1 e o nodata 0 conferem com o L2A de baseline N0513 (quantificação 10000 e offset −1000). A S2A de 09/11 permanece reserva e não é baixada nesta medição. Datas não se misturam. Se a geração ou o catálogo falham, o raster anterior é restaurado. Um JP2 existente ilegível ou divergente do contrato oficial é preservado.

A leitura de janela com GDAL 3.13.3, em raster sintético, está em `docs/evidence/sentinel/gdal_window_synthetic.json`. Durou 0,073 s, leu uma janela 2×2 e manteve `sentinel_scene` e `ndvi_published` falsos. O mosaico sintético anterior, em `docs/evidence/sentinel/gdal_mosaic_synthetic.json`, durou 0,022 s: 24 pixels, 23 válidos, 7 da primeira tile e 16 da segunda. O `PeakWorkingSetSize` daquele processo QGIS foi 62,961 MB e inclui o processo inteiro.

## Acesso

O método preparado é OIDC/OData, fora do Streamlit, em `geoai/sentinel/cdse_auth.py`.

- Token endpoint: `https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token`
- Cliente público documentado: `cdse-public`
- Variáveis locais, se existirem: `CDSE_USERNAME` e `CDSE_PASSWORD`, ou `CDSE_ACCESS_TOKEN`
- Host do asset: `download.dataspace.copernicus.eu`

O catálogo gravado na busca ainda tem `authorized_attempted` falso. Uma sessão local posterior informou sonda autorizada com HTTP 206, 1024 bytes e `range_honored` verdadeiro. Esse registro da sonda não foi alterado. A medição `--measure-only` da S2B é outro evento: transferiu 308.160.853 bytes, calculou a fração e não escreveu COG. Nenhum segredo foi gravado.

O cliente só aceita HTTPS em `download.dataspace.copernicus.eu`, caminho `/odata/v1/Products(...)/$value`, sem usuário, senha ou query na URL. Redirecionamento para outro host é recusado antes de reenviar `Authorization`. A sonda pede `Range: bytes=0-1023` e lê no máximo 1024 bytes. `range_honored` só fica verdadeiro com HTTP 206, `Content-Range` começando em 0 e terminando no máximo em 1023, tamanho igual aos bytes lidos e, se `Content-Length` vier, igual a esse tamanho. Um objeto menor só vale se o total declarado for exatamente `fim + 1`. HTTP 200 deixa `range_honored` falso, mesmo com corpo curto ou com `Content-Range`.

Para o B04 da tile 22KCV desta passagem, um GET sem `Authorization` e com `Range: bytes=0-0` respondeu HTTP 401. `WWW-Authenticate` veio vazio. O corpo não foi armazenado. `access_status` é `blocked_auth`.

S3 em `https://eodata.dataspace.copernicus.eu` continua declarado na coleção e não foi usado. O endpoint comercial com `requester_pays` não foi chamado.

## Processamento

`processing_status` é `measured`. A fração válida é 0,7311414776754075, acima de 0,70, e `quality_approved` é verdadeiro. `ndvi_published` é falso e não há COG. `scripts/prepare_sentinel_pilot.py` continua terminando com código 2 e não publica raster. A sonda em `access_probe_scene` permanece não autenticada: `downloaded_bytes` 0, HTTP 401 e `authorized_attempted` falso. Esse histórico não foi reescrito. A transferência da medição, 308.160.853 bytes, está em `aoi_measurements`.

## Interface

`app/pages/8_Sentinel_Piloto.py` lê `data/derived/sentinel_maringa_pilot.json`. O arquivo da página fica em `app/pages`, então a raiz do repositório é `parents[2]`. Mostra a passagem, as tiles, a fração, a soma das contribuições, o estado `measured` e a sonda histórica em separado. Não baixa cena nem calcula NDVI.

## GDAL

QGIS 3.44.15-Solothurn, GDAL 3.13.3 e PROJ 9.8.1, pelo `python-qgis-ltr.bat`. O pytest do sistema não importa `osgeo`. O warp nearest sintético em `docs/evidence/sentinel/gdal_nearest_synthetic.json` tem `sentinel_scene: false`.

## Reproduzir

```powershell
py -3 scripts/search_sentinel_pilot.py --as-of 2026-11-14T17:56:56Z
```

A credencial, quando existir, fica só no ambiente do processo. Não entra no Git.

## Medições

- Busca STAC e cobertura da janela de 7 dias: 9,197 s
- Bytes de banda oficiais gravados: 0
- Bytes lidos na requisição autorizada: 0
- Mosaico sintético no Python do QGIS: 0,022 s, 0 bytes gravados no piloto
- RSS de pico desse processo QGIS: 62,961 MB, processo inteiro
- Dry-run sem download: soma oficial dos JP2 357.870.297 bytes; bloco 3.342.336 bytes
- Janela sintética `ReadAsArray` e `WriteArray` no Python do QGIS: 0,020 s
- Fração válida da cena oficial: não medida neste processo
- Leitura de preview no Streamlit: não medido

## Fora desta entrega

Fração válida da S2B, passagem S2A caso a S2B fique abaixo de 0,70, COG do piloto, composição de datas, agendamento, Paraná inteiro, Cloud e Supabase. O comando que mede a AOI é `scripts/run_maringa_sentinel.py`, pelo `python-qgis-ltr.bat`, no processo em que a credencial já existe.

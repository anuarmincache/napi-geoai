# Processamento geoespacial — fundação (Issue #40)

Esta etapa separa a interface do cálculo pesado e registra jobs locais. Não baixa Sentinel-2 e não publica mapa de imagem.

## O que o Streamlit faz

As páginas em `app/` leem JSON e GeoJSON já preparados (`st.cache_resource` em `app/_bootstrap.py`). Não importam QGIS, não chamam Processing e não executam `geoai.processing.execute_job` durante a navegação.

PyQGIS continua apenas nos workers já existentes, fora da interface:

- `scripts/_qgis_mun_worker.py`
- `scripts/_qgis_siga_join_worker.py`

Esses workers não foram reescritos.

## Jobs desta fundação

Executor: `py -3 scripts/run_geo_job.py` (não é chamado pelo Streamlit).

Tipos permitidos:

| Tipo | Entrada | Saída |
| --- | --- | --- |
| `vector_bbox_metrics` | GeoJSON sob `data/derived` ou `tests/fixtures` | contagem de feições e bbox |
| `sentinel2_ndvi_window` | grades `b04`/`b08` (e `scl` opcional) em memória | NDVI da janela; pixel inválido fica nulo |

Contrato em `geoai/processing/contract.py`: estado, fonte, parâmetros, algoritmos, hashes, tempo e RSS quando a API do Windows responde. A chave de idempotência é o hash de fonte + versão + parâmetros + algoritmo, sem timestamp.

Publicação: arquivo temporário, releitura do JSON e `os.replace`. Falha não substitui um JSON já publicado da mesma chave. Saídas de execução ficam em `data/jobs/` (gitignored).

O bbox deste job não substitui `AREA_KM2` oficial nem um join QGIS.

## Sentinel-2 — só a preparação

`geoai/processing/ndvi.py` define:

- busca preferida de 7 dias e alternativa de 30 dias (busca, não garantia de cena limpa);
- nível L2A, bandas B04 e B08;
- NDVI \((B08-B04)/(B08+B04)\) sem clamp e sem tratar nulo como zero;
- SCL reamostrado por vizinho mais próximo; classes 0, 1, 3, 8, 9, 10 e 11 ficam de fora da máscara válida;
- `download_in_this_release: false`.

Não há conector Copernicus, não há recorte do Paraná e não há visualização Sentinel na interface. A Issue #40 precisa permanecer válida antes dessa visualização.

NDVI é índice espectral. Não é biogás, biomassa, rendimento nem receita.

## Medição

`py -3 scripts/benchmark_spatial_small.py` grava `docs/evidence/processing/benchmark_small.json` a partir do fixture `tests/fixtures/processing/tiny_bbox.geojson`. Os números desse arquivo são da máquina que rodou o script. Não são limite de produção.

## Testes

```powershell
ruff check geoai/processing scripts/run_geo_job.py scripts/benchmark_spatial_small.py tests/test_processing_jobs.py
pytest -q tests/test_processing_jobs.py
```

A suíte nova não exige QGIS. Os testes de PyQGIS dos MVPs anteriores continuam dependentes de QGIS instalado e não entram no CI.

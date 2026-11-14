# Processamento geoespacial — fundação (Issue #40)

Esta etapa separa a interface do cálculo pesado e registra jobs locais. Não baixa Sentinel-2 e não publica mapa de imagem.

## O que o Streamlit faz

As páginas em `app/` leem JSON e GeoJSON já preparados (`st.cache_resource` em `app/_bootstrap.py`). Não importam QGIS, não chamam Processing e não executam `geoai.processing.execute_job` durante a navegação.

PyQGIS continua apenas nos workers já existentes, fora da interface:

- `scripts/_qgis_mun_worker.py`
- `scripts/_qgis_siga_join_worker.py`

A lógica PyQGIS desses workers não mudou. O `import processing` continua dentro da função e, no join SIGA, depois do `sys.path` do plugin. Há `# noqa: I001` nesse ponto para o Ruff não reordenar o import.

## Jobs desta fundação

Executor: `py -3 scripts/run_geo_job.py` (não é chamado pelo Streamlit).

Tipos permitidos:

| Tipo | Entrada | Saída |
| --- | --- | --- |
| `vector_bbox_metrics` | GeoJSON sob `data/derived` ou `tests/fixtures` | contagem de feições e bbox |
| `sentinel2_ndvi_window` | grades `b04`/`b08` (e `scl` opcional) em memória | NDVI da janela; pixel inválido fica nulo |

Contrato em `geoai/processing/contract.py`: estado, fonte, parâmetros, algoritmos, hashes, tempo e RSS quando a API do Windows responde. A chave de idempotência inclui o SHA-256 real do arquivo (ou dos parâmetros, na janela em memória), a versão e o algoritmo. Não inclui timestamp. Um digest informado pelo chamador que não confere com a entrada é recusado. O mesmo caminho com bytes novos gera outra chave.

Publicação: cada escrita usa um temporário exclusivo no mesmo diretório e `os.replace`. Duas execuções da mesma chave no mesmo computador compartilham um lock local `{chave}.lock`: trava do sistema (`LockFile` no Windows, `flock` no Linux) e, no mesmo processo, um `threading.Lock`. O parâmetro `wait_timeout_s` (120 s por omissão) é só o tempo de espera. Não é prazo de posse. Um job longo não perde o lock, e outro processo não apaga o arquivo de quem ainda executa. Se a espera estoura, a segunda chamada falha. O arquivo pode permanecer depois da liberação; a trava do sistema cai se o processo morre. Não há fila, Redis nem worker distribuído. O JSON de resultado é gravado primeiro, ainda com o lock. O manifest `.job.json` é o ponteiro de commit: reutilizar só ocorre se o status for `succeeded`, a chave do manifest e a do payload coincidirem e `output_sha256` for o SHA-256 atual do arquivo. Ao soltar o lock, essa conferência precisa passar. Arquivo truncado, adulterado ou manifest defasado não é reutilizado. Falha não reescreve um manifest que ainda confere. Saídas de execução ficam em `data/jobs/` (gitignored).

O SHA-256 da chave é o dos bytes lidos para montar a chave. Dentro do lock o arquivo é lido de novo. Se o digest mudou, o job falha e não publica. Isso cobre a troca do arquivo entre as duas leituras. Não cobre um rasgo no meio de uma única leitura: a origem deve ser substituída com `os.replace`, não reescrita no lugar. Uma mudança depois do snapshot confirmado vale para a próxima chave, não para a publicação já feita.

O bbox deste job não substitui `AREA_KM2` oficial nem um join QGIS.

## Sentinel-2 — só a preparação

`geoai/processing/ndvi.py` define:

- busca preferida de 7 dias e alternativa de 30 dias (busca, não garantia de cena limpa);
- nível L2A, bandas B04 e B08;
- NDVI \((B08-B04)/(B08+B04)\) sem clamp e sem tratar nulo como zero;
- SCL por vizinho mais próximo **apenas por índice**, em grade sintética já alinhada (`allow_index_only=True`). Geotransform e CRS são recusados. Cena real exigiria nearest georreferenciado com GDAL ou rasterio; isso não está implementado;
- classes SCL 0, 1, 3, 8, 9, 10 e 11 ficam de fora da máscara válida;
- `download_in_this_release: false` e `operational_sentinel: false`.

Não há conector Copernicus, não há recorte do Paraná e não há visualização Sentinel na interface. A Issue #40 precisa permanecer válida antes dessa visualização.

NDVI é índice espectral. Não é biogás, biomassa, rendimento nem receita.

## Medição

`py -3 scripts/benchmark_spatial_small.py` grava `docs/evidence/processing/benchmark_small.json` a partir do fixture `tests/fixtures/processing/tiny_bbox.geojson` (238 bytes de entrada na medição registrada). Os números são da máquina que rodou o script. Não são teste de raster, não medem o Paraná e não são SLA.

## Testes

```powershell
ruff check .
pytest -q
```

A suíte nova não exige QGIS. A varredura estática de `app/` e `geoai/portal/` procura imports diretos de QGIS e `execute_job`; ela não prova a ausência de todo caminho indireto. Nenhum teste PyQGIS entra no CI.

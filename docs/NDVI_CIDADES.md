# NDVI por satélite nos municípios acima de 20 mil habitantes

Data: 2026-11-19. Continuação da Issue #42. Esta etapa não baixou cena, não
mediu pixel e não publicou NDVI.

## O que entrou

- `data/derived/ndvi_targets_pr.json`: 97 municípios com população estimada
  IBGE 2026 acima de 20.000 habitantes, 79.454 km² (40% do estado). Derivado
  dos artefatos de população e malha (classe B). Gerado por
  `scripts/prepare_ndvi_targets.py`, sem rede.
- `scripts/plan_ndvi_targets.py`: consulta o STAC oficial do Copernicus e
  grava `data/derived/ndvi_plan_pr.json`. Reusa a busca e a regra de passagem
  do piloto (`scripts/search_sentinel_pilot.py`). Não autentica e não baixa.
- `app/pages/12_NDVI_Cidades.py` e `geoai/portal/ndvi_panel.py`: mapa e tabela
  dos 97 municípios com a situação real de cada um.

## O que os dados já mostram

- 90 municípios caem na zona UTM 22 Sul (EPSG:32722) e 7 na 21 Sul
  (EPSG:32721): Foz do Iguaçu, Marechal Cândido Rondon, Medianeira, Guaíra,
  São Miguel do Iguaçu, Santa Helena e Santa Terezinha de Itaipu. O motor de
  NDVI só foi exercitado na 22 Sul.
- Só Maringá tem cena real medida: passagem S2B de 12/11/2026, 73,1% de
  pixels válidos. O raster não foi publicado.
- Astorga não tem código nem artefato no repositório.

## O que falta para rodar nos 97

1. **Generalizar o motor.** `geoai/sentinel/local_ndvi.py`,
   `geoai/sentinel/budget.py` e `scripts/run_maringa_*.py` fixam as tiles
   22KCV e 22KDV, a passagem S2B e as contagens aprovadas de Maringá
   (`APPROVED_N_AOI` e afins). Essas travas precisam virar parâmetros lidos do
   plano, com o aceite por município (fração válida mínima de 0,70) no lugar
   da contagem fixa.
2. **Processar por cena, não por município.** Uma tile serve vários
   municípios. O plano já conta cada cena uma vez; o download deve seguir a
   mesma lógica.
3. **Validar antes de escalar.** Cinco municípios de regiões diferentes,
   incluindo um da zona 21 Sul, comparando a contagem de pixels com uma
   recontagem independente.
4. **Decidir a regra para períodos nublados.** Com uma única passagem e 70%
   de pixels válidos, haverá municípios sem imagem em janelas de 15 dias. A
   página mostra a última passagem válida com a data; composição de datas é
   mudança de método e pede decisão própria.
5. **Definir onde roda e onde ficam os rasters.** O Streamlit Cloud só lê
   artefatos. Os rasters não cabem no Git: o portal deve receber estatísticas
   por município e uma prévia reduzida.

## Pergunta em aberto

A AOI é o município inteiro, como no piloto. Isso mede sobretudo lavoura. Se
o objetivo for vegetação urbana, a AOI precisa ser o perímetro urbano e o
critério de população faz sentido. Se for agricultura, o critério de
população não é o mais adequado.

## Reproduzir

```powershell
python scripts/prepare_ndvi_targets.py
python scripts/plan_ndvi_targets.py --days 15
```

## Plano medido em 2026-11-19 (catálogo real, sem download)

`data/derived/ndvi_plan_pr.json`, janela de 15 dias até 19/11/2026, 97
consultas em 459 s, sem falha. Geometria: malha de apresentação
(simplificada), suficiente para o plano e não para a medição.

| Corte de população | Municípios | Com passagem | Cenas | Tiles | Volume oficial |
|---|---:|---:|---:|---:|---:|
| acima de 20 mil | 97 | 95 | 39 | 31 | 8,08 GB |
| acima de 30 mil | 68 | 67 | 35 | 29 | 7,52 GB |
| acima de 50 mil | 38 | 37 | 27 | 24 | 5,98 GB |
| acima de 100 mil | 24 | 23 | 19 | 19 | 4,22 GB |

- Reduzir de 97 para 68 municípios economiza 7% do volume. O custo é das
  cenas, não dos municípios.
- 37 municípios precisam de mosaico de duas tiles da mesma passagem.
- 22 usos de tile estão em EPSG:32721 e 118 em EPSG:32722.
- Ponta Grossa e Piraí do Sul não têm passagem única que cubra 99,9% do
  polígono na janela. Com a regra atual ficam sem imagem.
- A regra do piloto escolhe a passagem mais recente que cobre o município,
  sem olhar nuvem. No plano, 64 de 140 usos de tile têm nuvem do item acima de
  50%, e Curitiba recebeu uma tile com 100%. Em escala, isso baixa cenas que
  serão reprovadas depois. A nuvem do item é da tile inteira e não substitui
  a fração válida no município, mas serve de triagem antes do download.

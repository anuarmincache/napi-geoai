# NDVI por satélite nos municípios acima de 20 mil habitantes

> **Congelado em 25/11/2026.** O NDVI saiu da navegação do portal e do
> protótipo web. O motor de cálculo, o plano de ciclo e o piloto medido de
> Maringá continuam no repositório. Motivos da decisão e caminho de reativação
> em `research/ndvi_congelado/LEIA-ME.md`.

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

## Otimização do ciclo — 2026-11-19

`geoai/sentinel/cycle_plan.py`, usado por `scripts/plan_ndvi_targets.py`
(plano `schema_version` 2).

No plano medido, as três bandas das 39 cenas somam 8,08 GB: B04 3,84 GB, B08
4,19 GB e SCL 0,058 GB. Das 39 cenas, 19 têm nuvem do item acima de 60% e 10
estão em 100%.

1. **Triagem por nuvem.** Passagem só é candidata com nuvem ponderada pela
   cobertura do município em até 40% (`--max-cloud`). É triagem, não aceite.
2. **Reuso de cena.** Entre as candidatas, vence a que acrescenta menos bytes
   às cenas já escolhidas para outros municípios.
3. **SCL primeiro.** O estágio 1 baixa só a SCL das cenas distintas e mede o
   teto da fração válida por município. B04 e B08 só são baixadas para cenas
   que servem algum município aprovado no estágio 1.

O plano grava a regra antiga e a nova lado a lado, e todas as passagens
candidatas de cada município. Município sem passagem dentro do limite fica
sem imagem na janela e não gera download.

O estágio 1 (download da SCL e medição por município) ainda não está
implementado: depende de credencial do Copernicus e de GDAL no computador.

### Plano otimizado medido (catálogo real, 19/11/2026)

Janela de 15 dias, 97 consultas em 607 s, sem falha.

| Limite de nuvem | Municípios | Cenas | SCL | B04+B08 (máx.) | Cenas com nuvem > 50% |
|---|---:|---:|---:|---:|---:|
| regra antiga | 95 | 39 | 58 MB | 8,03 GB | 19 acima de 60% |
| 20% | 62 | 28 | 49 MB | 6,35 GB | 0 |
| 30% | 75 | 33 | 59 MB | 7,52 GB | 1 |
| **40% (adotado)** | **83** | **34** | **60 MB** | **7,60 GB** | **0** |
| 50% | 92 | 38 | 69 MB | 8,59 GB | 3 |
| 60% | 93 | 40 | 75 MB | 9,07 GB | 4 |

- Com 40%, a nuvem ponderada das passagens escolhidas tem mediana 9,5% e
  máximo 37,7%. Datas usadas: 10, 12 e 14/11.
- O volume quase não cai. O ganho é de qualidade: a regra antiga baixaria
  metade das cenas para reprovar depois.
- 14 municípios ficam sem imagem na janela: 12 por nuvem (região de Curitiba,
  Campos Gerais e sul) e 2 sem passagem única que cubra (Ponta Grossa e
  Piraí do Sul).
- 8 das 34 cenas servem um único município cada.

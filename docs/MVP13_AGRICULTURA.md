# Agricultura — consulta territorial sem indicador

Data da inspeção: 2026-11-18. Nenhuma base agrícola foi baixada. Energia,
NDVI e o contrato MapBiomas Coleção 11 não foram alterados.

## Inventário

| Tema | Catálogo | Arquivo local | Validado | Indicador |
|---|---|---|---|---|
| Limites municipais IBGE `municipio_2025` | sim | sim | sim | não — só moldura |
| IBGE/SIDRA — PAM | não | não | não | não |
| IBGE/SIDRA — PPM | não | não | não | não |
| CONAB | não | não | não | não |
| IPARDES | não | não | não | não |
| MapBiomas Coleção 11 | sim, como LULC | não | não | não |

`data/raw` contém ANEEL, malha e população IBGE, e o piloto Sentinel. Não há
tabela SIDRA, CONAB ou IPARDES em `data/raw` nem em `data/derived`.

A malha validada tem 399 feições, CRS EPSG:4674 e área no atributo
`AREA_KM2`. A página `app/pages/10_Agricultura.py` usa essa malha para mapa,
busca e comparação de área. Produção, área plantada, rendimento e pecuária
aparecem como indisponíveis.

## O que a próxima carga precisa respeitar

1. A primeira tabela é a PAM municipal: área plantada, área colhida, produção
   e rendimento, por cultura e ano, em unidade publicada.
2. Todo código do arquivo precisa existir nos 399 `CD_MUN`. Código extra
   interrompe a carga.
3. Município ou cultura sem linha permanece sem registro. Ausência não vira
   zero e não é imputada.
4. O denominador de um percentual, se um dia existir, será declarado com a
   tabela. `AREA_KM2` não vira área plantada.
5. Série temporal só depois de dois anos validados no mesmo arquivo. PPM,
   CONAB e IPARDES seguem carga própria. CONAB não é tratada como municipal
   até o arquivo mostrar o recorte. IPARDES não substitui o IBGE enquanto a
   origem de cada número não for lida.
6. O contrato MapBiomas continua sem download. Hectare de cobertura não é
   produção nem rendimento.

## Atualização 2026-11-19 — PAM e PPM via SIDRA

Conector `geoai/connectors/sidra.py`, agregação `geoai/agriculture/build.py`,
serviço `geoai/portal/agro_panel.py` e script `scripts/prepare_agro_parana.py`.

- Tabelas: PAM 5457 (área plantada, área colhida, quantidade produzida,
  rendimento), PPM 3939 (bovinos, suínos, galináceos) e PPM 74 (leite).
- Códigos de variável e categoria não são fixados no código: são resolvidos
  pelo nome nos metadados oficiais. Nome ausente ou ambíguo interrompe a carga.
- Recorte: municípios do Paraná, último ano publicado. Sem série temporal.
- `-` do IBGE é zero verdadeiro. `..`, `...` e `X` ficam sem valor. Município
  sem linha fica "sem registro". Nada é imputado.
- O painel guarda as 12 culturas com maior soma municipal publicada de área
  plantada. Somas estaduais contam só valores publicados. Rendimento não é
  somado.
- A página só mostra valores se `data/derived/agro_pr_panel.json` existir e
  passar na validação. Sem ele, continua em "indisponível".
- Bruto em `data/raw/ibge/sidra/` (fora do Git).

Gerar: `python scripts/prepare_agro_parana.py`

# NDVI por satélite, motor congelado

Decisão de 25/11/2026: o NDVI saiu da navegação do portal e do protótipo web.
O motor de cálculo e os resultados medidos continuam no repositório, intactos,
como artefato de pesquisa.

## Por que saiu da interface

1. O recorte de análise é o município inteiro, então o índice reflete sobretudo
   lavoura e vegetação rural. Lavoura já está medida por dado oficial na
   Produção Agrícola Municipal e na cobertura do MapBiomas, sem necessidade de
   processar imagem.
2. O ciclo completo dos 97 municípios exige baixar até 7,6 GB de bandas e
   processar fora do navegador. Não cabe em um portal público sem servidor
   dedicado.
3. Em janela de 15 dias, 14 dos 97 municípios não tiveram passagem aproveitável.
   Um indicador que falha em 14% dos casos por nuvem não sustenta uma aba fixa.

## O que continua funcionando

| Item | Caminho |
|---|---|
| Registro dos 97 alvos e regra de seleção | `geoai/sentinel/targets.py` |
| Otimização do ciclo, triagem de nuvem e reuso de cena | `geoai/sentinel/cycle_plan.py` |
| Leitura de banda, máscara de nuvem e cálculo do índice | `geoai/sentinel/` |
| Serviço de apresentação | `geoai/portal/ndvi_panel.py` |
| Plano de catálogo dos 97 municípios | `data/derived/ndvi_plan_pr.json` |
| Piloto medido de Maringá | `data/derived/sentinel_maringa_pilot.json` |
| Documentação do método | `docs/NDVI_CIDADES.md` |
| Páginas de portal arquivadas | este diretório |
| Testes | `tests/` continuam cobrindo o motor |

O piloto de Maringá é um resultado medido de verdade: uma passagem única do
Sentinel-2, máscara de nuvem aplicada, 73,1% de pixels válidos. Ele é citável
como tal.

## Para reativar

O caminho viável não é o lote de 7,6 GB. É calcular o índice no servidor do
Copernicus, pela Sentinel Hub Process API, dentro da cota gratuita do Copernicus
Data Space, com cache por município e por data, e teto de requisições. Nesse
desenho o download local deixa de existir. O `cycle_plan.py` continua valendo
para escolher a passagem.

Reativar a interface significa devolver as páginas deste diretório para
`app/pages/`, recriar a rota em `web/src/app/ndvi/` e religar o bloco de resumo
em `scripts/build_web_data.py`. O histórico do Git guarda as três peças.

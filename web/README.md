# NAPI GeoAI — protótipo de interface web

Protótipo de front-end para o portal, construído com Next.js, Tailwind CSS,
shadcn/ui, MapLibre GL JS, deck.gl, Apache ECharts e Motion.

**Este protótipo não substitui nada.** O portal Streamlit em `app/` continua
sendo a interface em uso do projeto. Aqui se avalia se vale migrar.

## Páginas

| Rota | Aba | O que traz |
|---|---|---|
| `/` | Painel geral | Indicadores do estado, mapa com troca de camada, ficha ao clicar e quatro gráficos |
| `/ficha` | Ficha do município | Território, população, energia e agropecuária de um município |
| `/explorar` | Explorar o mapa | Os 399 municípios, busca, comparação lado a lado e tabela |
| `/geracao-distribuida` | Solar e geração distribuída | MMGD por município, classe de consumo e tecnologia |
| `/usinas` | Usinas e geração centralizada | SIGA por município, com filtro de tecnologia |
| `/calculadoras` | Calculadoras | Consumo de equipamentos e dimensionamento fotovoltaico preliminar |
| `/agricultura` | Agricultura e pecuária | Lavouras e rebanhos por município, com situação de cada valor |
| `/cobertura` | Cobertura da terra | MapBiomas por classe e ano, composição e mudança de estoque |
| `/ndvi` | Vegetação por satélite | Situação real dos 97 municípios e plano do ciclo |
| `/fontes` | Fontes e qualidade | Classes A, B e C, arquivos preparados e catálogo de fontes |
| `/sobre` | Sobre o projeto | O que é, o que não faz e quem faz |

## Regras mantidas

- Os dados vêm dos mesmos artefatos validados de `data/derived/`, pelos
  serviços de `geoai/portal`. Nada é recalculado no front.
- Fonte e data ao lado de cada número, e a classe científica (A, B ou C)
  visível em cada indicador.
- Ausência de dado aparece como ausência: no mapa fica cinza com "sem dado",
  na tabela aparece escrito, e nunca vira zero.
- Zero publicado, sigilo estatístico e ausência de registro são mostrados
  separadamente na aba de agricultura.
- Tarifa e irradiação não têm valor padrão nas calculadoras.

## Como rodar

Nesta pasta:

```bash
npm install
npm run dev     # http://localhost:3000
npm run build   # exportação estática em web/out/
```

`dev` e `build` geram os dados do front antes de começar, chamando
`scripts/build_web_data.py` (que não baixa nada). Se o Python não estiver no
PATH, eles avisam e seguem com o que já existir; nesse caso rode à mão, na
raiz do repositório:

```bash
python scripts/build_web_data.py
```

`npm run dados` repete só a geração.

## Decisões

- **Sem mapa-base por padrão.** A geometria é a malha oficial do IBGE servida
  pelo próprio projeto, desenhada sobre fundo escuro. Para usar um mapa-base,
  defina `NEXT_PUBLIC_BASEMAP` com a URL de um estilo MapLibre.
- **Fontes do sistema.** A build não depende de rede. No ambiente do projeto,
  troque por `next/font` com Inter e Montserrat.
- **Exportação estática** (`output: "export"`), para publicar como site de
  arquivos. Não há servidor nem banco.
- **Dados fora do Git.** `public/dados/` é gerado a partir de `data/derived/`,
  para não duplicar o artefato versionado nem deixá-lo desatualizar. Por isso
  `git pull` sozinho não traz dado novo: os scripts `predev` e `prebuild`
  cuidam disso.
- **Worker do MapLibre em `public/`.** O bundler não resolve o caminho interno
  da biblioteca; `scripts/preparar-maplibre.mjs` copia o arquivo e o mapa o
  carrega por `setWorkerUrl`.

## O que ainda não existe

- A publicação: nada foi colocado no ar.
- Imagens de NDVI: a aba mostra o andamento, não mapas de vegetação.
- Unidades de conservação e recursos hídricos, que seguem ausentes também no
  Streamlit.

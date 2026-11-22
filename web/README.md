# NAPI GeoAI — protótipo de interface web

Protótipo de front-end para o portal, construído com Next.js, Tailwind CSS,
shadcn/ui, MapLibre GL JS, deck.gl, Apache ECharts e Motion.

**Este protótipo não substitui nada.** O portal Streamlit em `app/` continua
sendo a interface do projeto. Aqui só se avalia se vale migrar.

## O que ele faz

- Lê os mesmos artefatos validados de `data/derived/`, pelos serviços de
  `geoai/portal`. Nenhum número novo é calculado no front.
- Mapa dos 399 municípios (deck.gl sobre MapLibre), com troca de indicador,
  tooltip e ficha do município ao clicar.
- Gráficos de cobertura da terra, geração distribuída, usinas e lavouras.
- Mantém as regras do projeto: fonte e data em cada número, classe A, B ou C
  visível e ausência de dado exibida como ausência.

## Como rodar

Na raiz do repositório, gere os dados do front (não baixa nada):

```bash
python scripts/build_web_data.py
```

Depois, nesta pasta:

```bash
npm install
npm run dev     # http://localhost:3000
npm run build   # exportação estática em web/out/
```

`npm run dados` repete a geração sem sair daqui.

## Decisões

- **Sem mapa-base por padrão.** A geometria é a malha oficial do IBGE servida
  pelo próprio projeto, desenhada sobre fundo escuro. Para usar um mapa-base,
  defina `NEXT_PUBLIC_BASEMAP` com a URL de um estilo MapLibre.
- **Fontes do sistema.** A build não depende de rede. No ambiente do projeto,
  troque por `next/font` com Inter e Montserrat.
- **Exportação estática** (`output: "export"`), para publicar como site de
  arquivos. Não há servidor nem banco.

## O que ainda não existe

Só a tela de painel foi construída. Ficha completa, explorador, calculadoras,
NDVI e as páginas de transparência continuam apenas no Streamlit. A navegação
lateral é visual e ainda não leva a lugar nenhum.

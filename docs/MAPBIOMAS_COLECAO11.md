# MapBiomas Coleção 11 — contrato de aquisição

Inspeção em 2026-11-18. Nenhum arquivo da tabela foi baixado. Não há SHA-256,
tamanho em bytes nem cabeçalho de coluna confirmado.

## Fonte

| Item | Situação |
|---|---|
| Página do produto | https://brasil.mapbiomas.org/iniciativas-e-produtos/cobertura-e-uso-da-terra/cobertura-30m/cobertura/ |
| Página da tabela | https://brasil.mapbiomas.org/downloads/estatisticas/ |
| Produto na página de estatísticas | Biomas, Estados e Municípios \| Cobertura 30m - Coleção 11 |
| Nome esperado do arquivo | `MAPBIOMAS_BRAZIL-COL.11-BIOME_STATE_MUNICIPALITY.xlsx` |
| Coleção e sensor | Coleção 11, Landsat, 30 m |
| Unidade | hectares |
| Anos declarados nas páginas do produto | 1985–2025 |
| Arquivo local | ausente |
| SHA-256 e tamanho | desconhecidos até a aquisição autorizada |

O nome do arquivo coincide com o produto pedido e com citação de uso
secundário. O href direto não foi lido no HTML oficial nesta etapa. A versão
“agosto de 2026” também fica por confirmar no arquivo.

A Coleção 10.1 no Dataverse é outro produto
(`MAPBIOMAS_BRAZIL-COVERAGE_STATISTICS-COL.10.1-MUNICIPALITIES_STATES_BIOMES.xlsx`,
75,0 MB, 1985–2024). Não substitui a Coleção 11 e não entra no portal.

O FAQ ainda enumera coleções até a Coleção 10 (1985–2024). As páginas de
cobertura e de estatísticas, mais novas, nomeiam a Coleção 11 e o ano 2025.
Na aquisição, o cabeçalho do arquivo é que confirma coleção e anos. Se 2025
não estiver na tabela, o ano fica indisponível e não é imputado.

## Licença e citação

O FAQ oficial pede a citação: “Projeto MapBiomas – Coleção [versão] da Série
Anual de Mapas de Cobertura e Uso da Terra do Brasil, acessado em [data]
através do link: [LINK]”. A referência metodológica citada é Souza et al.
2020, Remote Sensing 12(17), 10.3390/rs12172735.

A página antiga de termos (https://old-brasil.mapbiomas.org/termos-de-uso/)
declara uso público sob Creative Commons CC-BY, com citação obrigatória. O
registro Dataverse da Coleção 10.1 declara CC BY 4.0. Para a Coleção 11, a
licença exata será lida nos metadados do arquivo antes de gravar a
proveniência.

A área MapBiomas é a soma das áreas dos pixels. O próprio FAQ registra que a
diferença em relação à área IBGE em geral fica abaixo de 0,2% e pode chegar a
0,5% em municípios pequenos. O contrato não corrige essa diferença.

## Estrutura esperada

A página de estatísticas descreve uma tabela de área, em hectares, por classe
de cobertura, para biomas, estados e municípios. O layout largo ou longo e os
nomes das colunas só serão fixados com o arquivo aberto. Candidatos, ainda
não confirmados: código do município, bioma, estado, identificador da classe
e ano.

Códigos de classe publicados na página de cobertura da Coleção 11 estão em
`CLASS_PARENT` / `CLASS_NAME`. Classes beta: 7, 84, 62 e 91. Biomas relevantes
no Paraná: Mata Atlântica e Cerrado. Um município pode ter mais de uma linha
de bioma. A contagem que precisa fechar em 399 é a de códigos IBGE distintos,
não a de linhas.

## Regras de carga

Implementadas em `geoai/landcover/mapbiomas_col11.py`.

- `validate_parana_records` recusa a carga enquanto o arquivo e o SHA-256 não
  existirem.
- UF precisa ser PR e o geocódigo precisa ter sete dígitos começando em 41.
- O conjunto de geocódigos precisa ser exatamente o conjunto dos 399 `CD_MUN`.
  Falta ou sobra interrompe. Nada é preenchido.
- Classe fora da legenda, ano fora de 1985–2025, hectare negativo ou chave
  duplicada interrompem.
- Pai e filho com área no mesmo município, bioma e ano interrompem. Os grupos
  de exibição usam só folhas: floresta, vegetação herbácea e arbustiva,
  pastagem (15), agricultura sem pastagem, silvicultura nem mosaico, área
  urbanizada (24) e as demais folhas.
- Hectares permanecem como publicados. O percentual usa a soma das folhas como
  denominador. `area_difference_km2` compara com `AREA_KM2` e não reescala.
- A soma entre biomas do mesmo município e classe só é válida quando as
  parcelas particionam o município. A série de mudança de estoque e a tabela
  separada de desmatamento anual ficam fora até validação própria.

## Aba, depois da validação

A página atual continua sem percentual. Quando a carga passar:

- mapa municipal por classe de cobertura, na malha já validada;
- busca dos 399 municípios;
- composição percentual pelo denominador mapeado;
- comparação entre municípios, com a diferença para `AREA_KM2` visível;
- seletor de ano restrito aos anos presentes no arquivo;
- histórico de mudança só depois de dois anos validados. Isso não é o módulo
  de desmatamento.

Aba Energia, NDVI, rasters e cálculos Sentinel-2 permanecem fora desta etapa.

## Aquisição e carga — 2026-11-19

O arquivo foi obtido pelo botão "Baixar" da página oficial de estatísticas.

| Item | Valor |
|---|---|
| Link | `https://drive.google.com/uc?id=1otOqymHuixvkRGVl65zTTNyfaHo46Gqk&export=download` |
| Entrega | `.zip` com um único membro, o `.xlsx` de mesmo nome |
| `.zip` | 78.296.450 bytes, SHA-256 `c223fd84dcdd21e49d651788ff5a726a7e3aa04d2eab730e99407dd80a8d3e30` |
| `.xlsx` | 78.354.101 bytes, SHA-256 `8de70a35fdd35f943e059763d128825ee08c0978948311ac03c769e0f178abfe` |
| Versão declarada | Versão 11, agosto de 2026 (aba `READ_ME`) |
| Abas | `READ_ME`, `COVERAGE_11`, `PIVOT_COVERAGE`, `METADATA`, `LEGEND_CODE` |

Estrutura confirmada em `COVERAGE_11`: layout largo, uma linha por bioma ×
município × classe folha. Colunas: `ID`, `country`, `biome`, `region`,
`state` (nome por extenso), `geocode`, `municipality`, `municipality-state`,
`class`, `class_level_0` a `class_level_4`, `y1985` a `y2025`.

Recorte Paraná: 5.008 linhas de 77.606, 399 geocódigos, biomas Mata Atlântica
(4.892 linhas) e Cerrado (116). Dez municípios têm os dois biomas. Só classes
folha, todas na legenda do contrato. Nenhuma célula vazia. O ano 2025 está
presente.

Diferença entre área mapeada (2025) e `AREA_KM2`: mediana 0,22%, máxima 4,82%,
31 municípios acima de 1%. Acima do que o FAQ indica (0,5%). Os hectares não
foram reescalados; a diferença aparece na página por município.

Carga: `geoai/landcover/mapbiomas_load.py` e
`scripts/prepare_mapbiomas_parana.py`. O painel guarda os anos múltiplos de 5
e o último (1985, 1990, …, 2020, 2025), em nove grupos de exibição. A aba
mostra percentual sobre a área mapeada, composição, diferença de estoque entre
1985 e 2025 e CSV. Não há módulo de desmatamento. Unidades de conservação e
recursos hídricos continuam ausentes.

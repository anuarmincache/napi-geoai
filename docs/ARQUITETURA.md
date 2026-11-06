# Arquitetura proposta / Proposed architecture

**Fase:** proposta de arquitetura, sujeita à validação pela equipe.

## Princípios

1. **Ciência independente de UI:** modelos e algoritmos em pacote Python testável.
2. **Fontes desacopladas:** adaptadores por órgão e por formato (REST, CSV, GeoTIFF, GeoPackage, Earth Engine etc.).
3. **Dados rastreáveis:** preservar origem, data, versão, licença, CRS, unidades, resolução e parâmetros de processamento.
4. **Operações geoespaciais verificáveis:** QGIS/PyQGIS e bibliotecas Python com testes e amostras pequenas.
5. **Interfaces desacopladas:** FastAPI publica resultados para Streamlit e futuras aplicações.
6. **Internacionalização:** textos da interface em catálogos `pt_BR` e `en_US`; nomes de variáveis e APIs em inglês.
7. **Segurança e governança:** controles para arquivos, chaves, operações destrutivas, publicação e contribuição.
8. **Infraestrutura proporcional:** começar simples e evoluir por necessidade mensurável.

## Fluxo lógico

```text
IBGE/ANEEL/INPE/MapBiomas/...
                |
      Adaptadores de ingestão
                |
       Validação e catálogo
                |
       Processamento GeoAI
       /              \
 QGIS/PyQGIS       Python GIS
       \              /
       Armazenamento de resultados
        /                      \
      PostGIS            raster/objetos
         \                    /
              FastAPI
                 |
             Streamlit
```

## Desenvolvimento

- **GitHub:** código, issues, pull requests, documentação e CI.
- **Cursor:** implementação local, depuração e testes.
- **QGIS MCP:** ponte local para controlar QGIS Desktop; não é o backend de produção do site.
- **ChatGPT:** especificação científica, revisão, documentação e orquestração colaborativa via GitHub.
- **GitHub Actions:** lint e testes rápidos; pipelines de dados pesados devem executar em infraestrutura apropriada.

## Organização sugerida (a implementar)

```text
app/                   # Streamlit
api/                   # FastAPI
geoai/                 # motor geoespacial e analítico
connectors/            # adaptadores de dados oficiais
qgis/                  # projetos/estilos (sem rasters pesados)
tests/                 # testes unitários e integração
docs/                  # arquitetura, fontes e decisões
locales/               # pt_BR, en_US
.github/workflows/     # CI
```

## Por que ainda não Airflow ou Kafka?

**Airflow:** introduzir quando houver múltiplos DAGs ou dependências complexas, reprocessamento e operação agendada que excedam scripts e tarefas simples.

**Kafka:** considerar apenas quando houver ingestão contínua de eventos/sensores com consumidores múltiplos e métricas de escala que justifiquem o custo operacional.

## Validação científica

O estudo inicial de aptidão fotovoltaica deve explicitar variáveis, normalização, máscaras de restrição, pesos, sensibilidade, incerteza e limites de aplicação. Nenhuma camada ou classificação deve ser divulgada como viabilidade definitiva sem dados adicionais e revisão.

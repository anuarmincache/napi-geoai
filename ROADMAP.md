# Roteiro de desenvolvimento — NAPI GeoAI

> O roteiro descreve metas futuras, não funcionalidades já entregues.

## Marco 0 — Fundação e ferramentas

- [x] Repositório GitHub pessoal criado.
- [x] Conexão Cursor → QGIS MCP → QGIS Desktop validada pelo responsável (QGIS 3.44.15; porta local 9875).
- [x] Organizar ambiente Python, dependências e testes automatizados.
- [ ] Definir políticas de branches, revisão e versões.

## Marco 1 — Motor e fontes de dados

- [x] Criar pacote Python isolado da interface.
- [x] Implementar conectores documentados para IBGE e ANEEL com mocks e testes.
- [x] Definir contrato de metadados (fonte, versão, CRS, resolução, data, licença, checksum).
- [x] Arquitetura modular + qualidade + metadados didáticos (MVP 06 / Issue #19).
- [ ] Preparar ingestão de dados INPE/LABREN e MapBiomas em formatos disponíveis.
- [x] Validar a geração de recorte geoespacial do Paraná no QGIS.

## Marco 2 — Aptidão solar territorial

- [ ] Definir exclusões e restrições legais/ambientais.
- [ ] Estabelecer critérios físicos/territoriais e normalização.
- [ ] Implementar cenários de pesos e análise de sensibilidade.
- [ ] Validar geometrias, projeções, unidades e indicadores.
- [ ] Gerar mapas e tabelas reproduzíveis com dados reais.

## Marco 3 — API e aplicação bilíngue

- [x] Streamlit didático com mapa oficial do Paraná (MVP 07 / Issue #22).
- [x] Preparar publicação profissional no Community Cloud sem publicar (MVP 08 / Issue #24).
- [x] Explorador territorial dos 399 municípios do Paraná (MVP 09 / Issue #26).
- [ ] FastAPI com endpoints versionados, documentação e health check.
- [ ] Streamlit com seletor PT-BR / EN completo e mais camadas.
- [ ] Exportação de resultados e metadados.
- [ ] Separar processamento pesado da interface (portal já inicia a separação).

## Marco 4 — Infraestrutura e publicação

- [x] Planejar PostGIS local + operação (MVPs 04–05); Cloud usa artefatos versionados.
- [ ] Definir autenticação, segurança, limites de carga e observabilidade.
- [ ] Publicar demo Streamlit Cloud após aprovação explícita (nome/URL).
- [ ] Avaliar implantação institucional e incorporação ao site NAPI.
- [ ] Supabase remoto somente com necessidade dinâmica (ver docs/SUPABASE_FUTURE.md).
- [ ] Acrescentar orquestração (Airflow) apenas quando justificada.
- [ ] Avaliar mensageria (Kafka) apenas com requisitos de eventos em tempo real.

## Critérios globais de aceite

Sem credenciais no Git; sem resultados científicos fabricados; testes documentados; proveniência rastreável; alterações importantes por pull requests; publicação institucional apenas após aprovação explícita.

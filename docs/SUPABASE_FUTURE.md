# Plano futuro — Supabase PostgreSQL/PostGIS (não provisionar agora)

> Documento de planejamento (Issue #24 / MVP 08). **Não criar projeto**,
> **não ativar serviços**, **não copiar dados**, **não acessar projetos
> existentes** sem autorização específica do responsável.

## Quando considerar

Somente se a demonstração ou o portal exigir **consultas dinâmicas** que os
artefatos versionados em `data/derived` não cubram (ex.: camadas atualizadas
com frequência, autenticação de leitores, escritas controladas).

## Princípios

1. **Projeto isolado** da pesquisa local (`:5433`) e de qualquer org compartilhada.
2. **Menor privilégio** na Cloud: role de leitura para a UI; escritas só via
   pipelines auditados.
3. **Replicação seletiva e versionada** — não espelhar o banco local inteiro.
4. Motor `geoai/` permanece usável **sem** Supabase (artefatos / PostGIS local).
5. Segredos só no painel Streamlit Cloud / vault — nunca no Git.
6. Estimar custo (Pro) e backups **antes** de ativar.

## Esboço de etapas (futuro)

1. Autorização escrita de escopo + orçamento.
2. Criar projeto novo (nome/região/plano aprovados).
3. Habilitar PostGIS se necessário; schemas mínimos.
4. Migrar apenas camadas aprovadas + metadados de proveniência.
5. Adaptador em `geoai.portal` com `DataBackendMode.REMOTE_SUPABASE_FUTURE`.
6. Testes de custo, RLS, observabilidade e rollback.

Até lá, a demo Cloud usa **somente** `local_artifacts`.

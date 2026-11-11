# MVP 08 — Resultados

| Item | Resultado |
|---|---|
| Base | `main` @ `550218e` (MVP 07 merged) |
| Objetivo | Preparar publicação profissional Community Cloud **sem publicar** |
| UI | Polish UX/a11y/responsivo; tema `.streamlit/config.toml` |
| Hospedagem | `requirements-streamlit.txt`, `.python-version` 3.12, `packages.txt` |
| Docs | `MVP08_DEPLOY.md`, `SUPABASE_FUTURE.md` |
| Testes | AppTest + `test_cloud_ready` |
| Supabase | **não** provisionado |
| Publish | **não** executado — aguarda aprovação |

## Critérios de aceite

- [x] App deployável sem segredos e sem PostGIS remoto
- [x] Fail-closed / proveniência preservados
- [x] Checklist de publish + rollback documentado
- [x] PR sem merge automático
- [x] Sem tocar em Supabase Pro

## Evidência de execução local

- `ruff check .` → OK
- `pytest -q` → suite completa (inclui AppTest + `test_cloud_ready`)
- Prévia visual: `docs/evidence/mvp08/` (`home.png`, `mapa_parana.png`)

# Migrações SQL (PostGIS)

Arquivos em `migrations/` com nome `NNNN_descricao.sql`, aplicados em ordem por
`scripts/migrate_db.py` / `geoai.db.migrate.apply_migrations`.

Requer `DATABASE_URL` (ver `.env.example`) e `pip install -e ".[db]"`.

# SQL migrations

This directory contains the first hand-written database schema files for Kelvin
Assistant.

We start with plain SQL because it is easier to inspect while learning:

- every table is visible directly;
- constraints and indexes are explicit;
- the schema can be tested before adding a migration framework.

Later, the project may move these migrations behind Alembic.

## Files

- `001_create_knowledge_schema.sql`: creates the initial knowledge/RAG tables.
- `002_create_memory_schema.sql`: creates the initial v0.5 memory tables.

## Running manually on the Ubuntu VM

From the repository root:

```bash
psql \
  --host=127.0.0.1 \
  --username=kelvin \
  --dbname=kelvin_assistant \
  --file=infrastructure/sql/001_create_knowledge_schema.sql
```

Run the memory schema after the knowledge schema:

```bash
psql \
  --host=127.0.0.1 \
  --username=kelvin \
  --dbname=kelvin_assistant \
  --file=infrastructure/sql/002_create_memory_schema.sql
```

Use `PGPASSWORD` or an interactive password prompt. Do not commit database
passwords.

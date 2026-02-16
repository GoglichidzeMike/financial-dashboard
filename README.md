# Financial Dashboard

Step 1 foundation setup for local development with Docker Compose.

## Prerequisites

- Docker Desktop running
- `.env` file at project root with DB and OpenAI variables

## Bootstrap

1. Start services:

```bash
docker compose up --build -d
```

2. Run DB migrations:

```bash
docker compose exec api alembic upgrade head
```

3. Seed default categories:

```bash
docker compose exec api python -m app.seed.categories
```

## Validation

1. API health:

```bash
curl http://localhost:8000/health
```

Expected:

```json
{"status":"ok"}
```

2. API readiness (DB connectivity):

```bash
curl http://localhost:8000/ready
```

Expected:

```json
{"status":"ready"}
```

3. Frontend availability:

Open `http://localhost:5173` and verify the page shows:

- `Finance Dashboard Frontend Ready`
- `API health: ok`

4. Category seed idempotency:

Run twice:

```bash
docker compose exec api python -m app.seed.categories
```

Expected:

- First run inserts defaults (`inserted=15`)
- Second run inserts none (`inserted=0`)

5. Confirm transaction indexes:

```bash
docker compose exec db psql -U finance -d finance_db -c "\\d+ transactions"
```

Expected indexes:

- `idx_transactions_date`
- `idx_transactions_merchant`
- `idx_transactions_embedding`

## Common Issues

- DB not ready yet:
  - wait a few seconds and retry migration command.
- Running seed before migration:
  - run `alembic upgrade head` first.
- Missing environment variables:
  - verify `.env` at project root includes `POSTGRES_*` values and `OPENAI_API_KEY`.

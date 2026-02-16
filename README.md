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

## Step 2: Upload and Parse

1. Run latest migrations (adds transaction dedup key and indexes):

```bash
docker compose exec api alembic upgrade head
```

2. Upload an XLSX statement:

```bash
curl -X POST http://localhost:8000/upload \
  -F "file=@/absolute/path/to/statement.xlsx"
```

Expected response shape:

```json
{
  "upload_id": 1,
  "filename": "statement.xlsx",
  "status": "done",
  "rows_total": 100,
  "rows_skipped_non_transaction": 8,
  "rows_invalid": 1,
  "rows_duplicate": 20,
  "rows_inserted": 71
}
```

3. Query imported transactions:

```bash
curl "http://localhost:8000/transactions?limit=20&offset=0"
```

Optional filters:

- `upload_id`
- `date_from` (`YYYY-MM-DD`)
- `date_to` (`YYYY-MM-DD`)

### Step 2 Validation Checklist

- Uploading non-`.xlsx` returns `400`.
- Uploading an XLSX with no valid transaction rows returns `400`.
- Re-uploading the same file increases `rows_duplicate` and prevents duplicate inserts.
- Rows with `Balance` in `Date` are skipped.
- `/transactions` returns inserted raw rows with parsed fields.

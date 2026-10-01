# Learnify Backend

Django REST Framework · PostgreSQL (pgvector) · Celery · Redis

## Quick start (Docker)

```bash
cp .env.example .env            # then set DJANGO_SECRET_KEY
docker compose up -d --build
docker compose exec api python manage.py migrate
docker compose exec api python manage.py createsuperuser
```

API docs: http://localhost:8000/api/docs/ · Admin: http://localhost:8000/admin/ · Health: http://localhost:8000/health/

## Layout

- `config/` — settings (base/dev/test/prod), celery, urls
- `apps/<name>/` — `models.py`, `services.py` (writes), `selectors.py` (reads), `tasks.py`, `views.py`, `serializers.py`, `tests/`
- New app: `./scripts/startapp.sh <name>`, then add it to `LOCAL_APPS`

## Rules

1. Views stay thin; business logic goes in `services.py`.
2. Creator-studio viewsets use `AcademyScopedViewSetMixin` (tenant isolation, `X-Academy` header).
3. Celery tasks take IDs, are idempotent, and are enqueued with `transaction.on_commit`.
4. Every error returns `{"error": {"code", "message", "details"}}`.

## Common commands

`make up | down | logs | migrate | migrations | superuser | shell | test | lint | schema`

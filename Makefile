up:            ## start everything
	docker compose up -d --build
down:
	docker compose down
logs:
	docker compose logs -f api worker worker-ai beat
migrate:
	docker compose exec api python manage.py migrate
migrations:
	docker compose exec api python manage.py makemigrations
superuser:
	docker compose exec api python manage.py createsuperuser
shell:
	docker compose exec api python manage.py shell
test:
	docker compose exec api pytest
lint:
	docker compose exec api ruff check .
schema:
	docker compose exec api python manage.py spectacular --file schema.yml

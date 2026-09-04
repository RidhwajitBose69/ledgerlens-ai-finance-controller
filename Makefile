.PHONY: setup dev test lint generate-data seed evaluate benchmark docker-up docker-down

setup:
	python3 -m venv .venv
	. .venv/bin/activate && pip install -r backend/requirements.txt
	cd frontend && npm install

dev-backend:
	. .venv/bin/activate && uvicorn backend.app.main:app --reload --port 8000

dev-frontend:
	cd frontend && npm run dev

test:
	. .venv/bin/activate && pytest backend/tests/ -v

generate-data:
	. .venv/bin/activate && python scripts/generate_dataset.py --records 500 --seed 42

seed:
	. .venv/bin/activate && python scripts/seed_database.py

evaluate:
	. .venv/bin/activate && python scripts/run_evaluation.py --records 500 --seed 42

benchmark:
	. .venv/bin/activate && python scripts/benchmark.py

docker-up:
	docker compose up -d

docker-down:
	docker compose down

.PHONY: lint test contract boundaries migrate seed seed-200 cold-start bundle-check skills

lint:
	ruff check backend runner seeds tools tests
	python3 tools/openapi_lint.py
	python3 tools/error_usage_check.py
	python3 tools/skill_lint.py

unit:
	pytest tests/unit -q

integration:
	pytest tests/integration -q

contract:
	pytest tests/contract -q

boundaries:
	pytest tests -m boundaries -q

security:
	pytest tests/security -q

test: unit integration contract security

migrate:
	cd backend && alembic upgrade head

seed:
	python3 seeds/dev_seed.py

seed-200:
	python3 seeds/synthetic_200.py

cold-start:
	cd frontend && pnpm --filter api-client gen && pnpm --filter api-client build && pnpm --filter participant build && pnpm --filter admin build

bundle-check:
	python3 tools/bundle_check.py frontend/apps/participant/dist

skills:
	python3 tools/gen_skills.py

audit-verify:
	python3 tools/audit_verify.py

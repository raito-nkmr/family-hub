.PHONY: backend-lock backend-sync check production-smoke

backend-lock:
	cd backend && uv lock

backend-sync:
	cd backend && uv sync --locked

check:
	bash scripts/check.sh

production-smoke:
	bash scripts/production-smoke.sh

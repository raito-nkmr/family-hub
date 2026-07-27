.PHONY: backend-lock backend-sync check

backend-lock:
	cd backend && uv lock

backend-sync:
	cd backend && uv sync --locked

check:
	bash scripts/check.sh

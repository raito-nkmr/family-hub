.PHONY: backend-lock backend-sync check

backend-lock:
	cd backend && uv pip compile requirements-dev.txt --output-file requirements.lock

backend-sync:
	cd backend && uv pip sync requirements.lock

check:
	bash scripts/check.sh

import argparse
import json
from pathlib import Path

from app.core.config import Settings
from app.main import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description="Export the FastAPI OpenAPI schema")
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()

    app = create_app(Settings(app_env="test"))
    schema = app.openapi()
    arguments.output.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

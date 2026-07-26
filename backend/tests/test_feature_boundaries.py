import ast
from pathlib import Path

FEATURE_ROOT = Path(__file__).resolve().parents[1] / "app" / "features"
EXPLICIT_PUBLIC_MODULES = {"app.features.auth.dependencies"}


def test_cross_feature_imports_use_public_boundaries() -> None:
    violations: list[str] = []

    for path in FEATURE_ROOT.rglob("*.py"):
        source_feature = path.relative_to(FEATURE_ROOT).parts[0]
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.module is None:
                continue
            parts = node.module.split(".")
            if len(parts) < 4 or parts[:2] != ["app", "features"]:
                continue
            target_feature = parts[2]
            if target_feature == source_feature:
                continue
            is_public_boundary = parts[3] == "public" or node.module in EXPLICIT_PUBLIC_MODULES
            if not is_public_boundary:
                relative_path = path.relative_to(FEATURE_ROOT.parent.parent)
                violations.append(f"{relative_path}:{node.lineno} imports {node.module}")

    assert not violations, "Cross-feature imports must use public boundaries:\n" + "\n".join(violations)

"""Enforce the most important inward dependency rules without frameworks."""

import ast
from pathlib import Path

import pytest


@pytest.mark.parametrize("layer", ["domain", "application"])
def test_inner_layers_do_not_import_outer_layers(layer: str) -> None:
    package_root = Path(__file__).resolve().parents[1] / "src" / "evidenceos"
    for path in (package_root / layer).rglob("*.py"):
        syntax = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(syntax):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
            else:
                continue
            for module in modules:
                assert not module.startswith("evidenceos.infrastructure"), (path, module)
                assert not module.startswith("evidenceos.presentation"), (path, module)
                if layer == "domain":
                    assert not module.startswith("evidenceos.application"), (path, module)

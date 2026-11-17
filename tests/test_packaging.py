"""Static checks on manifest, translations and requirements."""
from __future__ import annotations

import ast
import json
import pathlib
import sys

BASE = pathlib.Path(__file__).parents[1] / "custom_components" / "advanced_google_contacts"
STDLIB = set(sys.stdlib_module_names)


def _third_party_imports():
    mods = set()
    for py in BASE.glob("*.py"):
        for node in ast.walk(ast.parse(py.read_text())):
            if isinstance(node, ast.Import):
                mods |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                mods.add(node.module.split(".")[0])
    return mods - STDLIB - {"homeassistant", "voluptuous", "aiohttp"}


def test_third_party_imports_declared_in_manifest():
    """Expected: every non-core import (e.g. dateutil) is listed in manifest requirements."""
    manifest = json.loads((BASE / "manifest.json").read_text())
    declared = " ".join(manifest.get("requirements", [])).lower()
    missing = {m for m in _third_party_imports() if m.lower() not in declared and f"python-{m}".lower() not in declared}
    assert not missing, f"not declared in manifest requirements: {missing}"


def test_translations_have_same_keys():
    def keys(d, prefix=""):
        out = set()
        for k, v in d.items():
            out |= keys(v, f"{prefix}{k}.") if isinstance(v, dict) else {prefix + k}
        return out
    de = keys(json.loads((BASE / "translations/de.json").read_text()))
    en = keys(json.loads((BASE / "translations/en.json").read_text()))
    strings = keys(json.loads((BASE / "strings.json").read_text()))
    assert de == en == strings


def test_services_yaml_matches_registered_services():
    import yaml
    services = yaml.safe_load((BASE / "services.yaml").read_text())
    assert set(services) == {"sync_birthdays_from_google_contacts", "sync_events_from_google_contacts"}

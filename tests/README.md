# Tests

Laufen gegen eine echte Home-Assistant-Instanz (pytest-homeassistant-custom-component).
Google wird durch Mock-Antworten ersetzt, Zielkalender ist ein echter `local_calendar`.

```bash
uv venv -p 3.14 .venv
uv pip install -p .venv/bin/python pytest-homeassistant-custom-component "ical" pyyaml
.venv/bin/python -m pytest
```

Für eine neuere HA-Version als die vom Test-Plugin vorgegebene (z. B. 2026.11.x) die Version mit
`--override` erzwingen und HA vor pytest importieren (HA 2026.11 verlangt, dass `httpx` erst nach HA geladen wird):

```bash
.venv/bin/python -c "import sys, homeassistant, pytest; sys.exit(pytest.main())"
```

Die Tests laufen auch in der GitHub-Action **Validate** (Job „Tests“) mit der HA-Version, die das Test-Plugin vorgibt.

# Advanced Google Contacts – Changelog

## 0.1.0 – Erste Version als „Advanced Google Contacts“
Neue Versionszählung ab 0.1.0. Funktional identisch mit `google_contacts_basedog` 4.7.0.
- Domain `google_contacts_basedog` → `advanced_google_contacts`, Name „Advanced Google Contacts“.
- Dienst heißt jetzt `advanced_google_contacts.sync_birthdays_from_google_contacts`.
- Eigenes Logo unter `brand/` (wird ab Home Assistant 2026.3 angezeigt).
- `manifest.json`: Dokumentation/Issue-Tracker zeigen auf das GitHub-Repo, `codeowners` gesetzt.
- Installation über HACS (`hacs.json`).

## Vorgänger `google_contacts_basedog` 4.7.0 – Fix: Optionswechsel Kontakt-Entitäten
4.7 behebt `ValueError: Config entry was never loaded!` beim Wechsel von
„Entitäten aus“ zu „Entitäten ein“.

Die Integration merkt sich jetzt explizit, ob die Sensor-Plattform in der aktuellen
Config-Entry-Laufzeit tatsächlich mit `async_forward_entry_setups()` geladen wurde.
`async_unload_platforms()` wird nur dann aufgerufen, wenn sie auch geladen war.

Ablauf:
- AUS → EIN: keine nicht existente Sensor-Plattform wird entladen; nach Reload wird Sensor geladen.
- EIN → AUS: geladene Sensor-Plattform wird zuerst sauber entladen; danach werden Kontakt-
  Entitäten und Kontakt-Geräte aus den Registries entfernt.
- AUS → Neustart/Reload: kein Sensor-Unload; Registry-Cleanup bleibt selbstheilend.
- Birthday-Sync und OAuth/Kontoname bleiben unverändert verfügbar.

Die Lösung hängt bewusst nicht vom neuen Optionswert ab, um den alten und neuen Zustand
beim Reload nicht zu verwechseln.

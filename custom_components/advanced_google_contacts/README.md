# Advanced Google Contacts – Changelog

## 0.2.0 – Sicherer Geburtstags-Sync
- **Nur eigene Termine:** Der Sync vergleicht und löscht nur noch Termine, die er selbst angelegt hat. Er erkennt sie an der Beschreibung
  „Synchronisiert aus Advanced Google Contacts“ oder an der alten „… Google Contacts Basedog“. Von Hand eingetragene Termine bleiben unangetastet.
- **Immer frische Daten:** Vor jedem Sync werden die Kontakte direkt bei Google geladen. Bei einem Fehler oder einer leeren Kontaktliste
  bricht der Sync ab, ohne den Kalender zu ändern. Bei abgelaufener Anmeldung startet die erneute Anmeldung.
- **Weniger Abfragen:** Sind die Kontakt-Entitäten ausgeschaltet, gibt es keinen Abruf alle 30 Minuten mehr, nur noch beim Start und beim Sync.
- **Kompatibilität:** Die Registry wird über die offiziellen Hilfsfunktionen bereinigt. Damit fällt die Warnung im Log weg, und das Aufräumen funktioniert auch ab HA 2027.9.
- `CONFIG_SCHEMA` ergänzt, Redirect-URI in den Übersetzungen per Platzhalter, `en.json` vollständig englisch.
- Hinweis: Der Zielkalender muss beim Lesen die Terminbeschreibung zurückgeben. Sonst bricht der Sync mit einer Meldung ab, ohne etwas zu löschen.

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

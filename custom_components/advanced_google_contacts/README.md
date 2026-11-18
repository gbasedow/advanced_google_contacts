# Advanced Google Contacts – Changelog

## 0.5.0 – Neues Icon
- **Neues Icon und Logo:** Ein Adressbuch mit Person, Register-Reitern und Seitenstapel, in den Farben des bisherigen Logos (#0057CC, #578CFF, #86A9FF).
- Die Vektorvorlage liegt unter `assets/icon.svg` im Repository.

## 0.4.0 – Korrekturen aus dem Testlauf
- **Keine externe Bibliothek mehr:** `python-dateutil` wird nicht mehr benötigt. Die Monatsrechnung ist eingebaut, ein fehlender Tag im Zielmonat wird auf den Monatsletzten gesetzt.
- **Start bei Netzproblemen:** Ein vorübergehender Fehler beim Abruf der Kontoadresse (Netzwerk, Timeout, HTTP 5xx) führt zu einem neuen Versuch statt zu einem dauerhaften Fehler. Eine fehlende E-Mail startet die erneute Anmeldung.
- **Kontobindung:** Der Eintrag ist an das Google-Konto gebunden (`unique_id`). Eine erneute Anmeldung mit einem anderen Konto wird abgelehnt. Bestehende Einträge werden beim Start automatisch gebunden.
- **Kalender ohne Löschfunktion:** Müssten Einträge gelöscht werden, bricht der Sync ab, bevor er etwas anlegt. Es entstehen keine Doppeleinträge mehr.
- **Gleichzeitige Syncs** in denselben Kalender laufen nacheinander statt gegeneinander.
- **Ereignistypen:** `birthday`, `anniversary`, `other`, `custom` und `all` werden unabhängig von Groß- und Kleinschreibung erkannt. Eigene Typen, die in keinem Kontakt vorkommen, stehen als Warnung im Log und in der Rückgabe (`unmatched_types`).
- **Zeitraum:** Eigene Einträge der gewählten Typen jenseits von „Monate“ werden entfernt (geprüft bis 120 Monate voraus). „Monate“ begrenzt damit strikt, wie weit im Voraus Einträge existieren.
- **Notizen in Terminen:** Ein Eintrag bleibt eigener, solange die erste Zeile der Beschreibung die Markierung ist. Darunter dürfen eigene Notizen stehen.
- **Reparaturhinweise** werden beim Entfernen der Integration mitgelöscht.
- **Gerätenamen** folgen Umbenennungen in Google. Ein in HA selbst vergebener Name bleibt.
- **Historie:** Das Attribut `values` der Kontakt-Sensoren wird nicht mehr in der Historie gespeichert. Der Zustand schon.
- **Tests:** 111 automatische Tests gegen eine echte HA-Instanz laufen jetzt bei jedem Push mit.

## 0.3.0 – Beliebige Ereignisse, Titelformat, Diagnose und Reparaturhinweise
- **Beliebige Ereignisse:** Neuer Dienst `sync_events_from_google_contacts` für Geburtstage, Jahrestage, sonstige und eigene Ereignistypen.
  Ein Aufruf verwaltet nur die Einträge der gewählten Typen. `sync_birthdays_from_google_contacts` bleibt unverändert nutzbar.
- **Titelformat:** In den Optionen einstellbar, getrennt für Geburtstage und andere Ereignisse, pro Aufruf überschreibbar.
  Platzhalter {name}, {first_name}, {last_name}, {type}, {age}, {year}, optionale Teile in [ ]. Der Standard entspricht den bisherigen Titeln.
- **Diagnose-Download** ohne Token, Kontoadresse und Kontaktnamen.
- **Reparaturhinweise:** bei fehlgeschlagenem Kalender-Sync (pro Kalender) und solange die alte Integration google_contacts_basedog eingerichtet ist.
- Hat ein Kontakt einen Geburtstag mit und ohne Jahr, gilt jetzt immer die Angabe mit Jahr.

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

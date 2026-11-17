# Advanced Google Contacts (Home Assistant Custom Integration)

<img src="custom_components/advanced_google_contacts/brand/icon.png" width="96" alt="Logo">

Domain: `advanced_google_contacts` · Version: 0.2.0 · Ursprünglich als `google_contacts_basedog` 4.7.0 aus der laufenden HA-Installation übernommen.

## Zweck

Die Integration verbindet Home Assistant per OAuth2 mit der **Google People API** (nur Lesezugriff auf Kontakte) und bietet:

1. **Kalender-Sync:** Geburtstage und weitere Ereignisse der Kontakte (Jahrestage, sonstige und selbst benannte Ereignisse)
   werden als ganztägige Termine in einen beschreibbaren HA-Kalender geschrieben. Das Titelformat ist einstellbar.
2. **Kontakt-Entitäten** (optional): Für jeden Kontakt entsteht ein Gerät mit einem Sensor pro befülltem Kontaktfeld.
3. **Diagnose-Download und Reparaturhinweise** in Home Assistant.

## Dienste

| Dienst | Zweck |
|---|---|
| `advanced_google_contacts.sync_events_from_google_contacts` | Kalender-Sync für frei wählbare Ereignistypen |
| `advanced_google_contacts.sync_birthdays_from_google_contacts` | Wie oben, nur Geburtstage (bleibt für bestehende Automationen erhalten) |

Parameter:

| Parameter | Pflicht | Bedeutung |
|---|---|---|
| `calendar` | ja | Zielkalender (`calendar.*`), muss Termine anlegen und zum Aufräumen löschen können |
| `months` | ja | Zeitraum ab heute in Monaten (1–120) |
| `event_types` | nein (nur Ereignis-Dienst) | Liste aus `birthday`, `anniversary`, `other`, `custom` (alle selbst benannten Typen), `all` oder dem Namen eines eigenen Typs, z. B. `Hochzeitstag`. Standard: `birthday` |
| `title_format` | nein (nur Ereignis-Dienst) | Titelformat nur für diesen Aufruf, für alle gewählten Typen. Ohne Angabe gelten die Optionen. |

Beispiel:

```yaml
action: advanced_google_contacts.sync_events_from_google_contacts
data:
  calendar: calendar.geburtstage
  months: 24
  event_types: [birthday, anniversary, custom]
```

Rückgabe: `{desired, created, deleted, unchanged}`.

## Titelformat

Einstellbar unter *Integration → Konfigurieren*, getrennt für Geburtstage und andere Ereignisse.

| Platzhalter | Inhalt |
|---|---|
| `{name}` | Anzeigename aus Google |
| `{first_name}`, `{last_name}` | Vor- und Nachname |
| `{type}` | Geburtstag, Jahrestag, Ereignis oder der Name des eigenen Typs |
| `{age}` | Jahre seit dem Ursprungsjahr (Alter bzw. Jubiläum), leer ohne Jahr |
| `{year}` | Ursprungsjahr, leer ohne Jahr |

Text in eckigen Klammern entfällt, wenn ein Platzhalter darin leer ist.
Ein Namensplatzhalter ist Pflicht.

| Format | Ergebnis |
|---|---|
| `Geburtstag {name}[ - {age}]` (Standard) | `Geburtstag Anna Muster - 34` bzw. `Geburtstag Anna Muster` |
| `{type} {name}[ - {age}]` (Standard für Ereignisse) | `Jahrestag Anna Muster - 15` |
| `🎂 {first_name}[ ({age})]` | `🎂 Anna (34)` |

Ein geänderter Titel ersetzt beim nächsten Sync die bisherigen Einträge des Typs.
Zwei Automationen mit verschiedenen Formaten für denselben Typ und Kalender würden sich gegenseitig umschreiben.

## Diagnose und Reparaturhinweise

- **Diagnose:** *Einstellungen → Geräte & Dienste → Advanced Google Contacts → ⋮ → Diagnose herunterladen*.
  Enthalten sind die Version, die Optionen, der Abrufstatus, Kontakt-Statistiken (nur Anzahlen), das Ergebnis des letzten Syncs und die aktiven Reparaturhinweise.
  Token, Kontoadresse und Kontaktnamen werden entfernt.
- **Reparaturhinweise** (*Einstellungen → System → Reparaturen*):
  - *Kalender-Sync fehlgeschlagen*: pro Kalender, mit der Fehlermeldung. Verschwindet nach dem nächsten erfolgreichen Sync in diesen Kalender.
  - *Alte Integration noch eingerichtet*: solange `google_contacts_basedog` noch eingerichtet ist.

## Installation über HACS

1. HACS → ⋮ → *Benutzerdefinierte Repositories* → URL `https://github.com/gbasedow/advanced_google_contacts`, Typ **Integration**.
2. „Advanced Google Contacts“ herunterladen und Home Assistant neu starten.
3. *Einstellungen → Geräte & Dienste → Integration hinzufügen → Advanced Google Contacts*.

## Neue Version veröffentlichen

1. In `custom_components/advanced_google_contacts/manifest.json` die `version` erhöhen (Format `X.Y.Z`).
2. Im Changelog `custom_components/advanced_google_contacts/README.md` einen Abschnitt `## X.Y.Z – …` ergänzen. Sein Text wird zum Release-Text.
3. Nach `main` bringen, direkt oder per Pull Request.

Die Action **Release** legt dann automatisch den Release `vX.Y.Z` an, und HACS bietet das Update an.
Sie bricht ab, wenn der Changelog-Abschnitt fehlt oder die Version niedriger ist als der letzte Release.
Gibt es den Release schon, tut sie nichts. Manuell lässt sie sich über *Actions → Release → Run workflow* starten.
Die Action **Validate** prüft bei jedem Push und Pull Request die Version, den Changelog, die Python-Syntax, hassfest und die HACS-Struktur.

## Umstieg von `google_contacts_basedog` (≤ 4.7) auf `advanced_google_contacts` (0.1)

Durch die neue Domain ist es für Home Assistant eine **neue Integration**. Der alte Eintrag wird nicht übernommen.

1. In HA die alte Integration „Google Contacts Basedog“ löschen.
2. `/config/custom_components/google_contacts_basedog` entfernen, `custom_components/advanced_google_contacts` kopieren und HA neu starten.
3. Unter *Einstellungen → Anwendungs-Anmeldeinformationen* die Google-OAuth-Client-ID und das Secret für „Advanced Google Contacts“ eintragen. Die alten gehören zur alten Domain.
4. Die Integration „Advanced Google Contacts“ hinzufügen und mit Google anmelden. Danach bei Bedarf die Option für Kontakt-Entitäten setzen.
5. In Automationen den Dienst auf `advanced_google_contacts.sync_birthdays_from_google_contacts` umstellen.

Bereits angelegte Geburtstagstermine bleiben gültig. Der Sync erkennt sie an Titel und Beschreibung, auch an der alten „… Google Contacts Basedog“.

## Einrichtung

- Voraussetzungen: `application_credentials` (Google OAuth-Client vom Typ „Webanwendung“, People API aktiviert, Redirect-URI `https://my.home-assistant.io/redirect/oauth`) und `calendar`.
- Scopes: `contacts.readonly openid email`, mit `access_type=offline` und `prompt=consent`, damit ein Refresh-Token ausgestellt wird.
- Es ist nur **ein** Konto erlaubt (`single_instance_allowed`).
- Beim Start wird die E-Mail-Adresse des Kontos über OpenID UserInfo ermittelt und als Titel des Eintrags gesetzt. Bei 401/403 startet HA automatisch die Reauthentifizierung (`ConfigEntryAuthFailed`).
- Optionen: `create_contact_entities` (Standard im Code: ein), `title_format_birthday`, `title_format_event`. Eine Änderung lädt den Eintrag neu (`OptionsFlowWithReload`).

## Aufbau

| Datei | Aufgabe |
|---|---|
| `manifest.json` | Metadaten, Abhängigkeiten `application_credentials` und `calendar`, `cloud_polling` |
| `const.py` | OAuth-/API-URLs, abgefragte `personFields`, Feldliste und deutsche Feldnamen für die Entitäten |
| `application_credentials.py` | Google-Autorisierungs- und Token-Endpunkt |
| `config_flow.py` | OAuth2-Flow, Reauth und Options-Flow (Kontakt-Entitäten, Titelformate mit Prüfung) |
| `api.py` | `account_email()` über UserInfo; `contacts()` lädt alle Kontakte seitenweise (1000 pro Seite) und überspringt gelöschte. Ergebnis: Dict `resourceName → Kontakt` mit `display_name`. |
| `coordinator.py` | `DataUpdateCoordinator`. Abruf alle **30 Minuten** nur bei aktivierten Kontakt-Entitäten, sonst nur beim Start und beim Sync. 401/403 → Reauth, andere Fehler → `UpdateFailed` |
| `__init__.py` | Setup und Unload, Registrierung der Dienste, Reparaturhinweise, Aufräumen der Registry, wenn Entitäten deaktiviert sind |
| `sensor.py` | Ein Gerät pro Kontakt, ein Sensor pro befülltem Feld (der Name immer). Zustand = erster Wert (max. 255 Zeichen), Attribut `values` = alle Rohwerte. Neue Kontakte werden dynamisch ergänzt. |
| `calendar_sync.py` | Logik des Kalender-Syncs (siehe unten) |
| `title_format.py` | Prüfung und Ausgabe der Titelformate |
| `diagnostics.py` | Diagnose-Download |
| `services.yaml`, `strings.json`, `translations/` | Dienstbeschreibung und UI-Texte (de/en) |
| `brand/` | Icon und Logo (`icon.png` 256², `icon@2x.png` 512², `logo.png`, `logo@2x.png`); von HA ab 2026.3 genutzt |

## Ablauf des Kalender-Syncs

1. Prüfen, ob der Kalender existiert und `CREATE_EVENT` unterstützt. Dann die Kontakte **frisch** bei Google laden.
   Scheitert das, oder liefert Google keine Kontakte, bricht der Sync ab, ohne den Kalender zu ändern.
   Bei abgelaufener Anmeldung startet zusätzlich die Reauthentifizierung.
2. **Soll-Liste** für den Zeitraum heute bis heute + `months` erstellen, für die gewählten Ereignistypen und mit dem Titelformat.
   Pro Kontakt, Typ und Tag zählt ein Datum. Eine Angabe mit Jahr hat Vorrang vor einer ohne.
   Wer am 29.02. Geburtstag hat, bekommt den Termin in Nicht-Schaltjahren am 28.02.
3. **Anlegen:** Fehlende Termine werden ganztägig angelegt. Die Beschreibung ist die Markierung:
   „Synchronisiert aus Advanced Google Contacts“ für Geburtstage, mit angehängtem Typ für andere Ereignisse, z. B. „… [anniversary]“ oder „… [custom:Hochzeitstag]“.
4. **Kontrolllesen:** Fehlt danach ein Soll-Termin, bricht der Sync ab, **ohne etwas zu löschen**.
5. **Aufräumen:** Betrachtet werden nur Termine mit Markierung eines **gewählten** Typs, auch die alte „… Google Contacts Basedog“ (= Geburtstag).
   Ein Termin wird über Datum, Titel und Typ erkannt. Passt er nicht genau zu einem Soll-Termin, wird er über seine UID gelöscht.
   Das betrifft Duplikate, veraltete Alter, geänderte Titelformate und umbenannte oder gelöschte Kontakte.
   Von Hand angelegte Termine und Termine nicht gewählter Typen bleiben unangetastet.
6. **Abschlussprüfung:** Jeder Soll-Termin muss genau einmal vorhanden sein.

Im Einsatz: Die Automation „Geburtstage in Kalender eintragen“ läuft täglich um 01:00 mit `calendar.geburtstage` und `months: 24`.

## Hinweise aus der Code-Analyse

Bereits behoben: veraltete Registry-API, Sync mit veralteten Daten, Löschen fremder Termine, unnötiges Polling,
deutscher Text in `en.json`.

Noch offen:

- **Von Hand angelegte Termine mit gleichem Titel** werden nicht gelöscht. Neben ihnen legt der Sync aber einen eigenen Termin an, sodass er doppelt erscheint.
- Der Zielkalender muss die Terminbeschreibung beim Lesen zurückgeben. Sonst bricht der Sync mit einer Fehlermeldung ab, ohne etwas zu löschen.
- **Gleicher Titel am gleichen Tag:** Ergeben zwei Kontakte am selben Tag denselben Titel (gleicher Name), entsteht nur ein Termin.
- **Gelöschte Kontakte** hinterlassen bei aktivierten Entitäten Sensoren, die auf „nicht verfügbar“ stehen. Ihre Geräte werden nicht automatisch entfernt.

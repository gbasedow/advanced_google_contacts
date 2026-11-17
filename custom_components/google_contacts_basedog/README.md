# Google Contacts Basedog 4.7.0

## Fix: Optionswechsel Kontakt-Entitäten
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

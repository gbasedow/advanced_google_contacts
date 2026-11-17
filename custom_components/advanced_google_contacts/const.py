DOMAIN="advanced_google_contacts"
PLATFORMS=["sensor"]
AUTHORIZE="https://accounts.google.com/o/oauth2/v2/auth"
TOKEN="https://oauth2.googleapis.com/token"
SCOPE="https://www.googleapis.com/auth/contacts.readonly openid email"
URL="https://people.googleapis.com/v1/people/me/connections"
FIELDS="addresses,ageRanges,biographies,birthdays,calendarUrls,clientData,coverPhotos,emailAddresses,events,externalIds,genders,imClients,interests,locales,locations,memberships,metadata,miscKeywords,names,nicknames,occupations,organizations,phoneNumbers,photos,relations,sipAddresses,skills,urls,userDefined"
ENTITY_FIELDS=("names","nicknames","emailAddresses","phoneNumbers","addresses","birthdays","organizations","occupations","biographies","events","relations","urls","userDefined","genders","imClients","interests","locales","locations","memberships","miscKeywords","sipAddresses","skills","calendarUrls","clientData","externalIds","ageRanges")
LABELS={"names":"Name","nicknames":"Spitzname","emailAddresses":"E-Mail","phoneNumbers":"Telefon","addresses":"Adresse","birthdays":"Geburtstag","organizations":"Organisation","occupations":"Beruf","biographies":"Notizen","events":"Ereignisse","relations":"Beziehungen","urls":"Websites","userDefined":"Benutzerdefinierte Felder","genders":"Geschlecht","imClients":"Instant Messaging","interests":"Interessen","locales":"Sprache / Gebietsschema","locations":"Standorte","memberships":"Gruppen","miscKeywords":"Schlüsselwörter","sipAddresses":"SIP-Adressen","skills":"Fähigkeiten","calendarUrls":"Kalender-URLs","clientData":"Client-Daten","externalIds":"Externe IDs","photos":"Foto","coverPhotos":"Titelbild","ageRanges":"Altersbereich"}

CONF_CREATE_CONTACT_ENTITIES="create_contact_entities"
DEFAULT_CREATE_CONTACT_ENTITIES=True

PROFILE_URL="https://openidconnect.googleapis.com/v1/userinfo"

# Calendar sync: event types and title formats
CONF_TITLE_FORMAT_BIRTHDAY="title_format_birthday"
CONF_TITLE_FORMAT_EVENT="title_format_event"
DEFAULT_TITLE_FORMAT_BIRTHDAY="Geburtstag {name}[ - {age}]"
DEFAULT_TITLE_FORMAT_EVENT="{type} {name}[ - {age}]"

EVENT_TYPE_BIRTHDAY="birthday"
EVENT_TYPE_ANNIVERSARY="anniversary"
EVENT_TYPE_OTHER="other"
EVENT_TYPE_CUSTOM="custom"
EVENT_TYPE_ALL="all"
EVENT_TYPE_LABELS={EVENT_TYPE_BIRTHDAY:"Geburtstag",EVENT_TYPE_ANNIVERSARY:"Jahrestag",EVENT_TYPE_OTHER:"Ereignis"}

SERVICE_SYNC_BIRTHDAYS="sync_birthdays_from_google_contacts"
SERVICE_SYNC_EVENTS="sync_events_from_google_contacts"

LEGACY_DOMAIN="google_contacts_basedog"

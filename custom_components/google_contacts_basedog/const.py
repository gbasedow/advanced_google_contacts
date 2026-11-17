DOMAIN="google_contacts_basedog"
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

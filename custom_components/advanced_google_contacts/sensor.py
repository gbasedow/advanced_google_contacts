from homeassistant.components.sensor import SensorEntity
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN,ENTITY_FIELDS,LABELS
def primary(field,v):
 if not v:return "—"
 a=v if isinstance(v,list) else [v];x=a[0]
 if not isinstance(x,dict):s=str(x)
 elif field=="names":s=x.get("displayName","")
 elif field in ("emailAddresses","phoneNumbers","nicknames","occupations","biographies","urls","interests","locales","locations","miscKeywords","sipAddresses","skills","externalIds"):s=x.get("value","")
 elif field=="addresses":s=x.get("formattedValue") or x.get("streetAddress","")
 elif field=="birthdays":
  d=x.get("date",{});y=d.get("year");m=d.get("month");day=d.get("day");s=(f"{y:04d}-{m:02d}-{day:02d}" if y and m and day else f"{m:02d}-{day:02d}" if m and day else "")
 elif field=="organizations":s=x.get("name") or x.get("title","")
 elif field=="relations":s=x.get("person","")
 elif field=="genders":s=x.get("formattedValue") or x.get("value","")
 elif field=="imClients":s=x.get("username","")
 elif field=="userDefined":s=f"{x.get('key','')}: {x.get('value','')}".strip(": ")
 elif field in ("photos","coverPhotos"):s=x.get("url","")
 elif field=="calendarUrls":s=x.get("url","")
 elif field=="ageRanges":s=x.get("ageRange","")
 else:s=""
 return str(s or (f"{len(a)} Eintrag" if len(a)==1 else f"{len(a)} Einträge"))[:255]
async def async_setup_entry(hass,entry,add):
 c=hass.data[DOMAIN][entry.entry_id];known=set()
 @callback
 def sync_entities():
  new=[]
  for rn,contact in (c.data or {}).items():
   for field in ENTITY_FIELDS:
    if field!="names" and not contact.get(field):continue
    key=(rn,field)
    if key in known:continue
    known.add(key);new.append(Property(c,entry,rn,field))
  if new:add(new)
 sync_entities();entry.async_on_unload(c.async_add_listener(sync_entities))
class Property(CoordinatorEntity,SensorEntity):
 _attr_icon="mdi:card-account-details-outline"
 def __init__(self,c,e,rn,field):
  super().__init__(c);self.rn=rn;self.field=field;self._attr_unique_id=f"{e.entry_id}_{rn.replace('/','_')}_{field}";self._attr_name=LABELS.get(field,field)
 @property
 def contact(self):return (self.coordinator.data or {}).get(self.rn,{})
 @property
 def device_info(self):return DeviceInfo(identifiers={(DOMAIN,self.rn)},name=self.contact.get("display_name","Unbenannter Kontakt"),manufacturer="Google",model="Google Contact")
 @property
 def native_value(self):return primary(self.field,self.contact.get(self.field))
 @property
 def available(self):return super().available and self.rn in (self.coordinator.data or {})
 @property
 def extra_state_attributes(self):return {"values":self.contact.get(self.field) or []}

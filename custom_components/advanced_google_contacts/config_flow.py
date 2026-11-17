import logging
from aiohttp import ClientError
from homeassistant.config_entries import SOURCE_REAUTH, OptionsFlowWithReload
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import voluptuous as vol
from homeassistant.core import callback
from .const import (DOMAIN,SCOPE,CONF_CREATE_CONTACT_ENTITIES,DEFAULT_CREATE_CONTACT_ENTITIES,
 CONF_TITLE_FORMAT_BIRTHDAY,CONF_TITLE_FORMAT_EVENT,DEFAULT_TITLE_FORMAT_BIRTHDAY,DEFAULT_TITLE_FORMAT_EVENT)
from .api import fetch_account_email
from .title_format import PLACEHOLDERS,TitleFormatError,validate_title_format
# The form description shows the placeholders literally, e.g. "{name}".
PLACEHOLDER_HINTS={p:"{"+p+"}" for p in PLACEHOLDERS}
_LOGGER=logging.getLogger(__name__)
class Flow(config_entry_oauth2_flow.AbstractOAuth2FlowHandler,domain=DOMAIN):
 DOMAIN=DOMAIN
 VERSION=1
 @property
 def logger(self): return _LOGGER
 @property
 def extra_authorize_data(self): return {"scope":SCOPE,"access_type":"offline","prompt":"consent","include_granted_scopes":"true"}
 async def async_step_user(self,user_input=None):
  if self.source!=SOURCE_REAUTH and self._async_current_entries(): return self.async_abort(reason="single_instance_allowed")
  return await super().async_step_user(user_input)
 async def async_step_reauth(self,entry_data):
  return await self.async_step_reauth_confirm()
 async def async_step_reauth_confirm(self,user_input=None):
  if user_input is None:
   return self.async_show_form(step_id="reauth_confirm",data_schema=vol.Schema({}))
  return await self.async_step_user()
 @staticmethod
 @callback
 def async_get_options_flow(config_entry):
  return OptionsFlow()
 async def async_oauth_create_entry(self,data):
  # Bind the entry to the Google account: unique_id = account email.
  try:
   email=await fetch_account_email(async_get_clientsession(self.hass),data["token"]["access_token"])
  except (ClientError,TimeoutError,ValueError,KeyError) as err:
   _LOGGER.warning("Could not read the Google account email: %s",err)
   return self.async_abort(reason="cannot_connect")
  if self.source==SOURCE_REAUTH:
   e=self._get_reauth_entry()
   # Entries from before 0.4.0 have no unique_id; their title is the account email.
   expected=e.unique_id or (e.title if "@" in e.title else None)
   if expected and expected.casefold()!=email.casefold():
    return self.async_abort(reason="wrong_account")
   return self.async_update_reload_and_abort(e,unique_id=email,title=email,data={**e.data,**data})
  await self.async_set_unique_id(email)
  self._abort_if_unique_id_configured()
  return self.async_create_entry(title=email,data=data)


class OptionsFlow(OptionsFlowWithReload):
 async def async_step_init(self,user_input=None):
  errors={}
  if user_input is not None:
   data=dict(user_input)
   for key in (CONF_TITLE_FORMAT_BIRTHDAY,CONF_TITLE_FORMAT_EVENT):
    try:data[key]=validate_title_format(data.get(key,""))
    except TitleFormatError:errors[key]="invalid_title_format"
   if not errors:
    return self.async_create_entry(title="",data=data)
  current={**self.config_entry.options,**(user_input or {})}
  return self.async_show_form(step_id="init",errors=errors,description_placeholders=PLACEHOLDER_HINTS,data_schema=vol.Schema({
   vol.Required(CONF_CREATE_CONTACT_ENTITIES,default=current.get(CONF_CREATE_CONTACT_ENTITIES,DEFAULT_CREATE_CONTACT_ENTITIES)):bool,
   vol.Required(CONF_TITLE_FORMAT_BIRTHDAY,default=current.get(CONF_TITLE_FORMAT_BIRTHDAY,DEFAULT_TITLE_FORMAT_BIRTHDAY)):str,
   vol.Required(CONF_TITLE_FORMAT_EVENT,default=current.get(CONF_TITLE_FORMAT_EVENT,DEFAULT_TITLE_FORMAT_EVENT)):str,
  }))

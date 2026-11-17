import logging
from homeassistant.config_entries import SOURCE_REAUTH, OptionsFlowWithReload
from homeassistant.helpers import config_entry_oauth2_flow
import voluptuous as vol
from homeassistant.core import callback
from .const import DOMAIN,SCOPE,CONF_CREATE_CONTACT_ENTITIES,DEFAULT_CREATE_CONTACT_ENTITIES
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
  if self.source==SOURCE_REAUTH:
   e=self._get_reauth_entry();return self.async_update_reload_and_abort(e,data={**e.data,**data})
  return self.async_create_entry(title="Google Contacts Basedog",data=data)


class OptionsFlow(OptionsFlowWithReload):
 async def async_step_init(self,user_input=None):
  if user_input is not None:
   return self.async_create_entry(title="",data=user_input)
  return self.async_show_form(step_id="init",data_schema=vol.Schema({
   vol.Required(CONF_CREATE_CONTACT_ENTITIES,default=self.config_entry.options.get(CONF_CREATE_CONTACT_ENTITIES,DEFAULT_CREATE_CONTACT_ENTITIES)):bool
  }))

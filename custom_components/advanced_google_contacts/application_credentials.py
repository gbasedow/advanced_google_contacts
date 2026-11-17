from homeassistant.components.application_credentials import AuthorizationServer
from .const import AUTHORIZE,TOKEN
REDIRECT_URL="https://my.home-assistant.io/redirect/oauth"
async def async_get_authorization_server(hass):
 return AuthorizationServer(authorize_url=AUTHORIZE,token_url=TOKEN)
async def async_get_description_placeholders(hass):
 return {"redirect_url":REDIRECT_URL}

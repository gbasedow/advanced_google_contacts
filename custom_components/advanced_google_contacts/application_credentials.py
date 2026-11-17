from homeassistant.components.application_credentials import AuthorizationServer
from .const import AUTHORIZE,TOKEN
async def async_get_authorization_server(hass):
 return AuthorizationServer(authorize_url=AUTHORIZE,token_url=TOKEN)

"""Config flow (OAuth), single instance, reauth, options flow."""
from __future__ import annotations

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow

from custom_components.advanced_google_contacts.const import DOMAIN, PROFILE_URL, TOKEN
from .conftest import EMAIL, make_entry, person

REDIRECT = "https://example.com/auth/external/callback"


async def _complete_oauth(hass, hass_client_no_auth, aioclient_mock, result):
    state = config_entry_oauth2_flow._encode_jwt(hass, {"flow_id": result["flow_id"], "redirect_uri": REDIRECT})
    assert result["type"] == FlowResultType.EXTERNAL_STEP
    assert "contacts.readonly" in result["url"] and "access_type=offline" in result["url"]
    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    aioclient_mock.post(TOKEN, json={"refresh_token": "r", "access_token": "a", "type": "Bearer", "expires_in": 3600})
    return await hass.config_entries.flow.async_configure(result["flow_id"])


async def test_full_oauth_flow_creates_entry(hass, hass_client_no_auth, aioclient_mock, current_request_with_host, google):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await _complete_oauth(hass, hass_client_no_auth, aioclient_mock, result)
    assert result["type"] == FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.title == EMAIL  # renamed on setup


async def test_single_instance(hass, google):
    make_entry(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] == FlowResultType.ABORT and result["reason"] == "single_instance_allowed"


async def test_reauth_updates_token(hass, hass_client_no_auth, aioclient_mock, current_request_with_host, setup_integration):
    entry = await setup_integration([person("1", "A B")], create_contact_entities=False)
    result = await entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    result = await _complete_oauth(hass, hass_client_no_auth, aioclient_mock, result)
    assert result["type"] == FlowResultType.ABORT and result["reason"] == "reauth_successful"
    assert entry.data["token"]["access_token"] == "a"


async def test_reauth_with_other_account_should_abort(hass, hass_client_no_auth, aioclient_mock, current_request_with_host, setup_integration, google):
    """Expected: reauthenticating with a different Google account is refused (wrong_account)."""
    entry = await setup_integration([person("1", "A B")], create_contact_entities=False)
    result = await entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    google.email = "someone.else@example.com"
    google.install()
    result = await _complete_oauth(hass, hass_client_no_auth, aioclient_mock, result)
    assert result["type"] == FlowResultType.ABORT and result["reason"] != "reauth_successful"


async def test_options_flow_validation(hass, setup_integration):
    entry = await setup_integration([person("1", "A B")], create_contact_entities=False)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(result["flow_id"], {
        "create_contact_entities": False, "title_format_birthday": "{age}", "title_format_event": "{type"})
    assert result["errors"] == {"title_format_birthday": "invalid_title_format", "title_format_event": "invalid_title_format"}
    result = await hass.config_entries.options.async_configure(result["flow_id"], {
        "create_contact_entities": False, "title_format_birthday": "🎂 {name}", "title_format_event": "{type} {name}"})
    assert result["type"] == FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options["title_format_birthday"] == "🎂 {name}"
    assert entry.state is config_entries.ConfigEntryState.LOADED

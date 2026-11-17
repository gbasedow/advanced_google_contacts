"""Contact entities: naming, states, attributes, availability."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from .conftest import person


def states_by_device(hass, entry):
    entreg, devreg = er.async_get(hass), dr.async_get(hass)
    out = {}
    for ent in er.async_entries_for_config_entry(entreg, entry.entry_id):
        dev = devreg.async_get(ent.device_id)
        out.setdefault(dev.name, {})[ent.original_name] = (ent.entity_id, hass.states.get(ent.entity_id))
    return out


async def test_sensor_states_and_attributes(hass, setup_integration):
    people = [person("1", "Anna Muster", birthday=(1990, 3, 10),
                     phoneNumbers=[{"value": "+49 1"}, {"value": "+49 2"}],
                     addresses=[{"formattedValue": "Weg 1, Ort"}])]
    entry = await setup_integration(people, create_contact_entities=True)
    anna = states_by_device(hass, entry)["Anna Muster"]
    assert anna["Telefon"][1].state == "+49 1"
    assert anna["Telefon"][1].attributes["values"] == [{"value": "+49 1"}, {"value": "+49 2"}]
    assert anna["Geburtstag"][1].state == "1990-03-10"
    assert anna["Adresse"][1].state == "Weg 1, Ort"
    assert anna["Name"][1].state == "Anna Muster"


async def test_entity_ids_should_contain_contact_name(hass, setup_integration):
    """Expected: entity ids/names include the contact (has_entity_name), not just 'sensor.telefon_2'."""
    people = [person("1", "Anna Muster", phoneNumbers=[{"value": "1"}]),
              person("2", "Bernd Beispiel", phoneNumbers=[{"value": "2"}])]
    entry = await setup_integration(people, create_contact_entities=True)
    devs = states_by_device(hass, entry)
    assert devs["Anna Muster"]["Telefon"][0] == "sensor.anna_muster_telefon"
    assert devs["Bernd Beispiel"]["Telefon"][0] == "sensor.bernd_beispiel_telefon"


async def test_birthday_without_year_state(hass, setup_integration):
    entry = await setup_integration([person("1", "A B", birthday=(None, 12, 24))], create_contact_entities=True)
    assert states_by_device(hass, entry)["A B"]["Geburtstag"][1].state == "12-24"


async def test_long_values_truncated_to_255(hass, setup_integration):
    entry = await setup_integration([person("1", "A B", biographies=[{"value": "x" * 1000}])], create_contact_entities=True)
    assert len(states_by_device(hass, entry)["A B"]["Notizen"][1].state) == 255


async def test_contact_removed_becomes_unavailable(hass, setup_integration, google):
    entry = await setup_integration([person("1", "A B", phoneNumbers=[{"value": "1"}]), person("2", "C D")],
                                    create_contact_entities=True)
    ent_id = states_by_device(hass, entry)["A B"]["Telefon"][0]
    google.people = [person("2", "C D")]
    google.install()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=31))
    await hass.async_block_till_done()
    assert hass.states.get(ent_id).state == "unavailable"


async def test_new_contact_and_new_field_added_dynamically(hass, setup_integration, google):
    entry = await setup_integration([person("1", "A B")], create_contact_entities=True)
    google.people = [person("1", "A B", phoneNumbers=[{"value": "1"}]), person("2", "C D")]
    google.install()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=31))
    await hass.async_block_till_done()
    devs = states_by_device(hass, entry)
    assert "Telefon" in devs["A B"] and "C D" in devs


async def test_renamed_contact_updates_device_name(hass, setup_integration, google):
    """Expected: renaming a contact in Google renames its HA device."""
    entry = await setup_integration([person("1", "A B")], create_contact_entities=True)
    google.people = [person("1", "A Neu")]
    google.install()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=31))
    await hass.async_block_till_done()
    assert "A Neu" in states_by_device(hass, entry)


async def test_values_attribute_not_recorded(hass, recorder_mock, setup_integration):
    """The raw 'values' attribute stays live but is excluded from the recorder."""
    from homeassistant.components.recorder.history import get_significant_states
    from pytest_homeassistant_custom_component.components.recorder.common import async_wait_recording_done
    big = [{"value": f"+49 {i:010d}", "type": "mobile", "formattedType": "Mobil"} for i in range(400)]
    entry = await setup_integration([person("1", "A B", phoneNumbers=big)], create_contact_entities=True)
    ent_id, st = states_by_device(hass, entry)["A B"]["Telefon"]
    assert len(st.attributes["values"]) == 400
    await async_wait_recording_done(hass)
    hist = await hass.async_add_executor_job(get_significant_states, hass, dt_util.utcnow() - timedelta(hours=1), None, [ent_id])
    assert hist[ent_id] and "values" not in hist[ent_id][-1].attributes

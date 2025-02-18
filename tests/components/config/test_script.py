"""Tests for config/script."""
from http import HTTPStatus
import json
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.bootstrap import async_setup_component
from homeassistant.components import config
from homeassistant.const import STATE_OFF, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import yaml

from tests.typing import ClientSessionGenerator


@pytest.fixture(autouse=True, name="stub_blueprint_populate")
def stub_blueprint_populate_autouse(stub_blueprint_populate: None) -> None:
    """Stub copying the blueprints to the config folder."""


@pytest.fixture(autouse=True)
async def setup_script(hass, script_config, stub_blueprint_populate):  # noqa: F811
    """Set up script integration."""
    assert await async_setup_component(hass, "script", {"script": script_config})


@pytest.mark.parametrize("script_config", ({},))
async def test_get_script_config(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, hass_config_store
) -> None:
    """Test getting script config."""
    with patch.object(config, "SECTIONS", ["script"]):
        await async_setup_component(hass, "config", {})

    client = await hass_client()

    hass_config_store["scripts.yaml"] = {
        "sun": {"alias": "Sun"},
        "moon": {"alias": "Moon"},
    }

    resp = await client.get("/api/config/script/config/moon")

    assert resp.status == HTTPStatus.OK
    result = await resp.json()

    assert result == {"alias": "Moon"}


@pytest.mark.parametrize("script_config", ({},))
async def test_update_script_config(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, hass_config_store
) -> None:
    """Test updating script config."""
    with patch.object(config, "SECTIONS", ["script"]):
        await async_setup_component(hass, "config", {})

    assert sorted(hass.states.async_entity_ids("script")) == []

    client = await hass_client()

    orig_data = {"sun": {"alias": "Sun"}, "moon": {"alias": "Moon"}}
    hass_config_store["scripts.yaml"] = orig_data

    resp = await client.post(
        "/api/config/script/config/moon",
        data=json.dumps({"alias": "Moon updated", "sequence": []}),
    )
    await hass.async_block_till_done()
    assert sorted(hass.states.async_entity_ids("script")) == [
        "script.moon",
        "script.sun",
    ]
    assert hass.states.get("script.moon").state == STATE_OFF
    assert hass.states.get("script.sun").state == STATE_UNAVAILABLE

    assert resp.status == HTTPStatus.OK
    result = await resp.json()
    assert result == {"result": "ok"}

    new_data = hass_config_store["scripts.yaml"]
    assert list(new_data["moon"]) == ["alias", "sequence"]
    assert new_data["moon"] == {"alias": "Moon updated", "sequence": []}


@pytest.mark.parametrize("script_config", ({},))
@pytest.mark.parametrize(
    ("updated_config", "validation_error"),
    [
        ({}, "required key not provided @ data['sequence']"),
        (
            {
                "sequence": {
                    "condition": "state",
                    # The UUID will fail being resolved to en entity_id
                    "entity_id": "abcdabcdabcdabcdabcdabcdabcdabcd",
                    "state": "blah",
                }
            },
            "Unknown entity registry entry abcdabcdabcdabcdabcdabcdabcdabcd",
        ),
        (
            {
                "use_blueprint": {
                    "path": "test_service.yaml",
                    "input": {},
                },
            },
            "Missing input service_to_call",
        ),
    ],
)
async def test_update_script_config_with_error(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_config_store,
    caplog: pytest.LogCaptureFixture,
    updated_config: Any,
    validation_error: str,
) -> None:
    """Test updating script config with errors."""
    with patch.object(config, "SECTIONS", ["script"]):
        await async_setup_component(hass, "config", {})

    assert sorted(hass.states.async_entity_ids("script")) == []

    client = await hass_client()

    orig_data = {"sun": {}, "moon": {}}
    hass_config_store["scripts.yaml"] = orig_data

    resp = await client.post(
        "/api/config/script/config/moon",
        data=json.dumps(updated_config),
    )
    await hass.async_block_till_done()
    assert sorted(hass.states.async_entity_ids("script")) == []

    assert resp.status != HTTPStatus.OK
    result = await resp.json()
    assert result == {"message": f"Message malformed: {validation_error}"}
    # Assert the validation error is not logged
    assert validation_error not in caplog.text


@pytest.mark.parametrize("script_config", ({},))
@pytest.mark.parametrize(
    ("updated_config", "validation_error"),
    [
        (
            {
                "use_blueprint": {
                    "path": "test_service.yaml",
                    "input": {
                        "service_to_call": "test.automation",
                    },
                },
            },
            "No substitution found for input blah",
        ),
    ],
)
async def test_update_script_config_with_blueprint_substitution_error(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_config_store,
    # setup_automation,
    caplog: pytest.LogCaptureFixture,
    updated_config: Any,
    validation_error: str,
) -> None:
    """Test updating script config with errors."""
    with patch.object(config, "SECTIONS", ["script"]):
        await async_setup_component(hass, "config", {})

    assert sorted(hass.states.async_entity_ids("script")) == []

    client = await hass_client()

    orig_data = {"sun": {}, "moon": {}}
    hass_config_store["scripts.yaml"] = orig_data

    with patch(
        "homeassistant.components.blueprint.models.BlueprintInputs.async_substitute",
        side_effect=yaml.UndefinedSubstitution("blah"),
    ):
        resp = await client.post(
            "/api/config/script/config/moon",
            data=json.dumps(updated_config),
        )
        await hass.async_block_till_done()
    assert sorted(hass.states.async_entity_ids("script")) == []

    assert resp.status != HTTPStatus.OK
    result = await resp.json()
    assert result == {"message": f"Message malformed: {validation_error}"}
    # Assert the validation error is not logged
    assert validation_error not in caplog.text


@pytest.mark.parametrize("script_config", ({},))
async def test_update_remove_key_script_config(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, hass_config_store
) -> None:
    """Test updating script config while removing a key."""
    with patch.object(config, "SECTIONS", ["script"]):
        await async_setup_component(hass, "config", {})

    assert sorted(hass.states.async_entity_ids("script")) == []

    client = await hass_client()

    orig_data = {"sun": {"key": "value"}, "moon": {"key": "value"}}
    hass_config_store["scripts.yaml"] = orig_data

    resp = await client.post(
        "/api/config/script/config/moon",
        data=json.dumps({"sequence": []}),
    )
    await hass.async_block_till_done()
    assert sorted(hass.states.async_entity_ids("script")) == [
        "script.moon",
        "script.sun",
    ]
    assert hass.states.get("script.moon").state == STATE_OFF
    assert hass.states.get("script.sun").state == STATE_UNAVAILABLE

    assert resp.status == HTTPStatus.OK
    result = await resp.json()
    assert result == {"result": "ok"}

    new_data = hass_config_store["scripts.yaml"]
    assert list(new_data["moon"]) == ["sequence"]
    assert new_data["moon"] == {"sequence": []}


@pytest.mark.parametrize(
    "script_config",
    (
        {
            "one": {"alias": "Light on", "sequence": []},
            "two": {"alias": "Light off", "sequence": []},
        },
    ),
)
async def test_delete_script(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, hass_config_store
) -> None:
    """Test deleting a script."""
    with patch.object(config, "SECTIONS", ["script"]):
        await async_setup_component(hass, "config", {})

    assert sorted(hass.states.async_entity_ids("script")) == [
        "script.one",
        "script.two",
    ]

    ent_reg = er.async_get(hass)
    assert len(ent_reg.entities) == 2

    client = await hass_client()

    orig_data = {"one": {}, "two": {}}
    hass_config_store["scripts.yaml"] = orig_data

    resp = await client.delete("/api/config/script/config/two")
    await hass.async_block_till_done()

    assert sorted(hass.states.async_entity_ids("script")) == [
        "script.one",
    ]

    assert resp.status == HTTPStatus.OK
    result = await resp.json()
    assert result == {"result": "ok"}

    assert hass_config_store["scripts.yaml"] == {"one": {}}

    assert len(ent_reg.entities) == 1

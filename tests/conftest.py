"""Shared fixtures.

The ``pytest-homeassistant`` plugin loads itself, so there is no
``pytest_plugins`` here.
"""

from collections.abc import Iterator
from unittest.mock import patch

import pytest
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from pytest_homeassistant.common import MockConfigEntry

from custom_components.sse_ezona.const import DOMAIN

from .common import FakeApi


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Let Home Assistant load the integration from custom_components."""


@pytest.fixture
def fake_api() -> Iterator[FakeApi]:
    """Replace the eZóna client used by the integration with a fake."""
    api = FakeApi()
    with patch("custom_components.sse_ezona.SseEzonaApi", return_value=api):
        yield api


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """An entry for a made-up account, added to Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="someone@example.com",
        data={CONF_USERNAME: "someone@example.com", CONF_PASSWORD: "hunter2"},
        unique_id="someone@example.com",
    )
    entry.add_to_hass(hass)
    return entry

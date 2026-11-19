import pytest

pytest_plugins = ["pytest_homeassistant_custom_component"]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture(autouse=True)
def skip_frontend_deps(hass):
    """frontend/zeroconf need packages the test env doesn't install; the card is
    patched out in the tests, so mark them as already set up."""
    hass.config.components.update({"frontend", "zeroconf", "http"})
    yield

"""Config flow for A3 Miners."""

from homeassistant import config_entries

from .const import DOMAIN


class A3MinersConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Create one integration entry backed by miners/miners.json."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        return self.async_create_entry(title="A3 Miners", data={})

"""Config and options flows for A3 Miners."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from .const import CONF_ACTION, CONF_HOST, CONF_NAME, DOMAIN, MINERS

ACTIONS = (
    SelectOptionDict(value="add", label="Add miner"),
    SelectOptionDict(value="edit", label="Edit miner"),
    SelectOptionDict(value="remove", label="Remove miner"),
)


class A3MinersConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure the first A3 miner."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Add the first miner."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            return self.async_create_entry(
                title="A3 Miners",
                data={
                    MINERS: {
                        "miner_1": {
                            CONF_NAME: user_input[CONF_NAME],
                            CONF_HOST: user_input[CONF_HOST],
                        }
                    }
                },
            )
        return self.async_show_form(
            step_id="user",
            data_schema=_miner_schema(),
            description_placeholders={"example": "192.168.2.154"},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Create the miner management flow."""
        return A3MinersOptionsFlow()


class A3MinersOptionsFlow(config_entries.OptionsFlow):
    """Add, edit, or remove configured miners."""

    async def async_step_init(self, user_input=None):
        """Choose a miner management action."""
        actions = {
            "add": self.async_step_add,
            "edit": self.async_step_edit,
            "remove": self.async_step_remove,
        }
        if user_input is not None:
            return await actions[user_input[CONF_ACTION]]()
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ACTION): SelectSelector(
                        SelectSelectorConfig(options=list(ACTIONS))
                    )
                }
            ),
        )

    async def async_step_add(self, user_input=None):
        """Add a miner slot."""
        if user_input is not None:
            miners = dict(self.config_entry.data.get(MINERS, {}))
            miners[_next_slot(miners)] = {
                CONF_NAME: user_input[CONF_NAME],
                CONF_HOST: user_input[CONF_HOST],
            }
            await self._async_save_miners(miners)
            return self.async_create_entry(data={})
        return self.async_show_form(step_id="add", data_schema=_miner_schema())

    async def async_step_edit(self, user_input=None):
        """Choose a miner to edit."""
        if user_input is not None:
            self._slot = user_input["slot"]
            return await self.async_step_edit_miner()
        miners = self.config_entry.data.get(MINERS, {})
        return self.async_show_form(
            step_id="edit",
            data_schema=_slot_schema(miners),
            description_placeholders={"count": str(len(miners))},
        )

    async def async_step_edit_miner(self, user_input=None):
        """Update a configured miner without changing its stable slot."""
        miners = dict(self.config_entry.data.get(MINERS, {}))
        if user_input is not None:
            miners[self._slot] = {
                CONF_NAME: user_input[CONF_NAME],
                CONF_HOST: user_input[CONF_HOST],
            }
            await self._async_save_miners(miners)
            return self.async_create_entry(data={})
        return self.async_show_form(
            step_id="edit_miner",
            data_schema=_miner_schema(miners[self._slot]),
            description_placeholders={"slot": self._slot},
        )

    async def async_step_remove(self, user_input=None):
        """Remove a miner slot."""
        miners = dict(self.config_entry.data.get(MINERS, {}))
        if user_input is not None:
            if len(miners) == 1:
                return self.async_show_form(
                    step_id="remove",
                    data_schema=_slot_schema(miners),
                    errors={"base": "cannot_remove_last"},
                    description_placeholders={"count": "1"},
                )
            miners.pop(user_input["slot"])
            await self._async_save_miners(miners)
            return self.async_create_entry(data={})
        return self.async_show_form(
            step_id="remove",
            data_schema=_slot_schema(miners),
            description_placeholders={"count": str(len(miners))},
        )

    async def _async_save_miners(self, miners):
        """Store miners on the config entry and reload the integration."""
        self.hass.config_entries.async_update_entry(
            self.config_entry, data={MINERS: miners}
        )
        await self.hass.config_entries.async_reload(self.config_entry.entry_id)


def _miner_schema(defaults=None):
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, "")): str,
            vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): str,
        }
    )


def _slot_schema(miners):
    return vol.Schema({vol.Required("slot"): vol.In(sorted(miners))})


def _next_slot(miners):
    number = 1
    while f"miner_{number}" in miners:
        number += 1
    return f"miner_{number}"

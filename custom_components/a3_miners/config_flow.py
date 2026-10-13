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

from .const import (
    CONF_ACTION,
    CONF_HOST,
    CONF_IP_CHANGED,
    CONF_MAC,
    CONF_NAME,
    DOMAIN,
    MINERS,
)
from .coordinator import async_read_mac

ACTIONS = (
    SelectOptionDict(value="add", label="Add miner"),
    SelectOptionDict(value="edit", label="Edit miner"),
    SelectOptionDict(value="remove", label="Remove miner"),
)

CONNECT_CHOICES = (
    SelectOptionDict(value="yes", label="Yes, connect the existing history"),
    SelectOptionDict(value="no", label="No, add as a new device"),
)


class A3MinersConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure the first A3 miner."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Add the first miner."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        errors = {}
        if user_input is not None:
            try:
                mac = await async_read_mac(self.hass, user_input[CONF_HOST])
            except (OSError, ValueError):
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title="A3 Miners",
                    data={
                        MINERS: {
                            _slot_for_mac(mac, {}): {
                                CONF_NAME: user_input[CONF_NAME],
                                CONF_HOST: user_input[CONF_HOST],
                                CONF_MAC: mac,
                                CONF_IP_CHANGED: False,
                            }
                        }
                    },
                )
        return self.async_show_form(
            step_id="user", data_schema=_miner_schema(), errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Create the miner management flow."""
        return A3MinersOptionsFlow()


class A3MinersOptionsFlow(config_entries.OptionsFlow):
    """Add, edit, or remove configured miners."""

    _slot: str | None = None
    _pending: dict | None = None

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
        """Add a miner, identified by its MAC address."""
        errors = {}
        if user_input is not None:
            try:
                mac = await async_read_mac(self.hass, user_input[CONF_HOST])
            except (OSError, ValueError):
                errors["base"] = "cannot_connect"
            else:
                known_slot = self._known_macs().get(mac)
                if known_slot is None:
                    self._async_add_miner(
                        user_input[CONF_NAME], user_input[CONF_HOST], mac
                    )
                    return self.async_create_entry(data={})
                self._pending = {
                    "slot": known_slot,
                    CONF_NAME: user_input[CONF_NAME],
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_MAC: mac,
                }
                return await self.async_step_add_known()
        return self.async_show_form(
            step_id="add", data_schema=_miner_schema(), errors=errors
        )

    async def async_step_add_known(self, user_input=None):
        """Ask whether a known miner keeps its history."""
        if user_input is not None:
            if user_input["connect"] == "yes":
                miners = dict(self.config_entry.data.get(MINERS, {}))
                slot = self._pending["slot"]
                miners[slot] = {
                    **miners[slot],
                    CONF_HOST: self._pending[CONF_HOST],
                    CONF_MAC: self._pending[CONF_MAC],
                    CONF_IP_CHANGED: True,
                }
                self._async_save(miners)
            else:
                self._async_add_miner(
                    self._pending[CONF_NAME],
                    self._pending[CONF_HOST],
                    self._pending[CONF_MAC],
                )
            return self.async_create_entry(data={})
        return self.async_show_form(
            step_id="add_known",
            data_schema=vol.Schema(
                {
                    vol.Required("connect"): SelectSelector(
                        SelectSelectorConfig(options=list(CONNECT_CHOICES))
                    )
                }
            ),
            description_placeholders={"mac": self._pending[CONF_MAC]},
        )

    async def async_step_edit(self, user_input=None):
        """Choose a miner to edit."""
        if user_input is not None:
            self._slot = user_input["slot"]
            return await self.async_step_edit_miner()
        return self.async_show_form(
            step_id="edit",
            data_schema=_slot_schema(self.config_entry.data.get(MINERS, {})),
        )

    async def async_step_edit_miner(self, user_input=None):
        """Update a miner, refusing to point it at a different MAC address."""
        miners = dict(self.config_entry.data.get(MINERS, {}))
        record = miners[self._slot]
        errors = {}
        if user_input is not None:
            try:
                mac = await async_read_mac(self.hass, user_input[CONF_HOST])
            except (OSError, ValueError):
                errors["base"] = "cannot_connect"
            else:
                if record.get(CONF_MAC) and mac != record[CONF_MAC]:
                    errors["base"] = "mac_mismatch"
                else:
                    miners[self._slot] = {
                        **record,
                        CONF_NAME: user_input[CONF_NAME],
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_MAC: mac,
                        CONF_IP_CHANGED: record.get(CONF_IP_CHANGED, False)
                        or user_input[CONF_HOST] != record.get(CONF_HOST),
                    }
                    self._async_save(miners)
                    return self.async_create_entry(data={})
        return self.async_show_form(
            step_id="edit_miner",
            data_schema=_miner_schema(record),
            errors=errors,
            description_placeholders={"mac": record.get(CONF_MAC) or "unknown"},
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
                )
            miners.pop(user_input["slot"])
            self._async_save(miners)
            return self.async_create_entry(data={})
        return self.async_show_form(step_id="remove", data_schema=_slot_schema(miners))

    def _known_macs(self) -> dict[str, str]:
        """Map every MAC already known to its slot."""
        known = {
            record[CONF_MAC]: slot
            for slot, record in (self.config_entry.data.get(MINERS) or {}).items()
            if record.get(CONF_MAC)
        }
        coordinator = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
        if coordinator is not None:
            for slot, mac in coordinator.macs.items():
                if mac:
                    known.setdefault(mac, slot)
        return known

    def _async_add_miner(self, name: str, host: str, mac: str) -> None:
        miners = dict(self.config_entry.data.get(MINERS, {}))
        miners[_slot_for_mac(mac, miners)] = {
            CONF_NAME: name,
            CONF_HOST: host,
            CONF_MAC: mac,
            CONF_IP_CHANGED: False,
        }
        self._async_save(miners)

    def _async_save(self, miners: dict) -> None:
        """Store miners and reload the integration once the flow finishes."""
        self.hass.config_entries.async_update_entry(
            self.config_entry, data={MINERS: miners}
        )
        self.hass.async_create_task(
            self.hass.config_entries.async_reload(self.config_entry.entry_id)
        )


def _miner_schema(defaults=None):
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, "")): str,
            vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): str,
        }
    )


def _slot_schema(miners):
    options = [
        SelectOptionDict(
            value=slot,
            label=f"{record.get(CONF_NAME, slot)} ({record.get(CONF_MAC) or 'no MAC'})",
        )
        for slot, record in sorted(miners.items())
    ]
    return vol.Schema(
        {
            vol.Required("slot"): SelectSelector(
                SelectSelectorConfig(options=options)
            )
        }
    )


def _slot_for_mac(mac: str, miners: dict) -> str:
    """Build a stable slot key from a MAC address."""
    base = f"mac_{mac.replace(':', '')}"
    if base not in miners:
        return base
    suffix = 2
    while f"{base}_{suffix}" in miners:
        suffix += 1
    return f"{base}_{suffix}"

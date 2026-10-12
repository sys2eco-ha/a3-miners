# A3 Miners

Local Home Assistant integration for stock Bitmain Antminer A3 miners. Each configured `miner_N` slot creates a stable Home Assistant device and separate entities, so history survives a miner IP-address change.

## What it does

- Polls stock A3 HTTP endpoints locally using HTTP Digest authentication.
- Uses read-only requests only; it never changes pool, worker, wallet, frequency, firmware, or network settings.
- Keeps Home Assistant identity stable from the JSON slot key, not from IP or MAC address.
- Exposes hashrate, temperatures, fans, frequency, uptime, hardware errors, ASIC health, pool details, share counters, MAC address, and host.
- Exposes reachability, overheat, chain-fault, not-hashing, and pool-down binary sensors.

## Requirements

- Home Assistant with access to each miner over HTTP.
- Stock Antminer A3 firmware with HTTP Digest credentials `root` / `root`.

## Install with HACS

1. In HACS, select **Integrations**.
2. Select **Download custom repository** and enter `sys2eco-ha/a3-miners`.
3. Download **A3 Miners**.
4. Restart Home Assistant.
5. Go to **Settings → Devices & services → Add integration** and add **A3 Miners**.
6. Enter the first miner name and IP address.

To add, edit, or remove miners later, open **A3 Miners** in **Settings → Devices & services**, select **Configure**, then select the required action.
If an older installation shows a failed setup, update it through HACS, restart Home Assistant, then select **Configure → Add miner**. No JSON file is required.


## Configuration

The first setup creates `miner_1`. Each added miner gets the next available stable slot key. Slot keys preserve entity history when a configured host stays assigned to its miner.

| Field | Description |
| --- | --- |
| Name | Device name shown in Home Assistant. |
| Host | Miner IPv4 address or hostname. |

## Entities

Each configured slot creates these entities:

| Category | Entities |
| --- | --- |
| Performance | Hashrate, average hashrate, frequency, uptime |
| Hardware | PCB temperature, chip temperature, fan 1 RPM, fan 2 RPM, hardware errors, ASIC OK, ASIC bad, MAC address, host |
| Pool and shares | Pool URL, worker, status, difficulty, last share, accepted, rejected, stale, discarded |
| Health | Reachable, overheat, chain fault, not hashing, pool down |

Health thresholds: overheat is PCB temperature at least 85 °C; chain fault is any failed ASIC-chain marker; not hashing is hashrate below 1 GH/s; pool down is any pool status other than `Alive`.

## Network access

The integration reads only these miner endpoints:

- `http://<host>/cgi-bin/get_status_api.cgi`
- `http://<host>/cgi-bin/get_network_info.cgi`

Allow Home Assistant to reach TCP port 80 on each miner. Do not expose miner web interfaces to the public internet.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Integration does not start | Confirm `/config/miners/miners.json` exists and contains valid JSON with at least one slot. |
| Miner is unavailable | Confirm the `host`, local routing, and HTTP access from Home Assistant. |
| Entities use unexpected names | Keep the slot key stable; change only `name` or `host`. |
| Miner IP changed | Update that slot's `host`, then restart Home Assistant. |

## HACS status

This repository meets HACS custom-integration repository requirements. Add it as a custom repository in HACS until it is included in the default store.

## Support

[Open an issue](https://github.com/sys2eco-ha/a3-miners/issues) with Home Assistant version, integration logs, sanitized `miners.json`, and the affected slot name. Never include credentials or Home Assistant tokens.

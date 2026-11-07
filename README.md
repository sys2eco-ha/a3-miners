# A3 Miners

Local Home Assistant integration for stock Bitmain Antminer A3 miners. Each miner is identified by its **MAC address**, so entities and history follow the hardware when its IP address changes.

## What it does

- Polls the stock A3 HTTP endpoints over HTTP Digest (`root` / `root`).
- Reads only; it never changes pool, worker, wallet, frequency, firmware or network settings.
- Identifies every miner by MAC, so a new IP address does not create a new device.
- Finds miners on the network using manual IP ranges.
- Exposes hashrate, temperatures, fans, frequency, uptime, hardware errors, ASIC health, pool details, share counters, MAC and host.
- Exposes reachability, overheat, chain-fault, not-hashing and pool-down binary sensors.

## Requirements

- Home Assistant able to reach each miner over HTTP (TCP 80).
- Stock Antminer A3 firmware with HTTP Digest credentials `root` / `root`.
- `/cgi-bin/get_status_api.cgi` must report data, which requires cgminer to be running on the miner.

## Install with HACS

1. HACS → **Integrations** → three dots → **Custom repositories**.
2. Add `https://github.com/sys2eco-ha/a3-miners` as an **Integration**.
3. Download **A3 Miners** and restart Home Assistant.
4. **Settings → Devices & services → Add integration → A3 Miners**.
5. Enter the miner name and its current IP address.

## Managing miners

Open **A3 Miners** in **Settings → Devices & services** and select **Configure**:

| Action | What it does |
| --- | --- |
| Add miner | Reads the MAC from the entered IP. If the MAC is already known, asks whether to connect the existing history. |
| Edit miner | Changes the name or IP. Refuses an IP that belongs to a different MAC. |
| Remove miner | Deletes a slot. At least one miner must remain. |
| Scan network | Scans the ranges you enter and offers the miners it finds. |

### Adding a known miner

When the MAC is already configured, the flow asks:

- **Yes, connect the existing history** — the same device and entities are kept, only the host is updated and `ip_changed` is set.
- **No, add as a new device** — the old entry is left untouched and a second slot (`mac_<mac>_2`) is created with fresh history.

### Scan network

Scanning is manual only; there is no schedule and no background scan.

Enter the ranges, smaller address first, separated by commas:

```text
172.16.5.10 - 172.16.5.18, 192.168.2.10 - 192.168.2.20
```

- Format: `start - end`. A single address is `172.16.5.10 - 172.16.5.10`.
- A reversed range is rejected together with the offending entry.
- Up to 8192 addresses in total. CIDR notation is not accepted.
- While scanning, Home Assistant shows the progress percentage.
- Results are listed as `IP — MAC — new` or `IP — MAC — known`. Select what to add or re-point.

Ranges are stored in the config entry and survive restarts.

## Entities

Each miner slot creates these entities:

| Category | Entities |
| --- | --- |
| Performance | Hashrate, average hashrate, frequency, uptime |
| Hardware | PCB temperature, chip temperature, fan 1 RPM, fan 2 RPM, hardware errors, ASIC OK, ASIC bad, MAC address, host |
| Pool and shares | Pool URL, worker, status, difficulty, last share, accepted, rejected, stale, discarded |
| Health | Reachable, overheat, chain fault, not hashing, pool down |

Health thresholds: overheat is PCB temperature at or above 85 °C; chain fault is any failed chain marker; not hashing is hashrate below 1 GH/s; pool down is any pool status other than `Alive`.

Sensors carry `host`, `mac` and `ip_changed` attributes.

## Identity and history

The slot key is derived from the MAC (`mac_aabbccddeeff`). Every entity uses `unique_id = {entry_id}_{slot}_{key}`, so:

- Changing the IP address keeps the same entities and history.
- Replacing the miner with another unit creates a new device, because the MAC changes.
- The MAC is learned on the first successful poll and stored in the config entry.

## Network access

The integration reads only these endpoints:

- `http://<host>/cgi-bin/get_status_api.cgi`
- `http://<host>/cgi-bin/get_network_info.cgi`

Do not expose miner web interfaces to the public internet.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Add miner reports `cannot_connect` | The host must answer HTTP Digest and return a MAC from `get_network_info.cgi`. |
| Entities exist but every value is `unknown` | The miner answers but `get_status_api.cgi` returns `Socket connect failed`, which means cgminer (port 4028) is not running on the miner. |
| Flow texts show raw keys such as `networks_text` | Home Assistant cached the integration as having no translations. Restart Home Assistant once; later updates apply normally. |
| Scan finds nothing on a subnet | The range must be routable from Home Assistant. Scans do not cross NAT. |
| Miner IP changed | Use **Scan network**, or **Edit miner** to enter the new address. No restart is needed. |

## Support

[Open an issue](https://github.com/sys2eco-ha/a3-miners/issues) with the Home Assistant version, the affected miner MAC, and integration logs. Never include credentials or tokens.

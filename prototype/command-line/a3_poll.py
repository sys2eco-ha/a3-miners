#!/usr/bin/env python3
"""A3 (Antminer, cgminer) poller for Home Assistant.

Reads a list of miner IPs and polls every miner once, in one pass.
Prints a single JSON object on stdout.

Usage: a3_poll.py [listfile]
List file: one IP or host per line, blank lines and # comments ignored.
"""

import json
import re
import sys
import urllib.request
from urllib.error import HTTPError, URLError

LIST_FILE = sys.argv[1] if len(sys.argv) > 1 else "/config/a3_miners.txt"
TIMEOUT = 3
URL_PATH = "/cgi-bin/get_status_api.cgi"
USER, PASSWORD = "root", "root"
MAX_TEMP = 85  # firmware shuts down above this

NUM_FIELDS = {
    "hashrate": (r"GHS 5s=([0-9.]+)", float),
    "hashrate_avg": (r"GHS av=([0-9.]+)", float),
    "accepted": (r"Accepted=([0-9]+),Rejected", int),
    "rejected": (r"Rejected=([0-9]+),Discarded", int),
    "hw_errors": (r"Hardware Errors=([0-9]+)", int),
    "uptime": (r"Elapsed=([0-9]+)", int),
    "frequency": (r"frequency=([0-9]+)", int),
    "fan1": (r"fan1=([0-9]+)", int),
    "fan2": (r"fan2=([0-9]+)", int),
    "temp_pcb": (r"temp_max=([0-9]+)", int),
    "asic_ok": (None, None),   # computed below
    "asic_bad": (None, None),
    "temp_chip": (None, None),
}


def read_hosts(path):
    hosts = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.split("#", 1)[0].strip()
            if line:
                hosts.append(line)
    return hosts


def fetch(host):
    url = f"http://{host}{URL_PATH}"
    pw = urllib.request.HTTPPasswordMgrWithDefaultRealm()
    pw.add_password(None, url, USER, PASSWORD)
    opener = urllib.request.build_opener(urllib.request.HTTPDigestAuthHandler(pw))
    with opener.open(url, timeout=TIMEOUT) as resp:
        return resp.read().decode("utf-8", "replace")


def parse(text):
    data = {}
    for name, (pattern, cast) in NUM_FIELDS.items():
        if pattern is None:
            continue
        m = re.search(pattern, text)
        data[name] = cast(m.group(1)) if m else None

    acs = "".join(re.findall(r"chain_acs[123]=([^,]*)", text))
    data["asic_ok"] = acs.count("o")
    data["asic_bad"] = acs.count("x")

    chips = [int(x) for x in re.findall(r"temp2_[123]=([0-9]+)", text)]
    data["temp_chip"] = max(chips) if chips else None

    m = re.search(r"Status=([A-Za-z]+)", text)
    data["pool_status"] = m.group(1) if m else None

    data["overheat"] = bool(data.get("temp_pcb") and data["temp_pcb"] >= MAX_TEMP)
    data["chain_fault"] = data["asic_bad"] > 0
    data["not_hashing"] = (data.get("hashrate") or 0) < 1
    data["pool_down"] = data["pool_status"] != "Alive"
    return data


def status_text(m):
    if not m.get("reachable"):
        return "nepasiekiamas"
    if m.get("overheat"):
        return "PERKAITĘS"
    if m.get("chain_fault"):
        return "chain gedimas"
    if m.get("not_hashing"):
        return "nekasa"
    if m.get("pool_down"):
        return "pool down"
    return "OK"


def build_table(miners):
    rows = [
        "| Adresas | Hash GH/s | PCB °C | Chip °C | ASIC ok/viso | Accepted | Vent. rpm | Būsena |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for ip, m in miners.items():
        if m.get("reachable"):
            asic = f"{m['asic_ok']}/{m['asic_ok'] + m['asic_bad']}"
            fan = f"{m['fan1']}/{m['fan2']}"
            rows.append(
                f"| {ip} | {m['hashrate']} | {m['temp_pcb']} | {m['temp_chip']} "
                f"| {asic} | {m['accepted']} | {fan} | {status_text(m)} |"
            )
        else:
            rows.append(f"| {ip} | — | — | — | — | — | — | nepasiekiamas |")
    return "\n".join(rows)


def main():
    try:
        hosts = read_hosts(LIST_FILE)
    except OSError as err:
        print(json.dumps({"error": f"{LIST_FILE}: {err}", "total": 0, "ok": 0, "miners": {}}))
        return 0

    miners = {}
    ok = 0
    for host in hosts:
        try:
            miners[host] = parse(fetch(host))
            miners[host]["reachable"] = True
            ok += 1
        except (HTTPError, URLError, OSError, ValueError) as err:
            miners[host] = {
                "reachable": False,
                "error": type(err).__name__,
                "overheat": False,
                "chain_fault": False,
                "not_hashing": True,
                "pool_down": True,
            }

    print(json.dumps({
        "total": len(hosts),
        "ok": ok,
        "failing": len(hosts) - ok,
        "table": build_table(miners),
        "miners": miners,
    }, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())

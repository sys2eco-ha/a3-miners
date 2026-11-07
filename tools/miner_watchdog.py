#!/usr/bin/env python3
"""Watchdog for an AnthillOS (Vnish) miner.

Polls /api/v1/summary, and when the miner stays unhealthy for a number of
consecutive checks it raises a Home Assistant notification and optionally
runs a reboot command.

Standard library only.

Examples:
    # one check, print the result
    python3 miner_watchdog.py --host 172.16.8.195 --once

    # continuous, notify Home Assistant, reboot over SSH after 3 bad checks
    HA_TOKEN=... python3 miner_watchdog.py --host 172.16.8.195 \
        --ha-url http://192.168.2.202 --reboot-cmd 'ssh root@172.16.8.195 reboot'
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

LOG = logging.getLogger("miner-watchdog")

DEFAULT_STATE = os.path.expanduser("~/.config/miner-watchdog.json")


def fetch_summary(host: str, timeout: float) -> dict:
    """Return the parsed summary payload."""
    url = f"http://{host}/api/v1/summary"
    with urllib.request.urlopen(url, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8", "replace"))
    if "miner" not in payload:
        raise ValueError("response has no 'miner' section")
    return payload["miner"]


def evaluate(miner: dict, min_hashrate: float) -> tuple[bool, str]:
    """Decide whether the miner is healthy right now."""
    hashrate = miner.get("instant_hashrate")
    state = (miner.get("miner_status") or {}).get("miner_state")
    if hashrate is None:
        return False, f"no hashrate in response (state={state})"
    if float(hashrate) < min_hashrate:
        return False, f"hashrate {float(hashrate):.2f} TH/s below {min_hashrate} (state={state})"
    return True, f"{float(hashrate):.2f} TH/s, state={state}"


def notify_ha(base: str, token: str, title: str, message: str) -> None:
    """Create a persistent notification in Home Assistant."""
    body = json.dumps({"title": title, "message": message}).encode()
    request = urllib.request.Request(
        f"{base.rstrip('/')}/api/services/persistent_notification/create",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        response.read()


def run_reboot(command: str) -> tuple[bool, str]:
    """Run the configured reboot command."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as err:
        return False, str(err)
    if result.returncode != 0:
        return False, (result.stderr or result.stdout).strip()[:200]
    return True, (result.stdout or "").strip()[:200]


def load_state(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {}


def save_state(path: str, state: dict) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(state, handle)


def check(args, state: dict) -> tuple[bool, str]:
    """Run one check and apply the actions."""
    try:
        miner = fetch_summary(args.host, args.timeout)
    except (urllib.error.URLError, OSError, ValueError) as err:
        healthy, reason = False, f"unreachable: {type(err).__name__}: {err}"
    else:
        healthy, reason = evaluate(miner, args.min_hashrate)

    LOG.info("%s -> %s (%s)", "OK" if healthy else "FAIL", reason, args.host)
    if healthy:
        state["failures"] = 0
        return True, reason

    state["failures"] = int(state.get("failures", 0)) + 1
    LOG.warning("consecutive failures: %s", state["failures"])
    if state["failures"] < args.failures:
        return False, reason

    now = time.time()
    last = float(state.get("last_action", 0))
    if now - last < args.cooldown:
        LOG.warning("action skipped, cooldown %ss", int(args.cooldown - (now - last)))
        return False, reason

    state["last_action"] = now
    state["failures"] = 0

    message = f"{args.host}: {reason}"
    if args.dry_run:
        LOG.warning("dry run, would notify: %s", message)
        return False, reason

    if args.ha_url and args.ha_token:
        try:
            notify_ha(args.ha_url, args.ha_token, "Miner watchdog", message)
            LOG.warning("notified Home Assistant")
        except (urllib.error.URLError, OSError) as err:
            LOG.error("notification failed: %s", err)

    if args.reboot_cmd:
        ok, output = run_reboot(args.reboot_cmd)
        LOG.warning("reboot %s: %s", "sent" if ok else "failed", output)
    return False, reason


def main() -> int:
    parser = argparse.ArgumentParser(description="Watchdog for an AnthillOS miner")
    parser.add_argument("--host", required=True, help="miner address, e.g. 172.16.8.195")
    parser.add_argument("--min-hashrate", type=float, default=50.0, help="TH/s below which the miner counts as dead")
    parser.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout in seconds")
    parser.add_argument("--failures", type=int, default=3, help="consecutive failures before acting")
    parser.add_argument("--interval", type=float, default=60.0, help="seconds between checks in loop mode")
    parser.add_argument("--cooldown", type=float, default=1800.0, help="seconds between actions")
    parser.add_argument("--ha-url", default=os.environ.get("HA_URL"), help="Home Assistant base URL")
    parser.add_argument("--ha-token", default=os.environ.get("HA_TOKEN"), help="Home Assistant long-lived token")
    parser.add_argument("--reboot-cmd", default=None, help="command that reboots the miner")
    parser.add_argument("--state-file", default=DEFAULT_STATE, help="where counters are kept")
    parser.add_argument("--once", action="store_true", help="run a single check and exit")
    parser.add_argument("--dry-run", action="store_true", help="log actions without doing them")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    state = load_state(args.state_file)
    if args.once:
        healthy, _ = check(args, state)
        save_state(args.state_file, state)
        return 0 if healthy else 1

    LOG.info("watching %s every %ss", args.host, args.interval)
    while True:
        try:
            check(args, state)
            save_state(args.state_file, state)
        except KeyboardInterrupt:
            return 0
        except Exception as err:  # noqa: BLE001 - keep the watchdog alive
            LOG.error("unexpected error: %s", err)
        time.sleep(args.interval)


if __name__ == "__main__":
    sys.exit(main())

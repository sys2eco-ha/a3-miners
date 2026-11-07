# A3

## Tikslas

Home Assistant integracija stock firmware `Antminer A3` mineriams. Ji turi kurti atskiras HA entity ir istoriją kiekvienam mineriiui, identifikuojamam pagal MAC, nors IP adresai keičiasi.

## Struktūra

- `custom_components/a3_miners/` — HA custom component; HACS custom repository šaknis.
- `integration/a3-miners-ha.zip` — diegimo archyvas; atnaujink jį tik po komponento pakeitimų.
- `hacs.json` — HACS metaduomenys.
- `prototype/command-line/` — ankstesnis vieno `sensor.a3_miners` sprendimas; neplėsti jo, jis nesukuria atskirų istorinių entity.
- `diagnostics/` — užfiksuoti HTTP, CGMiner API ir kernel log atsakymai; naudok tik kaip diagnostikos pavyzdžius.

## Kontraktas

Konfigūracija įvedama HA UI per integracijos config flow (`Add integration` arba `Configure`) ir saugoma `config_entry.data["miners"]`:

```json
{
  "mac_aabbccddeeff": {
    "name": "Miner 1",
    "host": "192.168.2.154",
    "mac": "aa:bb:cc:dd:ee:ff",
    "ip_changed": false
  }
}
```

- Sloto raktas sudaromas iš MAC: `mac_<mac be skirtukų>`. Jei naudotojas pasirenka nejungti istorijos, pridedamas antras slotas su priesaga (`mac_<mac>_2`).
- `unique_id = {entry_id}_{slot}_{key}`, todėl MAC keitimas keičia įrenginį, o IP keitimas — ne.
- `host` ir `name` keičiami per `Configure → Edit miner`; redagavimas atmeta IP, kurio MAC nesutampa su įrašytu.
- Pridedant IP, kurio MAC jau žinomas, klausiama, ar jungti esamą istoriją.
- Rankinis `/config/miners/miners.json` failas nenaudojamas.
- Tinklo skenavimas yra tik rankinis: naudotojas įveda rėžius `mažesnis - didesnis`, atskirtus kableliais; bendra riba 8192 adresai. Jokio skenavimo pagal grafiką.

## API

Stock A3 naudoja HTTP Digest `root:root`:

```text
http://<host>/cgi-bin/get_status_api.cgi
http://<host>/cgi-bin/get_network_info.cgi
```

CGMiner TCP `4028` tinka diagnostikai, bet komponentas remiasi HTTP endpointais.

## Reikalaujamos entity

Kiekvienam minerio slotui privalo būti atskiros entity: hashrate, vidutinis hashrate, PCB/chip temperatūros, abu RPM, frequency, uptime, hardware errors, ASIC ok/bad, MAC, host, pool URL/worker/status/difficulty/last share, accepted/rejected/stale/discarded ir binary sensors reachable/overheat/chain fault/not hashing/pool down.

## Taisyklės

- Nekeisk minerio pool, worker, wallet, dažnio, firmware ar tinklo nustatymų.
- Nerašyk į A3 HTTP API; tik skaityk.
- Nenaudok MQTT šiame etape.
- Prieš diegimą HA tikrink Python sintaksę ir parserį su `diagnostics/` arba gyvu A3 API.
- Prieš release paleisk `python3 -m py_compile custom_components/a3_miners/*.py` ir patikros scenarijus su `diagnostics/` duomenimis.
- Nekomitink `__pycache__` ar `.pyc` failų; ZIP archyvas neturi jų turėti.
- HA diegimas pirmiausia turi būti patikrintas su vienu mineriu; tik tada keisti arba išmesti seną `command_line` sprendimą.
- Niekada neįrašyk HA tokenų, MQTT slaptažodžių ar kitų paslapčių į failus ar Git.

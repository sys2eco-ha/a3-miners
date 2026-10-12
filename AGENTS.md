# A3

## Tikslas

Home Assistant integracija stock firmware `Antminer A3` mineriams. Ji turi kurti atskiras HA entity ir istoriją kiekvienam pastoviam `miner_N`, nors IP adresai keičiasi.

## Struktūra

- `custom_components/a3_miners/` — HA custom component; HACS custom repository šaknis.
- `integration/a3-miners-ha.zip` — diegimo archyvas; atnaujink jį tik po komponento pakeitimų.
- `hacs.json`, `.github/workflows/validate.yml` — HACS ir hassfest validacija.
- `prototype/command-line/` — ankstesnis vieno `sensor.a3_miners` sprendimas; neplėsti jo, jis nesukuria atskirų istorinių entity.
- `diagnostics/` — užfiksuoti HTTP, CGMiner API ir kernel log atsakymai; naudok tik kaip diagnostikos pavyzdžius.

## Kontraktas

Konfigūracija įvedama HA UI per integracijos config flow (`Add integration` arba `Configure`) ir saugoma `config_entry.data["miners"]`:

```json
{
  "miner_1": { "name": "Miner 1", "host": "192.168.2.154" }
}
```

- `miner_N` yra pastovus entity tapatybės raktas; priskiriamas eilės tvarka.
- `host` ir `name` keičiami per `Configure → Edit miner`; entity vardai ir jų istorija neturi keistis.
- Rankinis `/config/miners/miners.json` failas nenaudojamas.
- Minerio MAC renkamas rodyti įrenginio tapatybę, bet šioje fazėje nenaudojamas automatiškai perrišti slotus.

## API

Stock A3 naudoja HTTP Digest `root:root`:

```text
http://<host>/cgi-bin/get_status_api.cgi
http://<host>/cgi-bin/get_network_info.cgi
```

CGMiner TCP `4028` tinka diagnostikai, bet komponentas remiasi HTTP endpointais.

## Reikalaujamos entity

Kiekvienam `miner_N` privalo būti atskiros entity: hashrate, vidutinis hashrate, PCB/chip temperatūros, abu RPM, frequency, uptime, hardware errors, ASIC ok/bad, MAC, host, pool URL/worker/status/difficulty/last share, accepted/rejected/stale/discarded ir binary sensors reachable/overheat/chain fault/not hashing/pool down.

## Taisyklės

- Nekeisk minerio pool, worker, wallet, dažnio, firmware ar tinklo nustatymų.
- Nerašyk į A3 HTTP API; tik skaityk.
- Nenaudok MQTT šiame etape.
- Prieš diegimą HA tikrink Python sintaksę ir parserį su `diagnostics/` arba gyvu A3 API.
- Prieš release palauk, kol `.github/workflows/validate.yml` (hassfest ir HACS) praeina be klaidų.
- Nekomitink `__pycache__` ar `.pyc` failų; ZIP archyvas neturi jų turėti.
- HA diegimas pirmiausia turi būti patikrintas su vienu mineriu; tik tada keisti arba išmesti seną `command_line` sprendimą.
- Niekada neįrašyk HA tokenų, MQTT slaptažodžių ar kitų paslapčių į failus ar Git.

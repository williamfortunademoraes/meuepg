#!/usr/bin/env python3
"""Build Meu EPG from the current XMLTV source and reviewed Tvvio mappings."""

import csv
import io
import os
import urllib.request
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = "https://raw.githubusercontent.com/limaalef/BrazilTVEPG/refs/heads/main/claro.xml"


def normalize(value):
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().upper()
    for suffix in ("HD", "FHD", "4K", "SD"):
        value = value.replace(suffix, "")
    return "".join(char for char in value if char.isalnum())


def fetch_source():
    local = os.environ.get("MEU_EPG_SOURCE_FILE")
    if local:
        return Path(local).read_bytes()
    request = urllib.request.Request(SOURCE, headers={"User-Agent": "MeuEPG-Builder/1.0"})
    with urllib.request.urlopen(request, timeout=90) as response:
        return response.read()


def main():
    mapping_path = ROOT / "pareamentos.csv"
    with mapping_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    raw = fetch_source()
    source_channels = {}
    for _, element in ET.iterparse(io.BytesIO(raw), events=("end",)):
        if element.tag == "channel":
            names = [normalize((child.text or "").removeprefix("BR - ")) for child in element.findall("display-name")]
            source_channels[element.get("id", "")] = set(names)
            element.clear()

    aliases = {
        "ec:globorj": "GLOBO RIO", "ec:globosp": "GLOBO SAO PAULO",
        "ec:globoes": "GLOBO ESPIRITO SANTO", "ec:globomg": "GLOBO MINAS",
        "ec:globors": "GLOBO PORTO ALEGRE", "ec:recordrj": "RECORD RIO",
        "ec:recordsp": "RECORD SAO PAULO", "ec:recordes": "RECORD ESPIRITO SANTO",
        "ec:recordmg": "RECORD MINAS", "ec:sbtsp": "SBT SAO PAULO",
        "ec:sbtrj": "SBT RIO", "ec:canaloff": "OFF", "ec:novotempo": "NOVO TEMPO",
        "ec:nickelodeon": "NICK", "ec:nsports": "NSPORTS",
        "ec:xsports": "XSPORTS", "ec:paramountnetwork": "PARAMOUNT CHANNEL",
    }
    source_to_tvvio = {}
    for row in rows:
        key = normalize(aliases.get(row["TvvioId"], row["Tvvio"]))
        hits = [source_id for source_id, names in source_channels.items() if key in names]
        if len(hits) == 1:
            source_to_tvvio[hits[0]] = row["TvvioId"]
            row["XmltvId"] = hits[0]
            row["XmltvName"] = hits[0]
            row["Status"] = "Correspondência"
        else:
            row["XmltvId"] = ""
            row["XmltvName"] = ""
            if row["Status"] != "Sem grade fixa":
                row["Status"] = "Sem correspondência"

    tmp_path = ROOT / "epg.xml.tmp"
    channels = set()
    programme_count = 0
    with tmp_path.open("wb") as output:
        output.write(b'<?xml version="1.0" encoding="UTF-8"?>\n<tv generator-info-name="Meu EPG">\n')
        for _, element in ET.iterparse(io.BytesIO(raw), events=("end",)):
            if element.tag == "channel":
                source_id = element.get("id", "")
                tvvio_id = source_to_tvvio.get(source_id)
                if tvvio_id:
                    channels.add(source_id)
                    safe_id = tvvio_id.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")
                    output.write(f'  <channel id="{safe_id}"><display-name>{safe_id}</display-name></channel>\n'.encode())
                element.clear()
            elif element.tag == "programme":
                tvvio_id = source_to_tvvio.get(element.get("channel", ""))
                if tvvio_id:
                    element.set("channel", tvvio_id)
                    output.write(b"  " + ET.tostring(element, encoding="utf-8") + b"\n")
                    programme_count += 1
                element.clear()
        output.write(b"</tv>\n")
    (ROOT / "epg.xml").write_bytes(tmp_path.read_bytes())
    tmp_path.unlink()

    with mapping_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["TvvioId", "Tvvio", "XmltvId", "XmltvName", "Status"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Generated epg.xml: {len(channels)} channels, {programme_count} programmes")


if __name__ == "__main__":
    main()

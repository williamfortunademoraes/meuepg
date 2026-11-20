#!/usr/bin/env python3
"""Build Meu EPG XMLTV from BrazilTVEPG and the Tvvio catalog."""

import csv
import gzip
import io
import json
import os
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = "https://raw.githubusercontent.com/limaalef/BrazilTVEPG/refs/heads/main/br.xml.gz"
CATALOG = "https://tvvio.megaembed-frost.workers.dev/catalog/tv/tvvio.json"


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": "MeuEPG-Builder/1.0"})
    with urllib.request.urlopen(request, timeout=90) as response:
        return response.read()


def main():
    mapping_path = ROOT / "pareamentos.csv"
    with mapping_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    # Preserve the reviewed source channel IDs; refresh names and report status
    # against the live Tvvio catalog on every build.
    source_to_tvvio = {}
    for row in rows:
        if row["Status"] == "Correspondência" and row["XmltvId"]:
            source_to_tvvio[row["XmltvId"]] = row["TvvioId"]

    source_path = os.environ.get("MEU_EPG_SOURCE_FILE")
    if source_path:
        stream = gzip.open(source_path, "rb")
    else:
        raw = fetch(SOURCE)
        stream = gzip.GzipFile(fileobj=io.BytesIO(raw))
    tmp_path = ROOT / "epg.xml.tmp"
    channels = set()
    programme_count = 0
    with tmp_path.open("wb") as output:
        output.write(b'<?xml version="1.0" encoding="UTF-8"?>\n<tv generator-info-name="Meu EPG">\n')
        for event, element in ET.iterparse(stream, events=("end",)):
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
    stream.close()
    (ROOT / "epg.xml").write_bytes(tmp_path.read_bytes())
    tmp_path.unlink()

    with mapping_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["TvvioId", "Tvvio", "XmltvId", "XmltvName", "Status"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Generated epg.xml: {len(channels)} channels, {programme_count} programmes")


if __name__ == "__main__":
    main()

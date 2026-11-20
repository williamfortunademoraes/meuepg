#!/usr/bin/env python3
"""Merge available BrazilTVEPG XMLTV sources into Meu EPG."""

import csv
import io
import json
import os
import urllib.request
import unicodedata
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BASE = "https://raw.githubusercontent.com/limaalef/BrazilTVEPG/refs/heads/main/"
# Specific channel feeds come first; claro.xml fills the remaining matches.
SOURCES = ["globo.xml", "maissbt.xml", "vivoplay.xml", "xsports.xml", "epg.xml", "claro.xml"]
EXTRA_SOURCES = [
    ("EPG-Scrapper-BR", "https://raw.githubusercontent.com/marcoshimselfxd/EPG-Scrapper-BR/main/epg.xml"),
    ("epg.pw", "https://epg.pw/xmltv/epg_BR.xml"),
]
CATALOG_URL = "https://tvvio.megaembed-frost.workers.dev/catalog/tv/tvvio.json"
ALIASES = {
    "ec:globorj": "GLOBO RJ", "ec:globosp": "GLOBO SP",
    "ec:globoes": "GLOBO ES", "ec:globomg": "GLOBO MG",
    "ec:globors": "GLOBO RS", "ec:recordrj": "RECORD TV RJ",
    "ec:recordsp": "RECORD SAO PAULO", "ec:recordes": "RECORD TV ES",
    "ec:recordmg": "RECORD TV MG", "ec:sbtsp": "SBT SAO PAULO",
    "ec:sbtrj": "SBT RJ", "ec:canaloff": "OFF HD", "ec:novotempo": "TV NOVO TEMPO",
    "ec:nickelodeon": "NICK", "ec:nsports": "N SPORTS", "ec:xsports": "XSPORTS",
    "ec:paramountnetwork": "PARAMOUNT CHANNEL", "ec:discoveryid": "INVESTIGATION DISCOVERY",
    "ec:discoverychannel": "DISCOVERY", "ec:cartoonnetwork": "CARTOON",
    "ec:tvcultura": "CULTURA", "ec:paieterno": "TV PAI ETERNO",
}


def normalize(value):
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().upper()
    for suffix in ("HD", "FHD", "4K", "SD"):
        value = value.replace(suffix, "")
    return "".join(char for char in value if char.isalnum())


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": "MeuEPG-Builder/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def get_bytes(filename):
    local = os.environ.get("MEU_EPG_SOURCE_FILE")
    if local and filename == "claro.xml":
        return Path(local).read_bytes()
    return fetch(BASE + filename)


def main():
    mapping_path = ROOT / "pareamentos.csv"
    with mapping_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    catalog_raw = Path(os.environ["MEU_EPG_CATALOG_FILE"]).read_bytes() if os.environ.get("MEU_EPG_CATALOG_FILE") else fetch(CATALOG_URL)
    catalog_items = json.loads(catalog_raw).get("metas", [])
    names = {item["id"]: item.get("name", item["id"]) for item in catalog_items}
    logos = {item["id"]: item.get("logo") or item.get("poster", "") for item in catalog_items}
    rows_by_id = {row["TvvioId"]: row for row in rows}
    # Build a normalized channel-name lookup; ambiguous matches are deliberately skipped.
    target_names = defaultdict(list)
    for row in rows:
        key = normalize(ALIASES.get(row["TvvioId"], names.get(row["TvvioId"], row["Tvvio"])))
        target_names[key].append(row["TvvioId"])

    chosen = {}
    programmes = {}
    counts = defaultdict(int)
    source_for = {}
    all_sources = [(filename, BASE + filename) for filename in SOURCES] + EXTRA_SOURCES
    for filename, url in all_sources:
        try:
            raw = get_bytes(filename) if url.startswith(BASE) else fetch(url)
        except Exception as error:
            print(f"Skipping unavailable source {filename}: {error}")
            continue
        source_map = {}
        for _, element in ET.iterparse(io.BytesIO(raw), events=("end",)):
            if element.tag == "channel":
                display_names = [normalize((child.text or "").removeprefix("BR - ")) for child in element.findall("display-name")]
                matched = {channel_id for display in display_names for channel_id in target_names.get(display, [])}
                if len(matched) == 1:
                    source_map[element.get("id", "")] = matched.pop()
                element.clear()
        for _, element in ET.iterparse(io.BytesIO(raw), events=("end",)):
            if element.tag == "programme":
                channel_id = source_map.get(element.get("channel", ""))
                if channel_id:
                    element.set("channel", channel_id)
                    title = element.findtext("title", "")
                    key = (channel_id, element.get("start", ""), title)
                    if key not in programmes:
                        programmes[key] = ET.tostring(element, encoding="unicode")
                        counts[channel_id] += 1
                        source_for.setdefault(channel_id, filename)
                element.clear()
        del raw

    event_ids = {row["TvvioId"] for row in rows if row["Status"] == "Sem grade fixa"}
    for row in rows:
        channel_id = row["TvvioId"]
        row["Tvvio"] = names.get(channel_id, row["Tvvio"])
        row["XmltvId"] = source_for.get(channel_id, "")
        row["XmltvName"] = source_for.get(channel_id, "")
        row["Status"] = "Correspondência" if counts[channel_id] else ("Sem grade fixa" if channel_id in event_ids else "Sem correspondência")

    xml_path = ROOT / "epg.xml"
    with xml_path.open("w", encoding="utf-8", newline="\n") as out:
        out.write('<?xml version="1.0" encoding="UTF-8"?>\n<tv generator-info-name="Meu EPG">\n')
        active = [row for row in rows if counts[row["TvvioId"]]]
        for row in active:
            channel_id = row["TvvioId"]
            channel = ET.Element("channel", {"id": channel_id})
            ET.SubElement(channel, "display-name").text = row["Tvvio"]
            if logos.get(channel_id):
                ET.SubElement(channel, "icon", {"src": logos[channel_id]})
            out.write("  " + ET.tostring(channel, encoding="unicode") + "\n")
        for (_, _, _), program in sorted(programmes.items(), key=lambda item: item[0][1]):
            out.write("  " + program + "\n")
        out.write("</tv>\n")

    fields = ["TvvioId", "Tvvio", "XmltvId", "XmltvName", "Status"]
    with mapping_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    with (ROOT / "cobertura.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["TvvioId", "Canal", "Status", "Programas", "Fonte prioritária"])
        for row in rows:
            channel_id = row["TvvioId"]
            writer.writerow([channel_id, row["Tvvio"], row["Status"], counts[channel_id], source_for.get(channel_id, "")])
    print(f"Generated Meu EPG: {sum(bool(counts[r['TvvioId']]) for r in rows)} channels, {len(programmes)} programmes")


if __name__ == "__main__":
    main()

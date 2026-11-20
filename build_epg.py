#!/usr/bin/env python3
"""Merge available BrazilTVEPG XMLTV sources into Meu EPG."""

import csv
from bisect import bisect_left
import datetime as dt
import gzip
import html
import io
import json
import os
import re
import urllib.request
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BASE = "https://raw.githubusercontent.com/limaalef/BrazilTVEPG/refs/heads/main/"
# Specific channel feeds come first; claro.xml fills the remaining matches.
SOURCES = ["globo.xml", "maissbt.xml", "vivoplay.xml", "xsports.xml", "epg.xml", "claro.xml"]
EXTRA_SOURCES = [
    ("rootcoder/epgtv Rio map", "https://raw.githubusercontent.com/rootcoder/epgtv/main/guide.xml.gz"),
    ("Open-EPG Brazil 1", "https://www.open-epg.com/files/brazil1.xml.gz"),
    ("Open-EPG Brazil 2", "https://www.open-epg.com/files/brazil2.xml.gz"),
    ("Open-EPG Brazil 3", "https://www.open-epg.com/files/brazil3.xml.gz"),
    ("EPG-Scrapper-BR", "https://raw.githubusercontent.com/marcoshimselfxd/EPG-Scrapper-BR/main/epg.xml"),
    ("epg.pw", "https://epg.pw/xmltv/epg_BR.xml"),
    ("vinnyoliveira/epg-br fallback", "https://raw.githubusercontent.com/vinnyoliveira/epg-br/main/epg.xml.gz"),
]
SOURCE_CHANNEL_ALLOWLIST = {
    "vinnyoliveira/epg-br fallback": {"ec:mtv", "ec:comedycentral"},
}
CATALOG_URL = "https://tvvio.megaembed-frost.workers.dev/catalog/tv/tvvio.json"
RICH_EPG_URL = "https://raw.githubusercontent.com/vinnyoliveira/epg-br/main/epg-rich.xml.gz"
AMC_SERIES_URL = "https://www.amcseries.com.br/horarios/{}"
AMC_SERIES_CHANNEL = "ec:amcseries"
SP_TZ = dt.timezone(dt.timedelta(hours=-3))
RICH_METADATA_TAGS = ("desc", "category", "rating", "episode-num", "sub-title", "icon")
ALIASES = {
    "ec:globorj": "GLOBO RJ", "ec:globosp": "GLOBO SP",
    "ec:globoes": "GLOBO ES", "ec:globomg": "GLOBO MG",
    "ec:globors": "GLOBO RS", "ec:recordrj": "RECORD TV RJ",
    "ec:recordsp": "RECORD SAO PAULO", "ec:recordes": "RECORD TV ES",
    "ec:recordmg": "RECORD TV MG", "ec:sbtsp": "SBT SAO PAULO",
    "ec:sbtrj": "SBT RJ", "ec:canaloff": "OFF HD", "ec:novotempo": "TV NOVO TEMPO",
    "ec:nickelodeon": "NICK", "ec:nsports": "N SPORTS", "ec:xsports": "XSPORTS",
    "ec:paramountnetwork": "PARAMOUNT CHANNEL", "ec:discoveryid": "ID",
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


def fetch_amc_series_programmes(now=None):
    """Read the official AMC Series Brasil daily schedule and infer end times."""
    now = now or dt.datetime.now(SP_TZ)
    first_day = now.date() - dt.timedelta(days=1)
    last_day = now.date() + dt.timedelta(days=3)
    starts = []
    for offset in range((last_day - first_day).days + 1):
        day = first_day + dt.timedelta(days=offset)
        try:
            page = fetch(AMC_SERIES_URL.format(day.isoformat())).decode("utf-8", "replace")
        except Exception as error:
            print(f"Skipping unavailable source AMC Series Brasil ({day}): {error}")
            continue
        entries = re.findall(
            r'<a class="itm[^\"]*"[^>]*>\s*<span>(\d{2}:\d{2})</span>\s*(.*?)</a>',
            page,
            re.S,
        )
        for clock, raw_title in entries:
            title = html.unescape(re.sub(r"<[^>]+>", "", raw_title)).strip()
            if not title:
                continue
            hour, minute = map(int, clock.split(":"))
            starts.append((dt.datetime.combine(day, dt.time(hour, minute), SP_TZ), title))

    starts.sort(key=lambda entry: entry[0])
    lower_bound = now - dt.timedelta(hours=6)
    upper_bound = now + dt.timedelta(hours=48)
    programmes = []
    for index, (start, title) in enumerate(starts[:-1]):
        end = starts[index + 1][0]
        if end <= start or start >= upper_bound or end <= lower_bound:
            continue
        programme = ET.Element("programme", {
            "start": start.strftime("%Y%m%d%H%M%S %z"),
            "stop": end.strftime("%Y%m%d%H%M%S %z"),
            "channel": AMC_SERIES_CHANNEL,
        })
        ET.SubElement(programme, "title", {"lang": "pt"}).text = title
        programmes.append((programme.get("start", ""), title, ET.tostring(programme, encoding="unicode")))
    return programmes


def parse_xmltv_datetime(value):
    try:
        return dt.datetime.strptime(value[:20], "%Y%m%d%H%M%S %z").astimezone(dt.timezone.utc)
    except (TypeError, ValueError):
        return None


def normalize_programme_title(value):
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().upper()
    return "".join(char for char in value if char.isalnum())


def enrich_programme_metadata(programmes, target_names):
    """Copy missing metadata from matching channel/title entries without changing schedules."""
    current = {}
    current_by_title = defaultdict(list)
    for key, raw_programme in programmes.items():
        element = ET.fromstring(raw_programme)
        start = parse_xmltv_datetime(element.get("start"))
        title_key = normalize_programme_title(element.findtext("title", ""))
        if start and title_key:
            current[key] = element
            current_by_title[(key[0], title_key)].append((start, key))
    for entries in current_by_title.values():
        entries.sort(key=lambda entry: entry[0])

    raw = gzip.decompress(fetch(RICH_EPG_URL))
    source_map = {}
    for _, element in ET.iterparse(io.BytesIO(raw), events=("end",)):
        if element.tag == "channel":
            displays = [normalize((child.text or "").removeprefix("BR - ")) for child in element.findall("display-name")]
            source_id = element.get("id", "")
            source_label = source_id.rsplit(".", 1)[0] if source_id.lower().endswith(".br") else source_id
            displays.append(normalize(source_label))
            matched = {channel_id for display in displays for channel_id in target_names.get(display, [])}
            if len(matched) == 1:
                source_map[source_id] = matched.pop()
            element.clear()

    best_metadata = {}
    tolerance = dt.timedelta(minutes=5)
    starts_by_title = {key: [entry[0] for entry in entries] for key, entries in current_by_title.items()}
    for _, element in ET.iterparse(io.BytesIO(raw), events=("end",)):
        if element.tag == "programme":
            channel_id = source_map.get(element.get("channel", ""))
            start = parse_xmltv_datetime(element.get("start"))
            title_key = normalize_programme_title(element.findtext("title", ""))
            entries = current_by_title.get((channel_id, title_key), []) if channel_id and start and title_key else []
            if entries:
                starts = starts_by_title[(channel_id, title_key)]
                position = bisect_left(starts, start)
                candidates = entries[max(0, position - 1):min(len(entries), position + 1)]
                if candidates:
                    match_start, match_key = min(candidates, key=lambda entry: abs(entry[0] - start))
                    difference = abs(match_start - start)
                    if difference <= tolerance:
                        existing_tags = {
                            tag for tag in RICH_METADATA_TAGS
                            if any(any((part.text or "").strip() for part in child.iter()) or child.get("src") for child in current[match_key].findall(tag))
                        }
                        metadata = {}
                        for tag in RICH_METADATA_TAGS:
                            if tag not in existing_tags:
                                children = [
                                    child for child in element.findall(tag)
                                    if any((part.text or "").strip() for part in child.iter()) or child.get("src")
                                ]
                                if children:
                                    metadata[tag] = [ET.tostring(child, encoding="unicode") for child in children]
                        for tag, children in metadata.items():
                            old = best_metadata.get((match_key, tag))
                            if old is None or difference < old[0]:
                                best_metadata[(match_key, tag)] = (difference, children)
            element.clear()

    enriched = set()
    for (key, tag), (_, children) in best_metadata.items():
        for child in children:
            current[key].append(ET.fromstring(child))
        enriched.add(key)
    for key, element in current.items():
        if key in enriched:
            programmes[key] = ET.tostring(element, encoding="unicode")
    return len(enriched), Counter(tag for _, tag in best_metadata)


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
    target_name_by_id = {}
    for row in rows:
        key = normalize(ALIASES.get(row["TvvioId"], names.get(row["TvvioId"], row["Tvvio"])))
        target_names[key].append(row["TvvioId"])
        target_name_by_id[row["TvvioId"]] = key

    chosen = {}
    programmes = {}
    counts = defaultdict(int)
    source_for = {}
    starts_by_channel = defaultdict(list)
    intervals_by_channel = defaultdict(list)
    now = dt.datetime.now(dt.timezone.utc)
    window_start = now - dt.timedelta(hours=6)
    window_end = now + dt.timedelta(hours=48)
    all_sources = [(filename, BASE + filename) for filename in SOURCES] + EXTRA_SOURCES
    for filename, url in all_sources:
        allowed_targets = SOURCE_CHANNEL_ALLOWLIST.get(filename)
        blocked_targets = {channel_id for channel_id in (allowed_targets or ()) if counts[channel_id]}
        try:
            raw = get_bytes(filename) if url.startswith(BASE) else fetch(url)
        except Exception as error:
            print(f"Skipping unavailable source {filename}: {error}")
            continue
        if url.endswith(".gz"):
            try:
                raw = gzip.decompress(raw)
            except OSError as error:
                print(f"Skipping invalid compressed source {filename}: {error}")
                continue
        if raw.startswith(b"\xff\xfe"):
            raw = raw.decode("utf-16").encode("utf-8")
        elif raw.startswith(b"\xfe\xff"):
            raw = raw.decode("utf-16").encode("utf-8")
        elif len(raw) > 1 and raw[1] == 0:
            raw = raw.decode("utf-16-le").encode("utf-8")
        source_map = {}
        try:
            for _, element in ET.iterparse(io.BytesIO(raw), events=("end",)):
                if element.tag == "channel":
                    display_names = [normalize((child.text or "").removeprefix("BR - ")) for child in element.findall("display-name")]
                    source_id = element.get("id", "")
                    # Some XMLTV feeds omit display-name and identify the channel only by id.
                    source_label = source_id.rsplit(".", 1)[0] if source_id.lower().endswith(".br") else source_id
                    display_names.append(normalize(source_label))
                    matched = {channel_id for display in display_names for channel_id in target_names.get(display, [])}
                    if allowed_targets is not None:
                        matched &= allowed_targets
                    if len(matched) == 1:
                        source_map[source_id] = matched.pop()
                    element.clear()
            for _, element in ET.iterparse(io.BytesIO(raw), events=("end",)):
                if element.tag == "programme":
                    channel_id = source_map.get(element.get("channel", ""))
                    if channel_id and channel_id not in blocked_targets:
                        title = element.findtext("title", "")
                        start = parse_xmltv_datetime(element.get("start"))
                        stop = parse_xmltv_datetime(element.get("stop"))
                        if not start or not stop or stop <= start or stop <= window_start or start >= window_end:
                            element.clear()
                            continue
                        title_key = normalize(title)
                        target_key = target_name_by_id[channel_id]
                        if title_key in {target_key, "PROGRAMACAO" + target_key}:
                            element.clear()
                            continue
                        key = (channel_id, element.get("start", ""), title)
                        if key not in programmes:
                            starts = starts_by_channel[channel_id]
                            intervals = intervals_by_channel[channel_id]
                            position = bisect_left(starts, start)
                            overlaps_previous = position > 0 and intervals[position - 1][1] > start
                            overlaps_next = position < len(starts) and starts[position] < stop
                            if overlaps_previous or overlaps_next:
                                element.clear()
                                continue
                            starts.insert(position, start)
                            intervals.insert(position, (start, stop))
                            element.set("channel", channel_id)
                            programmes[key] = ET.tostring(element, encoding="unicode")
                            counts[channel_id] += 1
                            source_for.setdefault(channel_id, filename)
                    element.clear()
        except ET.ParseError as error:
            print(f"Skipping non-XMLTV source {filename}: {error}; first bytes={raw[:48]!r}")
        del raw

    try:
        for start, title, program_xml in fetch_amc_series_programmes():
            key = (AMC_SERIES_CHANNEL, start, title)
            if key not in programmes:
                start_dt = parse_xmltv_datetime(start)
                stop_dt = parse_xmltv_datetime(ET.fromstring(program_xml).get("stop"))
                if not start_dt or not stop_dt or stop_dt <= start_dt:
                    continue
                starts = starts_by_channel[AMC_SERIES_CHANNEL]
                intervals = intervals_by_channel[AMC_SERIES_CHANNEL]
                position = bisect_left(starts, start_dt)
                if position > 0 and intervals[position - 1][1] > start_dt:
                    continue
                if position < len(starts) and starts[position] < stop_dt:
                    continue
                starts.insert(position, start_dt)
                intervals.insert(position, (start_dt, stop_dt))
                programmes[key] = program_xml
                counts[AMC_SERIES_CHANNEL] += 1
                source_for.setdefault(AMC_SERIES_CHANNEL, "AMC Series Brasil official")
    except Exception as error:
        print(f"Skipping AMC Series Brasil source: {error}")

    try:
        enriched, metadata_counts = enrich_programme_metadata(programmes, target_names)
        print(f"Enriched {enriched} programmes from EPG-BR rich metadata: {dict(metadata_counts)}")
    except Exception as error:
        print(f"Skipping EPG-BR rich metadata: {error}")

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

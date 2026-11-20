#!/usr/bin/env python3
"""Validate generated XMLTV and report significant coverage drops."""

import argparse
import csv
import os
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

from build_epg import has_xml_content, parse_xmltv_datetime


METADATA_COLUMNS = (
    "Programas com capa",
    "Programas com descrição",
    "Programas com categoria",
    "Programas com classificação",
)
METADATA_TAGS = {
    "Programas com capa": "icon",
    "Programas com descrição": "desc",
    "Programas com categoria": "category",
    "Programas com classificação": "rating",
}
PROGRAMME_DROP_RATIO = 0.5
METADATA_DROP_RATIO = 0.5
MIN_BASE_PROGRAMMES = 20
MIN_BASE_METADATA = 10


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def emit_warning(message, warnings):
    warnings.append(message)
    escaped = message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A").replace(":", "%3A").replace(",", "%2C")
    print(f"::warning title=EPG quality::{escaped}")


def write_step_summary(errors, warnings, channel_count, programme_count):
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return
    lines = ["## Validação do EPG", "", f"- Canais: {channel_count}", f"- Programas: {programme_count}", f"- Erros estruturais: {len(errors)}", f"- Alertas de queda: {len(warnings)}", ""]
    if errors:
        lines.extend(["### Erros", ""] + [f"- {item}" for item in errors] + [""])
    if warnings:
        lines.extend(["### Alertas", ""] + [f"- {item}" for item in warnings] + [""])
    with open(summary_path, "a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def validate(xml_path, coverage_path, baseline_path=None):
    errors = []
    warnings = []
    try:
        root = ET.parse(xml_path).getroot()
    except (ET.ParseError, OSError) as error:
        print(f"Invalid XMLTV: {error}", file=sys.stderr)
        return 1
    if root.tag != "tv":
        print(f"Invalid XMLTV root element: expected 'tv', got {root.tag!r}", file=sys.stderr)
        return 1

    channel_ids = [channel.get("id", "") for channel in root.findall("channel")]
    channels = set(channel_ids)
    if "" in channels:
        errors.append("A channel has no id")
    duplicate_channels = sorted(channel_id for channel_id, count in Counter(channel_ids).items() if count > 1)
    if duplicate_channels:
        errors.append(f"Duplicate channel ids: {', '.join(duplicate_channels[:10])}")

    programmes = defaultdict(list)
    metadata_counts = defaultdict(Counter)
    programme_count = 0
    for programme in root.findall("programme"):
        programme_count += 1
        channel_id = programme.get("channel", "")
        if channel_id not in channels:
            errors.append(f"Programme references missing channel {channel_id!r}")
        start = parse_xmltv_datetime(programme.get("start"))
        stop = parse_xmltv_datetime(programme.get("stop"))
        title = programme.findtext("title", "")
        if start is None or stop is None or stop <= start:
            errors.append(f"Invalid programme interval for {channel_id}: {title!r}")
            continue
        programmes[channel_id].append((start, stop, title))
        for column, tag in METADATA_TAGS.items():
            if any(has_xml_content(child) for child in programme.findall(tag)):
                metadata_counts[channel_id][column] += 1

    overlaps = []
    for channel_id, entries in programmes.items():
        entries.sort(key=lambda item: item[0])
        for previous, current in zip(entries, entries[1:]):
            if current[0] < previous[1]:
                overlaps.append((channel_id, previous[2], current[2]))
    if overlaps:
        examples = "; ".join(f"{channel}: {left!r} / {right!r}" for channel, left, right in overlaps[:5])
        errors.append(f"Found {len(overlaps)} overlapping programme intervals; examples: {examples}")
    if programme_count == 0:
        errors.append("XMLTV contains no programmes")
    if channels != set(programmes):
        without_programmes = sorted(channels - set(programmes))
        errors.extend(f"Channel {channel_id!r} has no programmes" for channel_id in without_programmes[:10])

    try:
        current_rows = read_csv(coverage_path)
    except (OSError, csv.Error) as error:
        errors.append(f"Cannot read coverage CSV: {error}")
        current_rows = []
    current_by_id = {row.get("TvvioId", ""): row for row in current_rows}
    coverage_channels = set()
    for row in current_rows:
        channel_id = row.get("TvvioId", "")
        try:
            recorded = int(row.get("Programas", "0"))
        except ValueError:
            recorded = -1
        if recorded > 0:
            coverage_channels.add(channel_id)
        if (recorded > 0) != (row.get("Status") == "Correspondência"):
            errors.append(f"Coverage status/programme count mismatch for {channel_id}")
    if coverage_channels != channels:
        missing = sorted(coverage_channels - channels)
        unlisted = sorted(channels - coverage_channels)
        if missing:
            errors.append(f"Coverage lists channels absent from XMLTV: {', '.join(missing[:10])}")
        if unlisted:
            errors.append(f"XMLTV channels missing from coverage counts: {', '.join(unlisted[:10])}")
    for channel_id in channels:
        row = current_by_id.get(channel_id)
        if row is None:
            errors.append(f"Channel {channel_id!r} is missing from cobertura.csv")
            continue
        expected_programmes = len(programmes.get(channel_id, []))
        try:
            recorded_programmes = int(row.get("Programas", "0"))
        except ValueError:
            recorded_programmes = -1
        if recorded_programmes != expected_programmes:
            errors.append(f"Coverage CSV programme count mismatch for {channel_id}: {recorded_programmes} vs {expected_programmes}")
        for column in METADATA_COLUMNS:
            try:
                recorded = int(row.get(column, "0"))
            except ValueError:
                recorded = -1
            actual = metadata_counts[channel_id][column]
            if recorded != actual:
                errors.append(f"Coverage CSV {column!r} mismatch for {channel_id}: {recorded} vs {actual}")

    if baseline_path and baseline_path.exists():
        try:
            previous_rows = read_csv(baseline_path)
        except (OSError, csv.Error) as error:
            emit_warning(f"Could not read previous coverage snapshot: {error}", warnings)
            previous_rows = []
        previous_by_id = {row.get("TvvioId", ""): row for row in previous_rows}
        for channel_id, previous in previous_by_id.items():
            if previous.get("Status") != "Correspondência":
                continue
            current = current_by_id.get(channel_id)
            if current is None:
                emit_warning(f"{channel_id} disappeared from cobertura.csv", warnings)
                continue
            try:
                old_programmes = int(previous.get("Programas", "0"))
                new_programmes = int(current.get("Programas", "0"))
            except ValueError:
                continue
            if old_programmes > 0 and new_programmes == 0:
                emit_warning(f"{channel_id} lost all programmes (was {old_programmes})", warnings)
            elif old_programmes >= MIN_BASE_PROGRAMMES and new_programmes < old_programmes * (1 - PROGRAMME_DROP_RATIO):
                emit_warning(f"{channel_id} programme count dropped from {old_programmes} to {new_programmes}", warnings)
            for column in METADATA_COLUMNS:
                try:
                    old_value = int(previous.get(column, "0"))
                    new_value = int(current.get(column, "0"))
                except ValueError:
                    continue
                if old_value >= MIN_BASE_METADATA and new_value < old_value * (1 - METADATA_DROP_RATIO):
                    emit_warning(f"{channel_id} {column.lower()} dropped from {old_value} to {new_value}", warnings)
    else:
        print("No previous coverage snapshot; trend alerts skipped.")

    write_step_summary(errors, warnings, len(channels), programme_count)
    print(f"Validated XMLTV: {len(channels)} channels, {programme_count} programmes, {len(overlaps)} overlaps, {len(warnings)} trend warnings.")
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    return 1 if errors else 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--xml", type=Path, default=Path("epg.xml"))
    parser.add_argument("--coverage", type=Path, default=Path("cobertura.csv"))
    parser.add_argument("--baseline", type=Path)
    args = parser.parse_args()
    return validate(args.xml, args.coverage, args.baseline)


if __name__ == "__main__":
    raise SystemExit(main())

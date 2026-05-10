from __future__ import annotations

import json
import re
import shutil
import tempfile
import urllib.request
import zipfile
from collections.abc import Iterable
from html import unescape
from pathlib import Path

from defusedxml import ElementTree as ET

CONGRESS_SUMMARIES_COLLECTION = "congress_summaries"
GOVINFO_SUMMARY_DETAILS_URL = "https://www.govinfo.gov/app/details/BILLSUM-{congress}{bill_type}{bill_number}"
SUMMARY_ID_RE = re.compile(
    r"^id(?P<congress>\d+)(?P<bill_type>[a-z]+)(?P<bill_number>\d+)(?P<version>v\d+)$",
    re.IGNORECASE,
)
TAG_STRIPPER = re.compile(r"<[^>]+>")
WHITESPACE = re.compile(r"\s+")


def ingest_billsum(
    source: str | Path | None = None,
    *,
    source_url: str | None = None,
    collection_name: str = CONGRESS_SUMMARIES_COLLECTION,
    jsonl_out: str | Path | None = None,
) -> int:
    records = _apply_collection_name(
        load_billsum_records(source=source, source_url=source_url),
        collection_name=collection_name,
    )
    if jsonl_out is not None:
        write_jsonl(records, jsonl_out)
    return index_billsum_records(records, collection_name=collection_name)


def load_billsum_records(
    source: str | Path | None = None,
    *,
    source_url: str | None = None,
) -> list[dict]:
    if not source and not source_url:
        raise ValueError("Provide a local BILLSUM source path or source_url.")

    if source_url:
        with tempfile.TemporaryDirectory(prefix="alcove-congress-") as tmpdir:
            temp_path = Path(tmpdir) / (Path(source_url).name or "billsum.xml")
            download_file(source_url, temp_path)
            return load_billsum_records(source=temp_path)

    path = Path(source)
    if not path.exists():
        raise FileNotFoundError(path)
    if path.is_dir():
        return _load_billsum_records_from_directory(path)
    if path.suffix.lower() == ".zip":
        return _load_billsum_records_from_zip(path)
    if path.suffix.lower() == ".xml":
        return parse_billsum_xml(path.read_text(encoding="utf-8"), source=str(path))
    if path.suffix.lower() == ".jsonl":
        return _load_billsum_records_from_jsonl(path)
    raise ValueError(f"Unsupported BILLSUM source: {path}")


def parse_billsum_xml(xml_text: str, *, source: str = "billsum.xml") -> list[dict]:
    root = ET.fromstring(xml_text)
    if _find_all(root, "item"):
        return _parse_govinfo_billsum_items(root, source=source)
    return _parse_summary_nodes(root, source=source)


def index_billsum_records(
    records: Iterable[dict],
    *,
    collection_name: str = CONGRESS_SUMMARIES_COLLECTION,
) -> int:
    materialized = _apply_collection_name(records, collection_name=collection_name)
    if not materialized:
        return 0

    get_embedder, get_backend = _load_indexing_dependencies()
    embedder = get_embedder()
    backend = get_backend(embedder)
    documents = [record["document"] for record in materialized]
    metadatas = [dict(record["metadata"]) for record in materialized]

    backend.add(
        ids=[record["id"] for record in materialized],
        embeddings=embedder.embed(documents),
        documents=documents,
        metadatas=metadatas,
    )
    return len(materialized)


def write_jsonl(records: Iterable[dict], output_path: str | Path) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return output_path


def download_file(url: str, destination: str | Path) -> Path:
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url) as response, destination.open("wb") as fh:
        shutil.copyfileobj(response, fh)
    return destination


def _apply_collection_name(records: Iterable[dict], *, collection_name: str) -> list[dict]:
    normalized = []
    for record in records:
        metadata = dict(record["metadata"])
        metadata["collection"] = collection_name
        normalized.append(
            {
                "id": record["id"],
                "document": record["document"],
                "metadata": metadata,
            }
        )
    return normalized


def _load_billsum_records_from_directory(directory: Path) -> list[dict]:
    records: list[dict] = []
    for path in sorted(directory.rglob("*")):
        if path.is_dir():
            continue
        if path.suffix.lower() == ".xml":
            records.extend(parse_billsum_xml(path.read_text(encoding="utf-8"), source=str(path)))
        elif path.suffix.lower() == ".zip":
            records.extend(_load_billsum_records_from_zip(path))
    return records


def _load_billsum_records_from_zip(path: Path) -> list[dict]:
    records: list[dict] = []
    with zipfile.ZipFile(path) as archive:
        for member in sorted(archive.namelist()):
            if not member.lower().endswith(".xml"):
                continue
            xml_text = archive.read(member).decode("utf-8")
            records.extend(parse_billsum_xml(xml_text, source=f"{path}!{member}"))
    return records


def _load_billsum_records_from_jsonl(path: Path) -> list[dict]:
    records: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            raw = json.loads(line)
            if not isinstance(raw, dict):
                continue
            record_id = str(raw.get("id") or "").strip()
            document = str(raw.get("document") or "").strip()
            metadata = raw.get("metadata")
            if not record_id or not document or not isinstance(metadata, dict):
                continue
            records.append(
                {
                    "id": record_id,
                    "document": document,
                    "metadata": dict(metadata),
                }
            )
    return records


def _parse_govinfo_billsum_items(root: ET.Element, *, source: str) -> list[dict]:
    records: list[dict] = []
    for item in _find_all(root, "item"):
        congress = _coerce_int(item.attrib.get("congress") or _first_text(item, "congress"))
        bill_type = _normalize_bill_type(item.attrib.get("measure-type") or _first_text(item, "billType", "bill-type"))
        bill_number = _coerce_int(item.attrib.get("measure-number") or _first_text(item, "billNumber", "bill-number"))
        title = _first_text(item, "title")
        origin_chamber = (item.attrib.get("originChamber") or "").strip().upper()
        publish_date = (item.attrib.get("orig-publish-date") or "").strip()
        update_date = (item.attrib.get("update-date") or "").strip()

        if not congress or not bill_type or not bill_number:
            continue

        summaries = [node for node in item if _local_name(node.tag).lower() == "summary"]
        for index, summary in enumerate(summaries, start=1):
            version = _extract_summary_version(summary, fallback_index=index)
            action_date = _first_text(summary, "actionDate", "action-date")
            action_desc = _first_text(summary, "actionDesc", "action-desc")
            current_chamber = (summary.attrib.get("currentChamber") or "").strip().upper()
            body = _clean_summary_text(_extract_summary_text(summary))
            if not body:
                continue

            section = f"summary-{version}"
            display_title = title or f"{bill_type.upper()} {bill_number}"
            records.append(
                {
                    "id": f"bill-{congress}-{bill_type}-{bill_number}-{section}",
                    "document": f"{display_title}\n\n{body}",
                    "metadata": {
                        "source": source,
                        "collection": CONGRESS_SUMMARIES_COLLECTION,
                        "congress": str(congress),
                        "bill_type": bill_type,
                        "bill_number": str(bill_number),
                        "version": version,
                        "section": section,
                        "title": display_title,
                        "is_summary": True,
                        "date_issued": action_date or update_date or publish_date,
                        "action_desc": action_desc or "",
                        "origin_chamber": origin_chamber,
                        "current_chamber": current_chamber,
                        "publish_date": publish_date,
                        "update_date": update_date,
                        "url": GOVINFO_SUMMARY_DETAILS_URL.format(
                            congress=congress,
                            bill_type=bill_type,
                            bill_number=bill_number,
                        ),
                        "source_format": "govinfo-billsum-xml",
                    },
                }
            )
    return records


def _parse_summary_nodes(root: ET.Element, *, source: str) -> list[dict]:
    records: list[dict] = []
    root_congress = _first_text(root, "congress")

    for index, summary in enumerate(_find_all(root, "summary"), start=1):
        congress = _first_text(summary, "congress") or root_congress
        bill_type = _normalize_bill_type(_first_text(summary, "billType", "bill-type"))
        bill_number = _first_text(summary, "billNumber", "bill-number")
        title = _first_text(summary, "title") or _first_text(summary, "titles", "title")
        version = _first_text(summary, "version") or f"legacy-{index}"
        issued = _first_text(summary, "actionDate", "action-date", "updateDate", "update-date")
        body = _clean_summary_text(_first_text(summary, "text", "summaryText", "summary-text"))

        if not congress or not bill_type or not bill_number or not body:
            continue

        section = f"summary-{version}"
        records.append(
            {
                "id": f"bill-{congress}-{bill_type}-{bill_number}-{section}",
                "document": f"{title}\n\n{body}" if title else body,
                "metadata": {
                    "source": source,
                    "collection": CONGRESS_SUMMARIES_COLLECTION,
                    "congress": str(congress),
                    "bill_type": bill_type,
                    "bill_number": str(bill_number),
                    "version": version,
                    "section": section,
                    "title": title or f"{bill_type.upper()} {bill_number}",
                    "is_summary": True,
                    "date_issued": issued or "",
                    "url": GOVINFO_SUMMARY_DETAILS_URL.format(
                        congress=congress,
                        bill_type=bill_type,
                        bill_number=bill_number,
                    ),
                    "source_format": "govinfo-billsum-xml",
                },
            }
        )

    return records


def _extract_summary_text(summary: ET.Element) -> str:
    for name in ("summary-text", "summaryText", "text"):
        node = _first_node(summary, name)
        if node is not None:
            return "".join(node.itertext()).strip()
    return ""


def _extract_summary_version(summary: ET.Element, *, fallback_index: int) -> str:
    summary_id = (summary.attrib.get("summary-id") or "").strip()
    if summary_id:
        match = SUMMARY_ID_RE.match(summary_id)
        if match:
            return match.group("version").lower()
        version_match = re.search(r"(v\d+)$", summary_id, re.IGNORECASE)
        if version_match:
            return version_match.group(1).lower()

    version = _first_text(summary, "version")
    if version:
        return _normalize_version(version)

    return f"v{fallback_index:02d}"


def _load_indexing_dependencies():
    from alcove.index.backend import get_backend
    from alcove.index.embedder import get_embedder

    return get_embedder, get_backend


def _find_all(root: ET.Element, name: str) -> list[ET.Element]:
    target = name.lower()
    return [node for node in root.iter() if _local_name(node.tag).lower() == target]


def _first_node(root: ET.Element, *names: str) -> ET.Element | None:
    wanted = {name.lower() for name in names}
    for node in root.iter():
        if _local_name(node.tag).lower() in wanted:
            return node
    return None


def _first_text(root: ET.Element, *names: str) -> str | None:
    node = _first_node(root, *names)
    if node is None:
        return None
    text = "".join(node.itertext()).strip()
    return text or None


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _normalize_bill_type(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _normalize_version(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]", "", value.lower())
    return normalized or "v00"


def _coerce_int(value: str | None) -> int | None:
    if value is None:
        return None
    text = value.strip()
    if text.isdigit():
        return int(text)
    return None


def _clean_summary_text(value: str | None) -> str:
    if not value:
        return ""
    text = unescape(value)
    text = TAG_STRIPPER.sub(" ", text)
    return WHITESPACE.sub(" ", text).strip()

"""GovInfo BILLSTATUS ingest helpers for Alcove retrieval indexes."""

from __future__ import annotations

import json
import re
import shutil
import tempfile
import urllib.request
import zipfile
from collections.abc import Iterable
from pathlib import Path

from defusedxml import ElementTree as ET

CONGRESS_BILLSTATUS_COLLECTION = "congress_billstatus"
GOVINFO_BILLSTATUS_SITEMAP = (
    "https://www.govinfo.gov/sitemap/bulkdata/BILLSTATUS/{congress}{bill_type}/sitemap.xml"
)
CONGRESS_GOV_URL = "https://www.congress.gov/bill/{congress}th-congress/{chamber}/{bill_number}"


def ingest_billstatus(
    source: str | Path | None = None,
    *,
    source_url: str | None = None,
    congress: int | None = None,
    bill_type: str | None = None,
    collection_name: str = CONGRESS_BILLSTATUS_COLLECTION,
    jsonl_out: str | Path | None = None,
    limit: int | None = None,
) -> int:
    records = _apply_collection_name(
        load_billstatus_records(
            source=source,
            source_url=source_url,
            congress=congress,
            bill_type=bill_type,
            limit=limit,
        ),
        collection_name=collection_name,
    )
    if jsonl_out is not None:
        write_jsonl(records, jsonl_out)
    return index_billstatus_records(records, collection_name=collection_name)


def load_billstatus_records(
    source: str | Path | None = None,
    *,
    source_url: str | None = None,
    congress: int | None = None,
    bill_type: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    if source:
        return _load_from_source(Path(source), limit=limit)
    if source_url:
        return _load_from_url(source_url, limit=limit)
    if congress is not None and bill_type is not None:
        return _load_from_sitemap(congress, bill_type.lower(), limit=limit)
    raise ValueError("Provide a local source path, source_url, or both congress and bill_type.")


def parse_billstatus_xml(xml_text: str, *, source: str = "billstatus.xml") -> list[dict]:
    root = ET.fromstring(xml_text)
    bill = _first_node(root, "bill")
    if bill is None:
        return []
    return _parse_bill(bill, source=source)


def index_billstatus_records(
    records: Iterable[dict],
    *,
    collection_name: str = CONGRESS_BILLSTATUS_COLLECTION,
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


def _load_from_source(path: Path, limit: int | None = None) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(path)
    if path.is_dir():
        return _load_from_directory(path, limit=limit)
    if path.suffix.lower() == ".zip":
        return _load_from_zip(path, limit=limit)
    if path.suffix.lower() == ".xml":
        return parse_billstatus_xml(path.read_text(encoding="utf-8"), source=str(path))
    if path.suffix.lower() == ".jsonl":
        return _load_from_jsonl(path, limit=limit)
    raise ValueError(f"Unsupported BILLSTATUS source: {path}")


def _load_from_url(url: str, limit: int | None = None) -> list[dict]:
    with tempfile.TemporaryDirectory(prefix="alcove-billstatus-") as tmpdir:
        temp_path = Path(tmpdir) / (Path(url).name or "billstatus.xml")
        download_file(url, temp_path)
        return _load_from_source(temp_path, limit=limit)


def _load_from_directory(directory: Path, limit: int | None = None) -> list[dict]:
    records: list[dict] = []
    for path in sorted(directory.rglob("*")):
        if path.is_dir():
            continue
        if path.suffix.lower() == ".xml":
            records.extend(parse_billstatus_xml(path.read_text(encoding="utf-8"), source=str(path)))
        elif path.suffix.lower() == ".zip":
            records.extend(_load_from_zip(path))
        if limit is not None and len(records) >= limit:
            break
    return records[:limit] if limit is not None else records


def _load_from_zip(path: Path, limit: int | None = None) -> list[dict]:
    records: list[dict] = []
    with zipfile.ZipFile(path) as archive:
        for member in sorted(archive.namelist()):
            if not member.lower().endswith(".xml"):
                continue
            xml_text = archive.read(member).decode("utf-8")
            records.extend(parse_billstatus_xml(xml_text, source=f"{path}!{member}"))
            if limit is not None and len(records) >= limit:
                break
    return records[:limit] if limit is not None else records


def _load_from_jsonl(path: Path, limit: int | None = None) -> list[dict]:
    records: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            raw = json.loads(line)
            metadata = raw.get("metadata") if isinstance(raw, dict) else None
            if isinstance(raw, dict) and raw.get("id") and raw.get("document") and isinstance(metadata, dict):
                records.append({"id": str(raw["id"]), "document": str(raw["document"]), "metadata": dict(metadata)})
            if limit is not None and len(records) >= limit:
                break
    return records


def _load_from_sitemap(congress: int, bill_type: str, limit: int | None = None) -> list[dict]:
    sitemap_url = GOVINFO_BILLSTATUS_SITEMAP.format(congress=congress, bill_type=bill_type)
    with urllib.request.urlopen(sitemap_url, timeout=30) as response:
        sitemap_xml = response.read().decode("utf-8")

    sitemap_root = ET.fromstring(sitemap_xml)
    urls = [
        node.text.strip()
        for node in sitemap_root.iter()
        if _local_name(node.tag).lower() == "loc" and node.text and node.text.strip().endswith(".xml")
    ]

    records: list[dict] = []
    for url in urls:
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                xml_text = response.read().decode("utf-8")
            records.extend(parse_billstatus_xml(xml_text, source=url))
        except Exception:
            continue
        if limit is not None and len(records) >= limit:
            break
    return records[:limit] if limit is not None else records


def _parse_bill(bill: ET.Element, *, source: str) -> list[dict]:
    congress = _text(bill, "congress")
    bill_type = _normalize_bill_type(_text(bill, "type"))
    bill_number = _text(bill, "number")
    introduced_date = _text(bill, "introducedDate") or ""
    origin_chamber = _text(bill, "originChamber") or ""
    legislation_url = _text(bill, "legislationUrl") or ""
    update_date = _text(bill, "updateDate") or ""

    if not congress or not bill_type or not bill_number:
        return []

    title = _extract_display_title(bill) or _text(bill, "title") or f"{bill_type.upper()} {bill_number}"
    policy_area = _text_nested(bill, "policyArea", "name") or ""

    sponsor_node = _first_child_node(_first_node(bill, "sponsors"), "item")
    sponsor_name = _text(sponsor_node, "fullName") or "" if sponsor_node is not None else ""
    sponsor_party = _text(sponsor_node, "party") or "" if sponsor_node is not None else ""
    sponsor_state = _text(sponsor_node, "state") or "" if sponsor_node is not None else ""
    sponsor_bioguide = _text(sponsor_node, "bioguideId") or "" if sponsor_node is not None else ""

    cosponsor_items = _find_all(_first_node(bill, "cosponsors"), "item")
    cosponsor_names = "; ".join(_text(cosponsor, "fullName") or "" for cosponsor in cosponsor_items[:10])

    committees_node = _first_node(bill, "committees")
    top_level_committees: list[str] = []
    if committees_node is not None:
        for item in committees_node:
            if _local_name(item.tag).lower() == "item":
                name = _text(item, "name")
                if name:
                    top_level_committees.append(name)
    committees = "; ".join(top_level_committees)

    action_items = _find_all(_first_node(bill, "actions"), "item")
    actions_summary = _extract_actions(action_items)
    latest_action_node = _direct_child(bill, "latestAction")
    latest_action_date = _text(latest_action_node, "actionDate") or "" if latest_action_node is not None else ""
    latest_action_text = _text(latest_action_node, "text") or "" if latest_action_node is not None else ""
    status = _derive_status(latest_action_text, action_items)
    related_count = len(_find_all(_first_node(bill, "relatedBills"), "item"))

    document_parts = [title]
    if sponsor_name:
        document_parts.append(f"Sponsor: {sponsor_name}")
    if committees:
        document_parts.append(f"Committees: {committees}")
    if policy_area:
        document_parts.append(f"Policy area: {policy_area}")
    if latest_action_text:
        document_parts.append(f"Latest action ({latest_action_date}): {latest_action_text}")
    if actions_summary:
        document_parts.append(f"Actions: {actions_summary}")

    bill_id = f"billstatus-{congress}-{bill_type}-{bill_number}"
    return [
        {
            "id": bill_id,
            "document": "\n".join(document_parts),
            "metadata": {
                "source": source,
                "collection": CONGRESS_BILLSTATUS_COLLECTION,
                "congress": str(congress),
                "bill_type": bill_type,
                "bill_number": str(bill_number),
                "bill_id": bill_id,
                "title": title,
                "introduced_date": introduced_date,
                "origin_chamber": origin_chamber,
                "update_date": update_date,
                "sponsor_name": sponsor_name,
                "sponsor_party": sponsor_party,
                "sponsor_state": sponsor_state,
                "sponsor_bioguide": sponsor_bioguide,
                "cosponsor_count": str(len(cosponsor_items)),
                "cosponsor_names": cosponsor_names,
                "committees": committees,
                "policy_area": policy_area,
                "latest_action_date": latest_action_date,
                "latest_action_text": latest_action_text,
                "status": status,
                "action_count": str(len(action_items)),
                "related_bill_count": str(related_count),
                "url": legislation_url or _build_congress_url(congress, bill_type, bill_number, origin_chamber),
                "source_format": "govinfo-billstatus-xml",
            },
        }
    ]


def _extract_display_title(bill: ET.Element) -> str | None:
    titles_node = _first_node(bill, "titles")
    if titles_node is None:
        return None
    for item in titles_node:
        if _local_name(item.tag).lower() != "item":
            continue
        title_type = _text(item, "titleType") or ""
        if "display" in title_type.lower():
            return _text(item, "title")
    for item in titles_node:
        if _local_name(item.tag).lower() == "item":
            return _text(item, "title")
    return None


def _extract_actions(action_items: list[ET.Element]) -> str:
    parts = []
    for item in action_items[-5:]:
        date = _text(item, "actionDate") or ""
        text = _text(item, "text") or ""
        if text:
            parts.append(f"{date}: {text}" if date else text)
    return "; ".join(parts)


def _derive_status(latest_action_text: str, action_items: list[ET.Element]) -> str:
    text = (latest_action_text or "").lower()
    if "became public law" in text or "signed by president" in text:
        return "enacted"
    if "passed" in text and "senate" in text:
        return "passed-senate"
    if "passed" in text and "house" in text:
        return "passed-house"
    if "failed" in text or "defeated" in text:
        return "failed"
    if "vetoed" in text:
        return "vetoed"
    if "referred" in text:
        return "referred"
    if action_items:
        return "active"
    return "unknown"


def _build_congress_url(congress: str, bill_type: str, bill_number: str, origin_chamber: str) -> str:
    chamber_map = {
        "house": "house-bill",
        "senate": "senate-bill",
        "h": "house-bill",
        "s": "senate-bill",
    }
    chamber = chamber_map.get((origin_chamber or "").lower(), "house-bill")
    return CONGRESS_GOV_URL.format(congress=congress, chamber=chamber, bill_number=bill_number)


def _apply_collection_name(records: Iterable[dict], *, collection_name: str) -> list[dict]:
    normalized = []
    for record in records:
        metadata = dict(record["metadata"])
        metadata["collection"] = collection_name
        normalized.append({"id": record["id"], "document": record["document"], "metadata": metadata})
    return normalized


def _load_indexing_dependencies():
    from alcove.index.backend import get_backend
    from alcove.index.embedder import get_embedder

    return get_embedder, get_backend


def _find_all(root: ET.Element | None, name: str) -> list[ET.Element]:
    if root is None:
        return []
    target = name.lower()
    return [node for node in root.iter() if _local_name(node.tag).lower() == target]


def _first_node(root: ET.Element | None, *names: str) -> ET.Element | None:
    if root is None:
        return None
    wanted = {name.lower() for name in names}
    for node in root.iter():
        if _local_name(node.tag).lower() in wanted:
            return node
    return None


def _first_child_node(root: ET.Element | None, name: str) -> ET.Element | None:
    if root is None:
        return None
    target = name.lower()
    for child in root:
        if _local_name(child.tag).lower() == target:
            return child
    return None


def _direct_child(root: ET.Element | None, name: str) -> ET.Element | None:
    if root is None:
        return None
    target = name.lower()
    for child in root:
        if _local_name(child.tag).lower() == target:
            return child
    return None


def _text(root: ET.Element | None, *names: str) -> str | None:
    node = _first_node(root, *names)
    if node is None:
        return None
    text = "".join(node.itertext()).strip()
    return text or None


def _text_nested(root: ET.Element | None, parent_name: str, child_name: str) -> str | None:
    parent = _first_node(root, parent_name)
    if parent is None:
        return None
    return _text(parent, child_name)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _normalize_bill_type(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"[^a-z0-9]", "", value.lower())

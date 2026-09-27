"""Fetch real PubMed and ClinicalTrials.gov records into data/corpus.json.

Runtime services only read the resulting committed file. Failed or unavailable
network calls are skipped; the deterministic fallback corpus is an empty list.
"""

from __future__ import annotations

import json
import os
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_PATH = ROOT / "data" / "corpus.json"
TIMEOUT_SECONDS = 10.0
RETRIES = 3
MAX_PER_SOURCE = 50

# Four focused query pairs per condition keep the corpus compact and useful.
QUERY_PAIRS = [
    ("Oncology", "Breast cancer", "clinical trials"),
    ("Oncology", "Breast cancer", "treatment sequencing"),
    ("Oncology", "Breast cancer", "guideline update"),
    ("Oncology", "Breast cancer", "monitoring"),
    ("Oncology", "Lung cancer", "clinical trials"),
    ("Oncology", "Lung cancer", "treatment sequencing"),
    ("Oncology", "Lung cancer", "guideline update"),
    ("Oncology", "Lung cancer", "monitoring"),
    ("Cardiology", "Heart failure", "clinical trials"),
    ("Cardiology", "Heart failure", "treatment sequencing"),
    ("Cardiology", "Heart failure", "guideline update"),
    ("Cardiology", "Heart failure", "monitoring"),
    ("Cardiology", "Atrial fibrillation", "clinical trials"),
    ("Cardiology", "Atrial fibrillation", "treatment sequencing"),
    ("Cardiology", "Atrial fibrillation", "guideline update"),
    ("Cardiology", "Atrial fibrillation", "monitoring"),
    ("Endocrinology", "Type 2 diabetes", "clinical trials"),
    ("Endocrinology", "Type 2 diabetes", "treatment sequencing"),
    ("Endocrinology", "Type 2 diabetes", "guideline update"),
    ("Endocrinology", "Type 2 diabetes", "monitoring"),
    ("Endocrinology", "Obesity", "clinical trials"),
    ("Endocrinology", "Obesity", "treatment sequencing"),
    ("Endocrinology", "Obesity", "guideline update"),
    ("Endocrinology", "Obesity", "monitoring"),
]
PUBMED_SEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_FETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
TRIALS_SEARCH = "https://clinicaltrials.gov/api/v2/studies"


def _get(client: httpx.Client, url: str, params: dict[str, Any]) -> httpx.Response:
    last_error: Exception | None = None
    for attempt in range(RETRIES):
        try:
            response = client.get(url, params=params)
            response.raise_for_status()
            return response
        except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as exc:
            last_error = exc
            if attempt + 1 < RETRIES:
                time.sleep(0.25 * (2 ** attempt))
    assert last_error is not None
    raise last_error


def _ncbi_params() -> dict[str, str]:
    params = {}
    tool = os.getenv("NCBI_TOOL", "")
    email = os.getenv("NCBI_EMAIL", "")
    if tool:
        params["tool"] = tool
    if email:
        params["email"] = email
    return params


def _specialty_for_condition(condition: str) -> str:
    return next((specialty for specialty, conditions in {
        "Oncology": ["Breast cancer", "Lung cancer"],
        "Cardiology": ["Heart failure", "Atrial fibrillation"],
        "Endocrinology": ["Type 2 diabetes", "Obesity"],
    }.items() if condition in conditions), "Other")


def fetch_pubmed(client: httpx.Client, specialty: str, condition: str, topic: str) -> list[dict]:
    params = {**_ncbi_params(), "db": "pubmed", "term": f'("{condition}"[Title/Abstract]) AND ({topic}[Title/Abstract]) AND ("last 5 years"[PDat])',
              "retmax": "5", "sort": "relevance", "retmode": "json"}
    search = _get(client, PUBMED_SEARCH, params).json()
    ids = search.get("esearchresult", {}).get("idlist", [])
    if not ids:
        return []
    # E-utilities rate limit: stay comfortably below three calls/second.
    time.sleep(0.34)
    xml = _get(client, PUBMED_FETCH, {**_ncbi_params(), "db": "pubmed", "id": ",".join(ids), "retmode": "xml"}).text
    root = ET.fromstring(xml)
    records = []
    for article in root.findall(".//PubmedArticle"):
        pmid = (article.findtext(".//PMID") or "").strip()
        title = " ".join("".join(article.find(".//ArticleTitle").itertext()).split()) if article.find(".//ArticleTitle") is not None else ""
        journal = " ".join((article.findtext(".//Journal/Title") or "").split())
        abstract_parts = [" ".join("".join(item.itertext()).split()) for item in article.findall(".//Abstract/AbstractText")]
        abstract = " ".join(part for part in abstract_parts if part)
        date_node = article.find(".//PubDate")
        date = " ".join((date_node.findtext(key) or "").strip() for key in ("Year", "Month", "Day") if date_node is not None and date_node.findtext(key)) if date_node is not None else ""
        if not (pmid and title and abstract):
            continue
        records.append({"external_id": f"PMID:{pmid}", "title": title, "source_type": "PubMed abstract",
                        "date": date or None, "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                        "citation": f"{journal}. {date}. PMID: {pmid}".strip(" ."), "publisher": journal or "PubMed",
                        "specialty": specialty, "condition": condition, "topics": [topic], "verified": True,
                        "full_text": abstract})
    return records


def fetch_clinical_trials(client: httpx.Client, specialty: str, condition: str, topic: str) -> list[dict]:
    payload = _get(client, TRIALS_SEARCH, {"query.cond": condition, "query.term": topic, "pageSize": "3",
                                           "format": "json"}).json()
    records = []
    for study in payload.get("studies", []):
        protocol = study.get("protocolSection", {})
        identification = protocol.get("identificationModule", {})
        status = protocol.get("statusModule", {})
        description = protocol.get("descriptionModule", {})
        nct_id = identification.get("nctId")
        title = identification.get("briefTitle") or identification.get("officialTitle")
        summary = description.get("briefSummary")
        if not (nct_id and title and summary):
            continue
        date = status.get("studyFirstSubmitDate") or status.get("studyFirstPostDate") or status.get("studyLastUpdatePostDate")
        records.append({"external_id": nct_id, "title": title, "source_type": "Clinical trial registry",
                        "date": date, "url": f"https://clinicaltrials.gov/study/{nct_id}",
                        "citation": f"ClinicalTrials.gov. {nct_id}", "publisher": "ClinicalTrials.gov",
                        "specialty": specialty, "condition": condition, "topics": [topic], "verified": True,
                        "full_text": summary.strip()})
    return records


def fetch_corpus(client: httpx.Client | None = None) -> list[dict]:
    owned_client = client is None
    client = client or httpx.Client(timeout=httpx.Timeout(TIMEOUT_SECONDS), headers={"User-Agent": "PULSEPOINT-HackGT13/1.0"})
    records: list[dict] = []
    seen: set[str] = set()
    records_by_id: dict[str, dict] = {}
    source_counts = {"PubMed abstract": 0, "Clinical trial registry": 0}
    try:
        for specialty, condition, topic in QUERY_PAIRS:
            for source_name, fetcher in (("PubMed abstract", fetch_pubmed), ("Clinical trial registry", fetch_clinical_trials)):
                if source_counts[source_name] >= MAX_PER_SOURCE:
                    continue
                try:
                    fetched = fetcher(client, specialty, condition, topic)
                except (httpx.HTTPError, ET.ParseError, ValueError, KeyError) as exc:
                    print(f"Skipping {source_name} query for {condition}/{topic}: {exc}")
                    continue
                for record in fetched:
                    identifier = record["external_id"]
                    if identifier in seen:
                        existing = records_by_id[identifier]
                        for matched_topic in record.get("topics", []):
                            if matched_topic not in existing.setdefault("topics", []):
                                existing["topics"].append(matched_topic)
                        continue
                    if source_counts[source_name] >= MAX_PER_SOURCE:
                        continue
                    seen.add(identifier)
                    records_by_id[identifier] = record
                    records.append(record)
                    source_counts[source_name] += 1
    finally:
        if owned_client:
            client.close()
    return records


def write_corpus(records: list[dict], output_path: Path = OUTPUT_PATH) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    try:
        records = fetch_corpus()
    except (httpx.HTTPError, OSError) as exc:
        print(f"Corpus fetch unavailable; writing deterministic empty fallback: {exc}")
        records = []
    if not records and OUTPUT_PATH.exists():
        # Preserve the committed deterministic corpus when the live APIs are
        # unavailable, rather than replacing useful offline data with nothing.
        try:
            existing = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
            if isinstance(existing, list):
                records = existing
                print("No live records fetched; preserving committed offline corpus.")
        except (OSError, json.JSONDecodeError):
            pass
    write_corpus(records)
    print(f"Wrote {len(records)} verified records to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

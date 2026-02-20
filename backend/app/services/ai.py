from datetime import datetime
from html import unescape
import io
from pathlib import Path
import json
import re
import time
import zipfile
from typing import Any
from collections import Counter

import httpx
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entities import (
    AiAuditLog,
    ChecklistItem,
    ChecklistVersion,
    MarketSignal,
    Milestone,
    Proof,
    Skill,
    StudentProfile,
    UserPathway,
)
from app.services.readiness import calculate_readiness
from app.services.storage import is_s3_object_url, read_s3_object_bytes

MAX_EVIDENCE_CHARS = 4000
MAX_RESUME_CONTEXT_CHARS = 12000
MAX_RESUME_READ_BYTES = 250000
SUPPORTED_LLM_PROVIDERS = {"groq", "openai"}
RESUME_MATCH_PROOF_TYPE = "resume_upload_match"
RESUME_MATCH_THRESHOLD = 0.65
AI_EVIDENCE_MAP_PROOF_TYPE = "ai_evidence_map"
AI_EVIDENCE_MAP_THRESHOLD = 0.66
MARKET_SIGNAL_LOOKBACK_LIMIT = 600
MARKET_GUIDE_SKILLS_LIMIT = 6
MARKET_TOKEN_STOPWORDS = {
    "and",
    "the",
    "for",
    "with",
    "from",
    "into",
    "that",
    "this",
    "your",
    "have",
    "has",
    "are",
    "was",
    "were",
    "their",
    "them",
    "will",
    "used",
    "using",
    "data",
    "skills",
    "skill",
    "basic",
    "basics",
    "fundamentals",
}
GENERAL_PROOF_TYPES = [
    "portfolio",
    "project_doc",
    "certificate",
    "internship_letter",
    "resume_upload",
]


def _truncate(text: str, limit: int = MAX_EVIDENCE_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def _clean_text(raw: str, limit: int = MAX_EVIDENCE_CHARS) -> str:
    cleaned = re.sub(r"\s+", " ", raw).strip()
    return _truncate(cleaned, limit=limit)


def _extract_text_from_bytes(blob: bytes, *, limit: int = MAX_EVIDENCE_CHARS) -> str | None:
    if not blob:
        return None
    try:
        text = blob.decode("utf-8", errors="ignore")
    except Exception:
        return None
    if not text.strip():
        return None
    printable = sum(ch.isprintable() for ch in text)
    ratio = printable / max(len(text), 1)
    if ratio < 0.6:
        return None
    return _clean_text(text, limit=limit)


def _extract_local_file_text(
    path: Path,
    *,
    read_bytes: int = 20000,
    limit: int = MAX_EVIDENCE_CHARS,
) -> str | None:
    try:
        with path.open("rb") as handle:
            blob = handle.read(read_bytes)
        return _extract_text_from_bytes(blob, limit=limit)
    except Exception:
        return None


def _extract_docx_text(path: Path) -> str | None:
    try:
        with zipfile.ZipFile(path) as archive:
            with archive.open("word/document.xml") as document:
                xml = document.read().decode("utf-8", errors="ignore")
    except Exception:
        return None
    text = re.sub(r"<[^>]+>", " ", xml)
    return _clean_text(unescape(text), limit=MAX_RESUME_CONTEXT_CHARS)


def _extract_pdf_text(path: Path) -> str | None:
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception:
        return None
    try:
        reader = PdfReader(str(path))
        parts: list[str] = []
        for page in reader.pages[:10]:
            page_text = page.extract_text() or ""
            if page_text:
                parts.append(page_text)
        if not parts:
            return None
        return _clean_text("\n".join(parts), limit=MAX_RESUME_CONTEXT_CHARS)
    except Exception:
        return None


def _extract_resume_file_text(path: Path) -> str | None:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md", ".rtf", ".csv", ".json"}:
        return _extract_local_file_text(
            path,
            read_bytes=MAX_RESUME_READ_BYTES,
            limit=MAX_RESUME_CONTEXT_CHARS,
        )
    if suffix == ".docx":
        parsed = _extract_docx_text(path)
        if parsed:
            return parsed
    if suffix == ".pdf":
        parsed = _extract_pdf_text(path)
        if parsed:
            return parsed
    return _extract_local_file_text(
        path,
        read_bytes=MAX_RESUME_READ_BYTES,
        limit=MAX_RESUME_CONTEXT_CHARS,
    )


def _extract_resume_blob_text(blob: bytes, suffix: str) -> str | None:
    if suffix in {".txt", ".md", ".rtf", ".csv", ".json"}:
        return _extract_text_from_bytes(blob, limit=MAX_RESUME_CONTEXT_CHARS)
    if suffix == ".docx":
        try:
            with zipfile.ZipFile(io.BytesIO(blob)) as archive:
                with archive.open("word/document.xml") as document:
                    xml = document.read().decode("utf-8", errors="ignore")
            text = re.sub(r"<[^>]+>", " ", xml)
            return _clean_text(unescape(text), limit=MAX_RESUME_CONTEXT_CHARS)
        except Exception:
            return None
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader  # type: ignore
        except Exception:
            return None
        try:
            reader = PdfReader(io.BytesIO(blob))
            parts: list[str] = []
            for page in reader.pages[:10]:
                page_text = page.extract_text() or ""
                if page_text:
                    parts.append(page_text)
            if not parts:
                return None
            return _clean_text("\n".join(parts), limit=MAX_RESUME_CONTEXT_CHARS)
        except Exception:
            return None
    return _extract_text_from_bytes(blob, limit=MAX_RESUME_CONTEXT_CHARS)


def _fetch_url_text(url: str) -> tuple[str | None, dict | None]:
    headers = {"User-Agent": "MarketPathwaysVerifier/1.0"}
    try:
        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            response = client.get(url, headers=headers)
            content_type = response.headers.get("content-type")
            text = None
            if "text" in (content_type or "") or "json" in (content_type or ""):
                text = _clean_text(response.text, limit=MAX_EVIDENCE_CHARS)
            else:
                text = _extract_text_from_bytes(
                    response.content[:20000],
                    limit=MAX_EVIDENCE_CHARS,
                )
            return text, {"status_code": response.status_code, "content_type": content_type}
    except Exception:
        return None, None


def _normalize_provider() -> str:
    provider = (settings.llm_provider or "groq").strip().lower()
    if provider not in SUPPORTED_LLM_PROVIDERS:
        return "groq"
    return provider


def _provider_config() -> tuple[str, str | None, str, str]:
    provider = _normalize_provider()
    if provider == "openai":
        return (
            provider,
            settings.openai_api_key,
            settings.openai_model,
            settings.openai_api_base.rstrip("/"),
        )
    return (
        "groq",
        settings.groq_api_key,
        settings.groq_model,
        settings.groq_api_base.rstrip("/"),
    )


def _is_certificate_proof_type(proof_type: str) -> bool:
    normalized = (proof_type or "").strip().lower()
    return normalized == "cert_upload" or "cert" in normalized


def _extract_resume_context(profile: StudentProfile | None) -> dict[str, Any] | None:
    if not profile or not getattr(profile, "resume_url", None):
        return None

    resume_url = profile.resume_url
    resume_text = None
    resume_meta: dict[str, Any] = {
        "resume_url": resume_url,
        "resume_filename": getattr(profile, "resume_filename", None),
        "resume_uploaded_at": (
            profile.resume_uploaded_at.isoformat()
            if getattr(profile, "resume_uploaded_at", None)
            else None
        ),
    }
    if resume_url.startswith("/uploads/"):
        local_path = Path(settings.local_upload_dir) / resume_url.removeprefix("/uploads/")
        resume_text = _extract_resume_file_text(local_path)
        resume_meta["source"] = "local_upload"
    elif is_s3_object_url(resume_url):
        blob = read_s3_object_bytes(resume_url, max_bytes=MAX_RESUME_READ_BYTES)
        suffix = Path((getattr(profile, "resume_filename", "") or resume_url)).suffix.lower()
        resume_text = _extract_resume_blob_text(blob, suffix) if blob else None
        resume_meta["source"] = "s3_object"
    elif resume_url.startswith("http://") or resume_url.startswith("https://"):
        fetched_text, fetched_meta = _fetch_url_text(resume_url)
        resume_text = _truncate(fetched_text or "", limit=MAX_RESUME_CONTEXT_CHARS) if fetched_text else None
        if fetched_meta:
            resume_meta["fetch_meta"] = fetched_meta
        resume_meta["source"] = "url_fetch"
    else:
        resume_meta["source"] = "unknown"

    if resume_text:
        resume_meta["resume_excerpt"] = resume_text
    return resume_meta


def _resume_keyword_fallback(
    resume_text: str,
    items: list[ChecklistItem],
) -> list[dict[str, Any]]:
    stop_words = {
        "with",
        "from",
        "into",
        "your",
        "that",
        "this",
        "and",
        "for",
        "the",
        "or",
        "to",
    }
    tokens = set(re.findall(r"[a-z0-9]+", resume_text.lower()))
    matches: list[dict[str, Any]] = []
    for item in items:
        title_tokens = [
            token
            for token in re.findall(r"[a-z0-9]+", (item.title or "").lower())
            if len(token) > 3 and token not in stop_words
        ]
        if not title_tokens:
            continue
        hits = sum(1 for token in title_tokens if token in tokens)
        coverage = hits / max(len(title_tokens), 1)
        if coverage >= 0.7:
            matches.append(
                {
                    "item_id": str(item.id),
                    "confidence": min(0.9, 0.7 + coverage * 0.2),
                    "rationale": "Resume text strongly overlaps this checklist requirement.",
                }
            )
    return matches


def _generate_resume_matches_with_llm(
    *,
    resume_context: dict[str, Any],
    items: list[ChecklistItem],
) -> dict[str, Any]:
    system = (
        "You analyze a student's resume against checklist requirements. "
        "Be conservative: only mark a requirement satisfied when resume evidence is explicit. "
        "Output a single JSON object with keys: "
        "matches (array of objects with item_id, confidence (0 to 1), rationale), "
        "uncertainty (string or null)."
    )
    payload = {
        "resume_context": resume_context,
        "checklist_items": [
            {
                "id": str(item.id),
                "title": item.title,
                "description": item.description,
                "tier": item.tier,
                "rationale": item.rationale,
            }
            for item in items
        ],
    }
    raw = _call_llm(system, json.dumps(payload))
    parsed = _safe_json(raw)
    return parsed or {"matches": [], "uncertainty": "AI output parse failure."}


def _evaluate_resume_matches(
    *,
    resume_context: dict[str, Any] | None,
    items: list[ChecklistItem],
) -> tuple[list[dict[str, Any]], str]:
    if not resume_context:
        return [], "no_resume"
    resume_text = (resume_context.get("resume_excerpt") or "").strip()
    if not resume_text:
        return [], "no_resume_text"

    valid_ids = {str(item.id) for item in items}
    threshold = RESUME_MATCH_THRESHOLD

    if ai_is_configured():
        try:
            parsed = _generate_resume_matches_with_llm(
                resume_context=resume_context,
                items=items,
            )
            matches: list[dict[str, Any]] = []
            for row in parsed.get("matches", []):
                item_id = str(row.get("item_id", ""))
                if item_id not in valid_ids:
                    continue
                confidence = float(row.get("confidence", 0.0))
                if confidence < threshold:
                    continue
                rationale = str(row.get("rationale") or "Matched by resume evidence.")
                matches.append(
                    {
                        "item_id": item_id,
                        "confidence": confidence,
                        "rationale": rationale,
                    }
                )
            return matches, "ai"
        except Exception:
            pass

    fallback = _resume_keyword_fallback(resume_text, items)
    return fallback, "rules"


def _rules_resume_feedback(
    *,
    resume_context: dict[str, Any] | None,
    gap_items: list[ChecklistItem],
) -> tuple[list[str], list[str]]:
    if not resume_context:
        return [], []

    resume_excerpt = (resume_context.get("resume_excerpt") or "").strip()
    if not resume_excerpt:
        return (
            [
                "Upload a text-readable resume (PDF/DOCX/TXT) so AI can analyze specific bullets and achievements."
            ],
            [],
        )

    lowered = resume_excerpt.lower()
    improvements: list[str] = []
    strengths: list[str] = []

    if re.search(r"\b\d+[%xkmb]?\b", lowered):
        strengths.append("You already include measurable outcomes, which strengthens your resume.")
    else:
        improvements.append("Add quantified outcomes (numbers, percentages, impact) to your project bullets.")

    if "github.com" in lowered or "portfolio" in lowered or "deployed" in lowered:
        strengths.append("You reference project artifacts, which helps verification.")
    else:
        improvements.append("Add GitHub/portfolio/deployed links for key projects to make evidence easier to verify.")

    if "full-stack" in lowered or "full stack" in lowered:
        strengths.append("You mention full-stack experience, which is strong market evidence.")

    for gap in gap_items[:3]:
        improvements.append(
            f"Add a bullet explicitly proving '{gap.title}' with tools used and final outcomes."
        )

    improvements = _unique_list(improvements)[:5]
    strengths = _unique_list(strengths)[:4]
    return improvements, strengths


def _extract_proof_evidence_excerpt(proof: Proof) -> tuple[str | None, dict[str, Any]]:
    meta: dict[str, Any] = {}
    evidence_text: str | None = None
    url = proof.url or ""

    if url.startswith("/uploads/"):
        local_path = Path(settings.local_upload_dir) / url.removeprefix("/uploads/")
        evidence_text = _extract_resume_file_text(local_path) or _extract_local_file_text(local_path)
        meta["source"] = "local_upload"
    elif is_s3_object_url(url):
        blob = read_s3_object_bytes(url, max_bytes=MAX_RESUME_READ_BYTES)
        suffix_hint = Path(
            str((proof.metadata_json or {}).get("filename") or (proof.metadata_json or {}).get("name") or url)
        ).suffix.lower()
        evidence_text = _extract_resume_blob_text(blob, suffix_hint) if blob else None
        meta["source"] = "s3_object"
    elif url.startswith("http://") or url.startswith("https://"):
        fetched_text, fetched_meta = _fetch_url_text(url)
        evidence_text = fetched_text
        if fetched_meta:
            meta.update(fetched_meta)
        meta["source"] = "url_fetch"
    else:
        meta["source"] = "metadata_only"

    metadata_payload = proof.metadata_json if isinstance(proof.metadata_json, dict) else None
    metadata_text = (
        _clean_text(json.dumps(metadata_payload, ensure_ascii=False), limit=1200)
        if metadata_payload
        else None
    )

    if evidence_text and metadata_text:
        return _clean_text(f"{metadata_text} {evidence_text}", limit=MAX_EVIDENCE_CHARS), meta
    if evidence_text:
        return _clean_text(evidence_text, limit=MAX_EVIDENCE_CHARS), meta
    if metadata_text:
        return metadata_text, meta
    return None, meta


def _rule_map_evidence_to_items(
    *,
    evidence_rows: list[dict[str, Any]],
    target_items: list[ChecklistItem],
) -> list[dict[str, Any]]:
    stop_words = {
        "with",
        "from",
        "into",
        "your",
        "that",
        "this",
        "and",
        "for",
        "the",
        "or",
        "to",
        "requirement",
    }
    evidence_tokens: dict[str, set[str]] = {}
    for row in evidence_rows:
        evidence_tokens[row["proof_id"]] = set(
            token for token in re.findall(r"[a-z0-9]+", (row.get("evidence_excerpt") or "").lower()) if len(token) > 2
        )

    matches: list[dict[str, Any]] = []
    for item in target_items:
        item_tokens = [
            token
            for token in re.findall(
                r"[a-z0-9]+",
                f"{item.title or ''} {item.description or ''} {item.rationale or ''}".lower(),
            )
            if len(token) > 3 and token not in stop_words
        ]
        if not item_tokens:
            continue

        best_proof_id: str | None = None
        best_coverage = 0.0
        for row in evidence_rows:
            tokens = evidence_tokens.get(row["proof_id"], set())
            if not tokens:
                continue
            hits = sum(1 for token in item_tokens if token in tokens)
            coverage = hits / max(len(item_tokens), 1)
            if coverage > best_coverage:
                best_coverage = coverage
                best_proof_id = row["proof_id"]

        if best_proof_id and best_coverage >= 0.58:
            confidence = min(0.95, 0.52 + best_coverage * 0.45)
            matches.append(
                {
                    "item_id": str(item.id),
                    "source_proof_id": best_proof_id,
                    "confidence": confidence,
                    "rationale": "Evidence text strongly overlaps this requirement.",
                }
            )
    return matches


def _generate_evidence_mapping_with_llm(
    *,
    evidence_rows: list[dict[str, Any]],
    target_items: list[ChecklistItem],
) -> dict[str, Any]:
    system = (
        "You map student evidence to checklist requirements. "
        "Only map when the evidence explicitly supports the requirement. "
        "Output one JSON object with keys: matches (array), uncertainty (string or null). "
        "Each matches item must include item_id, source_proof_id, confidence (0 to 1), rationale."
    )
    payload = {
        "checklist_items": [
            {
                "id": str(item.id),
                "title": item.title,
                "description": item.description,
                "rationale": item.rationale,
                "tier": item.tier,
            }
            for item in target_items
        ],
        "evidence_items": [
            {
                "proof_id": row["proof_id"],
                "proof_type": row.get("proof_type"),
                "url": row.get("url"),
                "evidence_excerpt": row.get("evidence_excerpt"),
                "metadata": row.get("metadata"),
            }
            for row in evidence_rows
        ],
    }
    raw = _call_llm(system, json.dumps(payload))
    parsed = _safe_json(raw)
    return parsed or {"matches": [], "uncertainty": "AI output parse failure."}


def _map_evidence_to_items(
    *,
    evidence_rows: list[dict[str, Any]],
    target_items: list[ChecklistItem],
) -> tuple[list[dict[str, Any]], str]:
    if not evidence_rows or not target_items:
        return [], "no_evidence"

    valid_item_ids = {str(item.id) for item in target_items}
    valid_proof_ids = {row["proof_id"] for row in evidence_rows}

    if ai_is_configured():
        try:
            parsed = _generate_evidence_mapping_with_llm(
                evidence_rows=evidence_rows,
                target_items=target_items,
            )
            mapped: list[dict[str, Any]] = []
            for row in parsed.get("matches", []):
                item_id = str(row.get("item_id") or "")
                source_proof_id = str(row.get("source_proof_id") or "")
                if item_id not in valid_item_ids or source_proof_id not in valid_proof_ids:
                    continue
                confidence = float(row.get("confidence", 0.0))
                if confidence < AI_EVIDENCE_MAP_THRESHOLD:
                    continue
                mapped.append(
                    {
                        "item_id": item_id,
                        "source_proof_id": source_proof_id,
                        "confidence": confidence,
                        "rationale": str(row.get("rationale") or "Mapped from uploaded evidence."),
                    }
                )
            deduped: list[dict[str, Any]] = []
            seen_items: set[str] = set()
            for row in mapped:
                if row["item_id"] in seen_items:
                    continue
                seen_items.add(row["item_id"])
                deduped.append(row)
            return deduped, "ai"
        except Exception:
            pass

    fallback = _rule_map_evidence_to_items(
        evidence_rows=evidence_rows,
        target_items=target_items,
    )
    return fallback, "rules"


def _recommended_certificates_for_gaps(gap_items: list[ChecklistItem]) -> list[str]:
    text = " ".join(
        f"{item.title} {item.description or ''} {item.rationale or ''}".lower()
        for item in gap_items
    )
    suggestions: list[str] = []

    if any(token in text for token in ["data", "sql", "analytics", "tableau", "power bi", "excel"]):
        suggestions.extend(
            [
                "Microsoft Power BI Data Analyst (PL-300)",
                "Databricks Certified Data Analyst Associate",
                "Google Data Analytics Professional Certificate",
            ]
        )

    if any(token in text for token in ["security", "cyber", "soc", "network", "threat"]):
        suggestions.extend(
            [
                "CompTIA Security+",
                "Microsoft Security, Compliance, and Identity Fundamentals (SC-900)",
                "Google Cybersecurity Professional Certificate",
            ]
        )

    if any(
        token in text
        for token in ["software", "backend", "api", "full-stack", "full stack", "cloud", "devops"]
    ):
        suggestions.extend(
            [
                "AWS Certified Cloud Practitioner",
                "AWS Certified Developer - Associate",
                "GitHub Foundations",
            ]
        )

    if not suggestions:
        suggestions.extend(
            [
                "AWS Certified Cloud Practitioner",
                "Google Career Certificate aligned to your pathway",
            ]
        )

    return _unique_list(suggestions)[:5]


def _materials_to_master_for_gaps(gap_items: list[ChecklistItem]) -> list[str]:
    materials = [f"Master: {item.title}" for item in gap_items[:4]]
    text = " ".join(
        f"{item.title} {item.description or ''} {item.rationale or ''}".lower()
        for item in gap_items
    )
    if any(token in text for token in ["sql", "data"]):
        materials.append("Practice SQL querying, joins, window functions, and data modeling.")
    if any(token in text for token in ["api", "backend", "full-stack", "full stack"]):
        materials.append("Deepen API design, backend architecture, and deployment fundamentals.")
    if any(token in text for token in ["security", "cyber"]):
        materials.append("Strengthen secure coding, IAM basics, and incident-response workflows.")
    if not materials:
        materials.append("Review checklist gaps and focus on one high-impact skill each week.")
    return _unique_list(materials)[:6]


def _priority_focus_areas_for_gaps(gap_items: list[ChecklistItem]) -> list[str]:
    focus = [item.title for item in gap_items[:4] if item.title]
    if not focus:
        focus = [
            "Maintain current checklist momentum",
            "Strengthen one portfolio-ready project",
        ]
    return _unique_list(focus)[:4]


def _yearize_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"(?i)\bsemester\b", "Year", str(value)).strip()


def _yearize_list(values: list[Any]) -> list[str]:
    return [_yearize_text(value) for value in values if isinstance(value, str) and value.strip()]


def _academic_year_number(stage: str | None) -> int | None:
    if not stage:
        return None
    normalized = stage.strip().lower()
    if not normalized:
        return None

    if re.fullmatch(r"\d+", normalized):
        value = int(normalized)
        return value if value > 0 else None

    keyword_map = {
        "freshman": 1,
        "first year": 1,
        "1st year": 1,
        "sophomore": 2,
        "second year": 2,
        "2nd year": 2,
        "junior": 3,
        "third year": 3,
        "3rd year": 3,
        "senior": 4,
        "fourth year": 4,
        "4th year": 4,
    }
    for key, value in keyword_map.items():
        if key in normalized:
            return value

    match = re.search(r"\b(?:year|semester|sem|yr)\s*([1-9])\b", normalized)
    if match:
        return int(match.group(1))

    return None


def _normalized_academic_stage(stage: str | None) -> str | None:
    if not stage:
        return None
    year_number = _academic_year_number(stage)
    if year_number:
        return f"Year {year_number}"
    value = _yearize_text(stage)
    if not value:
        return None
    return value


def _should_recommend_internships(stage: str | None) -> bool:
    year_number = _academic_year_number(stage)
    return year_number in {2, 3}


def _internship_recommendations(stage: str | None) -> list[str]:
    if not _should_recommend_internships(stage):
        return []
    return [
        "Apply to internships this cycle and prioritize roles that match your pathway skills.",
        "Target Year 2/Year 3 internship roles and tailor each application with proof-backed projects.",
    ]


def _weekly_plan_for_gaps(
    gap_items: list[ChecklistItem],
    milestones: list[Milestone],
    profile: StudentProfile | None,
) -> list[str]:
    plan: list[str] = []
    for index, item in enumerate(gap_items[:4], start=1):
        plan.append(
            f"Week {index}: Close '{item.title}' with one concrete deliverable and a concise proof artifact."
        )
    if milestones:
        week_index = min(max(len(plan) + 1, 1), 6)
        plan.append(
            f"Week {week_index}: Align your work to milestone '{milestones[0].title}' and log progress."
        )
    academic_stage = _normalized_academic_stage(profile.semester) if profile else None
    if academic_stage:
        week_index = min(max(len(plan) + 1, 1), 6)
        plan.append(
            f"Week {week_index}: Run a readiness check before the end of {academic_stage}."
        )
    if not plan:
        plan = [
            "Week 1: Review your checklist and pick one high-impact requirement.",
            "Week 2: Complete and submit proof for that requirement.",
            "Week 3: Recalculate readiness and repeat with the next gap.",
        ]
    return _unique_list(plan)[:6]


def _guide_explainability(
    *,
    gap_items: list[ChecklistItem],
    all_items: list[ChecklistItem],
    proofs: list[Proof],
) -> tuple[list[str], dict[str, float]]:
    evidence_snippets: list[str] = []
    confidence_by_item: dict[str, float] = {}
    verified_item_ids = {
        str(proof.checklist_item_id) for proof in proofs if proof.status == "verified"
    }
    for item in gap_items[:4]:
        evidence_snippets.append(
            f"Gap detected: '{item.title}' ({item.tier.replace('_', ' ')})."
        )
    for item in all_items[:30]:
        item_id = str(item.id)
        if item_id in verified_item_ids:
            confidence = 0.88
        elif item in gap_items:
            confidence = 0.62
        elif item.tier == "non_negotiable":
            confidence = 0.7
        else:
            confidence = 0.66
        confidence_by_item[item_id] = round(confidence, 2)
    return _unique_list(evidence_snippets)[:6], confidence_by_item


def _tokenize_market_terms(text: str) -> set[str]:
    if not text:
        return set()
    normalized = text.lower().replace("&", " and ")
    tokens = {
        token
        for token in re.findall(r"[a-z][a-z0-9+#./-]{1,}", normalized)
        if len(token) >= 3 and token not in MARKET_TOKEN_STOPWORDS
    }
    for phrase in [
        "full stack",
        "machine learning",
        "power bi",
        "data modeling",
        "system design",
        "incident response",
        "cloud iam",
    ]:
        if phrase in normalized:
            tokens.add(phrase)
    return tokens


def _format_skill_label(value: str) -> str:
    text = value.strip()
    if not text:
        return text
    if text.islower():
        acronyms = {"api", "sql", "aws", "gcp", "bi", "etl", "iam", "soc", "ci/cd"}
        if text in acronyms:
            return text.upper()
        return text.title()
    return text


def _market_signal_weight(signal: MarketSignal) -> float:
    weight = float(signal.source_count or 1)
    if signal.frequency is not None:
        weight += float(signal.frequency) * 50.0
    return max(weight, 0.1)


def _market_certificates_for_skills(skills: list[str]) -> list[str]:
    text = " ".join(skills).lower()
    certs: list[str] = []

    if any(token in text for token in ["aws", "cloud", "docker", "kubernetes", "devops"]):
        certs.extend(
            [
                "AWS Certified Cloud Practitioner",
                "AWS Certified Developer - Associate",
            ]
        )
    if any(token in text for token in ["sql", "analytics", "bi", "tableau", "power bi", "data"]):
        certs.extend(
            [
                "Microsoft Power BI Data Analyst (PL-300)",
                "Google Data Analytics Professional Certificate",
            ]
        )
    if any(token in text for token in ["security", "cyber", "iam", "network"]):
        certs.extend(
            [
                "CompTIA Security+",
                "Microsoft Security, Compliance, and Identity Fundamentals (SC-900)",
            ]
        )
    if any(token in text for token in ["python", "java", "javascript", "react", "api", "full stack"]):
        certs.append("GitHub Foundations")

    return _unique_list(certs)[:5]


def _market_materials_for_skills(skills: list[str]) -> list[str]:
    materials: list[str] = []
    text = " ".join(skills).lower()

    if any(token in text for token in ["sql", "analytics", "bi", "data"]):
        materials.append("Practice advanced SQL, data modeling, and dashboard storytelling with one end-to-end project.")
    if any(token in text for token in ["api", "python", "java", "javascript", "react", "full stack"]):
        materials.append("Deepen full-stack engineering: API design, testing, auth flows, and deployment.")
    if any(token in text for token in ["aws", "cloud", "docker", "kubernetes", "devops"]):
        materials.append("Build cloud deployment fluency: IAM, containerization, CI/CD, and monitoring basics.")
    if any(token in text for token in ["security", "cyber", "iam", "network"]):
        materials.append("Strengthen security fundamentals: secure coding, IAM controls, and incident response exercises.")

    if skills:
        materials.append(f"Produce one proof artifact this week tied to market demand: {skills[0]}.")

    return _unique_list(materials)[:6]


def _build_market_demand_context(
    db: Session,
    *,
    pathway_id,
    all_items: list[ChecklistItem],
    gap_items: list[ChecklistItem],
) -> dict[str, Any]:
    rows = (
        db.query(MarketSignal, Skill)
        .outerjoin(Skill, MarketSignal.skill_id == Skill.id)
        .filter(or_(MarketSignal.pathway_id == pathway_id, MarketSignal.pathway_id.is_(None)))
        .order_by(MarketSignal.window_end.desc().nullslast(), MarketSignal.id.desc())
        .limit(MARKET_SIGNAL_LOOKBACK_LIMIT)
        .all()
    )
    if not rows:
        return {
            "signal_count": 0,
            "latest_window_end": None,
            "top_skills": [],
            "market_alignment": [],
        }

    item_text_by_id: dict[str, str] = {}
    item_terms_by_id: dict[str, set[str]] = {}
    for item in all_items:
        item_text = f"{item.title} {item.description or ''} {item.rationale or ''}".lower()
        item_id = str(item.id)
        item_text_by_id[item_id] = item_text
        item_terms_by_id[item_id] = _tokenize_market_terms(item_text)

    score_by_skill: dict[str, float] = {}
    display_by_skill: dict[str, str] = {}
    score_by_item: dict[str, float] = {str(item.id): 0.0 for item in all_items}
    matched_skills_by_item: dict[str, list[tuple[str, float]]] = {
        str(item.id): [] for item in all_items
    }
    latest_window_end = None

    for signal, skill in rows:
        if signal.window_end and (latest_window_end is None or signal.window_end > latest_window_end):
            latest_window_end = signal.window_end
        skill_name = (skill.name if skill else None) or ""
        skill_name = str(skill_name).strip()
        if not skill_name:
            continue

        skill_key = skill_name.lower()
        if skill_key in MARKET_TOKEN_STOPWORDS:
            continue
        skill_terms = _tokenize_market_terms(skill_name)
        if not skill_terms:
            continue

        weight = _market_signal_weight(signal)
        score_by_skill[skill_key] = score_by_skill.get(skill_key, 0.0) + weight
        if skill_key not in display_by_skill:
            display_by_skill[skill_key] = _format_skill_label(skill_name)

        best_item_id = None
        best_match_score = 0.0
        for item_id, item_terms in item_terms_by_id.items():
            overlap = skill_terms.intersection(item_terms)
            phrase_match = skill_key in item_text_by_id[item_id]
            if phrase_match:
                match_score = 1.0
            elif overlap:
                match_score = len(overlap) / max(len(skill_terms), 1)
            else:
                match_score = 0.0
            if match_score > best_match_score:
                best_match_score = match_score
                best_item_id = item_id

        if best_item_id and best_match_score > 0:
            aligned_weight = weight * best_match_score
            score_by_item[best_item_id] = score_by_item.get(best_item_id, 0.0) + aligned_weight
            matched_skills_by_item[best_item_id].append((display_by_skill[skill_key], aligned_weight))

    top_skill_rows = sorted(score_by_skill.items(), key=lambda item: item[1], reverse=True)
    top_skills = [display_by_skill[key] for key, _ in top_skill_rows[:MARKET_GUIDE_SKILLS_LIMIT]]

    alignment_notes: list[str] = []
    for gap in gap_items[:4]:
        gap_id = str(gap.id)
        demand_score = score_by_item.get(gap_id, 0.0)
        skill_rows = sorted(
            matched_skills_by_item.get(gap_id, []),
            key=lambda item: item[1],
            reverse=True,
        )
        aligned_skills = _unique_list([label for label, _ in skill_rows])[:2]
        if demand_score > 0 and aligned_skills:
            alignment_notes.append(
                f"{gap.title}: strong market pull via {', '.join(aligned_skills)}."
            )
        else:
            alignment_notes.append(
                f"{gap.title}: required by checklist; market data is currently less explicit."
            )

    return {
        "signal_count": len(rows),
        "latest_window_end": latest_window_end.isoformat() if latest_window_end else None,
        "top_skills": top_skills,
        "market_alignment": alignment_notes[:4],
    }


def _build_global_market_context(db: Session) -> dict[str, Any]:
    rows = (
        db.query(MarketSignal, Skill)
        .outerjoin(Skill, MarketSignal.skill_id == Skill.id)
        .order_by(MarketSignal.window_end.desc().nullslast(), MarketSignal.id.desc())
        .limit(MARKET_SIGNAL_LOOKBACK_LIMIT)
        .all()
    )
    if not rows:
        return {
            "signal_count": 0,
            "latest_window_end": None,
            "top_skills": [],
            "top_roles": [],
            "market_alignment": [],
        }

    skill_weights: dict[str, float] = {}
    skill_labels: dict[str, str] = {}
    role_counts: Counter[str] = Counter()
    latest_window_end = None

    for signal, skill in rows:
        if signal.window_end and (latest_window_end is None or signal.window_end > latest_window_end):
            latest_window_end = signal.window_end

        role_family = (signal.role_family or "").strip()
        if role_family:
            role_counts[role_family] += 1

        raw_skill = ((skill.name if skill else None) or "").strip()
        if not raw_skill:
            continue
        skill_key = raw_skill.lower()
        if skill_key in MARKET_TOKEN_STOPWORDS:
            continue
        weight = _market_signal_weight(signal)
        skill_weights[skill_key] = skill_weights.get(skill_key, 0.0) + weight
        if skill_key not in skill_labels:
            skill_labels[skill_key] = _format_skill_label(raw_skill)

    top_skill_rows = sorted(skill_weights.items(), key=lambda row: row[1], reverse=True)
    top_skills = [skill_labels[key] for key, _ in top_skill_rows[:MARKET_GUIDE_SKILLS_LIMIT]]
    top_roles = [name for name, _ in role_counts.most_common(4)]

    alignment: list[str] = []
    if top_skills:
        alignment.append(f"Current demand is strongest for: {', '.join(top_skills[:3])}.")
    if top_roles:
        alignment.append(f"Common hiring clusters include: {', '.join(top_roles[:3])}.")
    if not alignment:
        alignment.append("Market signals are limited; guidance emphasizes transferable fundamentals.")

    return {
        "signal_count": len(rows),
        "latest_window_end": latest_window_end.isoformat() if latest_window_end else None,
        "top_skills": top_skills,
        "top_roles": top_roles,
        "market_alignment": alignment[:4],
    }


def ai_is_configured() -> bool:
    _, api_key, model, _ = _provider_config()
    return bool(settings.ai_enabled and api_key and model)


def get_active_ai_provider() -> str:
    return _provider_config()[0]


def get_active_ai_model() -> str:
    return _provider_config()[2]


def _call_llm(
    system_prompt: str,
    user_payload: str,
    *,
    override_model: str | None = None,
    expect_json: bool = True,
) -> str:
    provider, api_key, default_model, api_base = _provider_config()
    model = (override_model or default_model or "").strip()
    if not settings.ai_enabled:
        raise RuntimeError("AI is disabled")
    if not api_key:
        raise RuntimeError(f"{provider} API key is not configured")
    if not model:
        raise RuntimeError(f"No model configured for provider '{provider}'")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_payload},
        ],
        "temperature": 0.2,
    }
    if provider == "openai" and expect_json:
        body["response_format"] = {"type": "json_object"}

    last_error: Exception | None = None
    with httpx.Client(timeout=45.0) as client:
        for attempt in range(2):
            try:
                response = client.post(
                    f"{api_base}/chat/completions",
                    headers=headers,
                    json=body,
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
            except httpx.HTTPStatusError as exc:
                last_error = exc
                status = exc.response.status_code
                if status in {429, 500, 502, 503, 504} and attempt == 0:
                    time.sleep(1.5)
                    continue
                raise RuntimeError(
                    f"LLM API error ({status}): {exc.response.text[:500]}"
                ) from exc
            except Exception as exc:  # pragma: no cover - defensive
                last_error = exc
                if attempt == 0:
                    time.sleep(1.0)
                    continue
                break

    raise RuntimeError(f"LLM call failed: {last_error}") from last_error


def _log_ai_audit(
    db: Session,
    *,
    user_id: str | None,
    feature: str,
    prompt_input: dict | None,
    context_ids: list[str] | None,
    model: str | None,
    output: str | None,
):
    entry = AiAuditLog(
        user_id=user_id,
        feature=feature,
        prompt_input=prompt_input,
        context_ids=context_ids,
        model=model,
        output=output,
        created_at=datetime.utcnow(),
    )
    db.add(entry)
    db.commit()


def log_ai_feedback(
    db: Session,
    *,
    user_id: str,
    helpful: bool,
    comment: str | None,
    context_ids: list[str] | None,
):
    entry = AiAuditLog(
        user_id=user_id,
        feature="student_guide_feedback",
        prompt_input={"helpful": helpful},
        context_ids=context_ids,
        model=get_active_ai_model() if ai_is_configured() else "n/a",
        output=comment or "",
        feedback={"helpful": helpful, "comment": comment or ""},
        created_at=datetime.utcnow(),
    )
    db.add(entry)
    db.commit()


def sync_resume_requirement_matches(db: Session, user_id: str) -> dict[str, Any]:
    selection = db.query(UserPathway).filter(UserPathway.user_id == user_id).one_or_none()
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == user_id).one_or_none()

    # Remove previous resume-derived matches before recalculating.
    existing_resume_matches = (
        db.query(Proof)
        .filter(Proof.user_id == user_id)
        .filter(Proof.proof_type == RESUME_MATCH_PROOF_TYPE)
        .all()
    )
    for proof in existing_resume_matches:
        db.delete(proof)
    db.commit()

    if not selection:
        return {"matched_count": 0, "mode": "no_pathway"}

    if not profile or not getattr(profile, "resume_url", None):
        return {"matched_count": 0, "mode": "no_resume"}

    version_id = selection.checklist_version_id
    if not version_id:
        version = (
            db.query(ChecklistVersion)
            .filter(ChecklistVersion.pathway_id == selection.pathway_id)
            .filter(ChecklistVersion.status == "published")
            .order_by(ChecklistVersion.version_number.desc())
            .first()
        )
        if not version:
            return {"matched_count": 0, "mode": "no_published_checklist"}
        version_id = version.id

    items = db.query(ChecklistItem).filter(ChecklistItem.version_id == version_id).all()
    if not items:
        return {"matched_count": 0, "mode": "no_items"}

    resume_context = _extract_resume_context(profile)
    matches, mode = _evaluate_resume_matches(
        resume_context=resume_context,
        items=items,
    )
    if not matches:
        _log_ai_audit(
            db,
            user_id=user_id,
            feature="resume_requirement_match",
            prompt_input={"mode": mode},
            context_ids=[],
            model=get_active_ai_model() if mode == "ai" else "rules-based",
            output="No checklist items were satisfied by resume evidence.",
        )
        return {"matched_count": 0, "mode": mode}

    item_by_id = {str(item.id): item for item in items}
    created = 0
    for match in matches:
        item = item_by_id.get(match["item_id"])
        if not item:
            continue
        confidence = float(match.get("confidence", 0.0))
        rationale = str(match.get("rationale") or "Matched by resume evidence.")
        proof = Proof(
            user_id=user_id,
            checklist_item_id=item.id,
            proof_type=RESUME_MATCH_PROOF_TYPE,
            url=profile.resume_url,
            status="verified",
            review_note=f"Satisfied by resume upload. {rationale}",
            metadata_json={
                "source": "resume_upload",
                "confidence": confidence,
                "mode": mode,
                "resume_filename": profile.resume_filename,
                "resume_uploaded_at": (
                    profile.resume_uploaded_at.isoformat()
                    if profile.resume_uploaded_at
                    else None
                ),
            },
            created_at=datetime.utcnow(),
        )
        db.add(proof)
        created += 1

    db.commit()
    _log_ai_audit(
        db,
        user_id=user_id,
        feature="resume_requirement_match",
        prompt_input={"mode": mode},
        context_ids=[m["item_id"] for m in matches if m["item_id"] in item_by_id],
        model=get_active_ai_model() if mode == "ai" else "rules-based",
        output=f"Matched {created} checklist items from resume evidence.",
    )
    return {"matched_count": created, "mode": mode}


def sync_evidence_requirement_matches(db: Session, user_id: str) -> dict[str, Any]:
    selection = db.query(UserPathway).filter(UserPathway.user_id == user_id).one_or_none()
    if not selection:
        return {"matched_count": 0, "mode": "no_pathway", "matched_item_ids": []}

    version_id = selection.checklist_version_id
    if not version_id:
        version = (
            db.query(ChecklistVersion)
            .filter(ChecklistVersion.pathway_id == selection.pathway_id)
            .filter(ChecklistVersion.status == "published")
            .order_by(ChecklistVersion.version_number.desc())
            .first()
        )
        if not version:
            return {"matched_count": 0, "mode": "no_published_checklist", "matched_item_ids": []}
        version_id = version.id

    items = db.query(ChecklistItem).filter(ChecklistItem.version_id == version_id).all()
    if not items:
        return {"matched_count": 0, "mode": "no_items", "matched_item_ids": []}

    existing_ai_matches = (
        db.query(Proof)
        .filter(Proof.user_id == user_id)
        .filter(Proof.proof_type == AI_EVIDENCE_MAP_PROOF_TYPE)
        .all()
    )
    for proof in existing_ai_matches:
        db.delete(proof)
    db.commit()

    all_user_proofs = db.query(Proof).filter(Proof.user_id == user_id).all()
    verified_item_ids = {
        str(proof.checklist_item_id)
        for proof in all_user_proofs
        if proof.status == "verified" and proof.proof_type != AI_EVIDENCE_MAP_PROOF_TYPE
    }
    target_items = [item for item in items if str(item.id) not in verified_item_ids]
    if not target_items:
        return {"matched_count": 0, "mode": "already_complete", "matched_item_ids": []}

    source_proofs = [
        proof
        for proof in all_user_proofs
        if proof.status == "verified"
        and proof.proof_type not in {RESUME_MATCH_PROOF_TYPE, AI_EVIDENCE_MAP_PROOF_TYPE}
        and not (proof.url or "").startswith("self_attested://")
    ]
    evidence_rows: list[dict[str, Any]] = []
    for proof in source_proofs:
        excerpt, evidence_meta = _extract_proof_evidence_excerpt(proof)
        if not excerpt:
            continue
        evidence_rows.append(
            {
                "proof_id": str(proof.id),
                "proof_type": proof.proof_type,
                "url": proof.url,
                "metadata": proof.metadata_json or {},
                "evidence_meta": evidence_meta,
                "evidence_excerpt": excerpt,
            }
        )

    if not evidence_rows:
        _log_ai_audit(
            db,
            user_id=user_id,
            feature="evidence_requirement_match",
            prompt_input={"mode": "no_evidence"},
            context_ids=[],
            model="rules-based",
            output="No text-readable verified evidence found for cross-mapping.",
        )
        return {"matched_count": 0, "mode": "no_evidence", "matched_item_ids": []}

    matches, mode = _map_evidence_to_items(
        evidence_rows=evidence_rows,
        target_items=target_items,
    )
    if not matches:
        _log_ai_audit(
            db,
            user_id=user_id,
            feature="evidence_requirement_match",
            prompt_input={"mode": mode},
            context_ids=[],
            model=get_active_ai_model() if mode == "ai" else "rules-based",
            output="No additional requirements were satisfied from uploaded evidence.",
        )
        return {"matched_count": 0, "mode": mode, "matched_item_ids": []}

    source_by_id = {str(proof.id): proof for proof in source_proofs}
    item_by_id = {str(item.id): item for item in target_items}
    created = 0
    matched_item_ids: list[str] = []
    seen_items: set[str] = set()
    for match in matches:
        item_id = str(match.get("item_id") or "")
        source_proof_id = str(match.get("source_proof_id") or "")
        if item_id in seen_items:
            continue
        item = item_by_id.get(item_id)
        source = source_by_id.get(source_proof_id)
        if not item or not source:
            continue
        confidence = float(match.get("confidence", 0.0))
        rationale = str(match.get("rationale") or "Mapped from uploaded evidence.")
        db.add(
            Proof(
                user_id=user_id,
                checklist_item_id=item.id,
                proof_type=AI_EVIDENCE_MAP_PROOF_TYPE,
                url=source.url,
                status="verified",
                review_note=f"Satisfied by AI evidence mapping from '{source.proof_type}'. {rationale}",
                metadata_json={
                    "source_proof_id": source_proof_id,
                    "source_proof_type": source.proof_type,
                    "confidence": confidence,
                    "mode": mode,
                    "rationale": rationale,
                },
                created_at=datetime.utcnow(),
            )
        )
        seen_items.add(item_id)
        matched_item_ids.append(item_id)
        created += 1

    db.commit()
    _log_ai_audit(
        db,
        user_id=user_id,
        feature="evidence_requirement_match",
        prompt_input={"mode": mode},
        context_ids=matched_item_ids,
        model=get_active_ai_model() if mode == "ai" else "rules-based",
        output=f"Mapped {created} checklist items from uploaded proof evidence.",
    )
    return {
        "matched_count": created,
        "mode": mode,
        "matched_item_ids": matched_item_ids,
    }


def _rules_general_career_guidance(
    *,
    question: str | None,
    context_text: str | None,
    profile: StudentProfile | None,
    resume_detected: bool,
    resume_context: dict[str, Any] | None,
    market_context: dict[str, Any] | None,
) -> dict[str, Any]:
    academic_stage = _normalized_academic_stage(profile.semester) if profile else None
    internship_actions = _internship_recommendations(academic_stage)
    top_skills = list((market_context or {}).get("top_skills", []))[:MARKET_GUIDE_SKILLS_LIMIT]
    market_alignment = list((market_context or {}).get("market_alignment", []))[:4]
    question_text = (question or "").strip()
    profile_target = (
        (profile.masters_target or "").strip()
        if profile and profile.masters_interest
        else ""
    )

    recommendations: list[str] = []
    if question_text:
        recommendations.append(f"Directly prioritize: {question_text}")
    provided_context = _truncate((context_text or "").strip(), limit=1200)
    if provided_context:
        recommendations.append("Use the provided auditor context as primary evidence for this guidance.")
    recommendations += [
        "Define a target role list (5-10 roles) and map required skills from current job postings.",
        "Create one measurable project or portfolio artifact each week to prove capability.",
        "Tailor your resume bullets to outcomes, tools, and impact for each target role.",
    ]
    recommendations = _yearize_list(_unique_list(internship_actions + recommendations))[:3]

    next_actions = _yearize_list(
        _unique_list(
            internship_actions
            + [
                "Pick one target role and extract its top requirements from recent job posts.",
                "Submit one evidence-backed update this week (project, certification, internship, or work sample).",
                "Run a resume refinement pass for measurable impact and role-specific keywords.",
            ]
        )
    )[:3]

    weekly_plan = _yearize_list(
        _unique_list(
            internship_actions
            + [
                "Week 1: Clarify role targets and required competencies.",
                "Week 2: Build or improve one proof artifact tied to a target competency.",
                "Week 3: Update resume and portfolio evidence with quantified outcomes.",
                "Week 4: Apply to role-aligned opportunities and gather feedback.",
            ]
        )
    )[:6]

    evidence_snippets = [
        "General mode active because no pathway is selected yet.",
        "Guidance uses profile, resume context, and market-demand signals when available.",
    ]
    if resume_detected and resume_context and resume_context.get("resume_excerpt"):
        evidence_snippets.append("Resume text was analyzed for strengths and improvement opportunities.")
    if top_skills:
        evidence_snippets.append(f"Top market skills detected: {', '.join(top_skills[:3])}.")
    if profile_target:
        evidence_snippets.append(f"Profile indicates graduate-study intent toward: {profile_target}.")
    if provided_context:
        evidence_snippets.append(
            f"Auditor provided context analyzed: {provided_context}"
        )

    resume_improvements, resume_strengths = _rules_resume_feedback(
        resume_context=resume_context,
        gap_items=[],
    )
    if not resume_detected:
        resume_strengths = []
        resume_improvements = []

    recommended_certificates = _unique_list(_market_certificates_for_skills(top_skills))[:5]
    materials_to_master = _unique_list(_market_materials_for_skills(top_skills))[:6]
    if not materials_to_master:
        materials_to_master = [
            "Communication and storytelling for interviews and networking.",
            "Domain-specific fundamentals for your target role.",
            "Project scoping, execution, and outcome measurement.",
        ]

    return {
        "explanation": (
            "This guidance is generated in general career mode and is not limited to computer science. "
            "It uses your question, profile, resume context, any auditor-provided context, and market demand signals."
        ),
        "decision": "Focus on role-targeted evidence and measurable outcomes this month.",
        "recommendations": recommendations,
        "recommended_certificates": recommended_certificates,
        "materials_to_master": materials_to_master,
        "market_top_skills": top_skills,
        "market_alignment": market_alignment,
        "priority_focus_areas": [
            "Role targeting",
            "Evidence-backed project outcomes",
            "Resume-job alignment",
            "Interview readiness",
        ],
        "weekly_plan": weekly_plan,
        "evidence_snippets": evidence_snippets[:6],
        "confidence_by_item": {},
        "next_actions": next_actions,
        "suggested_proof_types": GENERAL_PROOF_TYPES,
        "cited_checklist_item_ids": [],
        "resume_detected": resume_detected,
        "resume_strengths": resume_strengths[:4],
        "resume_improvements": resume_improvements[:5],
        "uncertainty": "Using rules-based guidance because structured pathway data is not selected yet.",
    }


def _generate_general_career_guidance_with_llm(
    *,
    question: str | None,
    context_text: str | None,
    profile: StudentProfile | None,
    resume_context: dict[str, Any] | None,
    resume_detected: bool,
    market_context: dict[str, Any] | None,
) -> dict[str, Any]:
    academic_stage = _normalized_academic_stage(profile.semester) if profile else None
    internship_actions = _internship_recommendations(academic_stage)

    system = (
        "You are an OpenAI career strategist. Support ALL career domains "
        "(technology, business, healthcare, legal, design, finance, education, public sector, trades, and creative fields). "
        "Answer naturally like a professional career coach, but return output as a single JSON object. "
        "Use user profile, resume context, and market context when available. "
        "Do not assume the user is a CS major. "
        "If auditor_context is provided, treat it as first-class evidence for this response. "
        "If information is missing, make practical assumptions and provide adaptable recommendations. "
        "Output keys: explanation (string), decision (string), recommendations (max 3), "
        "recommended_certificates (max 5), materials_to_master (max 6), "
        "market_top_skills (max 6), market_alignment (max 4), priority_focus_areas (max 4), "
        "weekly_plan (max 6), evidence_snippets (max 6), confidence_by_item (object), "
        "next_actions (max 3), suggested_proof_types (unique array), cited_checklist_item_ids (empty array), "
        "resume_detected (boolean), resume_strengths (max 4), resume_improvements (max 5), uncertainty (string or null)."
    )
    payload = {
        "question": question,
        "auditor_context": _truncate((context_text or "").strip(), limit=3000) if context_text else None,
        "mode": "general_career_guidance",
        "student_profile": {
            "academic_stage": academic_stage,
            "state": profile.state if profile else None,
            "university": profile.university if profile else None,
            "masters_interest": profile.masters_interest if profile else None,
            "masters_target": profile.masters_target if profile else None,
            "masters_timeline": profile.masters_timeline if profile else None,
            "masters_status": profile.masters_status if profile else None,
        },
        "resume_detected": resume_detected,
        "resume_context": resume_context,
        "market_context": market_context or {},
    }

    raw = _call_llm(system, json.dumps(payload))
    parsed = _safe_json(raw)
    if not parsed:
        raise RuntimeError("AI output parse failure.")

    response = {
        "explanation": _yearize_text(str(parsed.get("explanation") or "")),
        "decision": _yearize_text(str(parsed.get("decision") or "")),
        "recommendations": _yearize_list(
            _unique_list(internship_actions + list(parsed.get("recommendations") or []))
        )[:3],
        "recommended_certificates": list(parsed.get("recommended_certificates") or [])[:5],
        "materials_to_master": list(parsed.get("materials_to_master") or [])[:6],
        "market_top_skills": list(parsed.get("market_top_skills") or [])[:MARKET_GUIDE_SKILLS_LIMIT],
        "market_alignment": list(parsed.get("market_alignment") or [])[:4],
        "priority_focus_areas": list(parsed.get("priority_focus_areas") or [])[:4],
        "weekly_plan": _yearize_list(list(parsed.get("weekly_plan") or []))[:6],
        "evidence_snippets": _yearize_list(list(parsed.get("evidence_snippets") or []))[:6],
        "confidence_by_item": parsed.get("confidence_by_item")
        if isinstance(parsed.get("confidence_by_item"), dict)
        else {},
        "next_actions": _yearize_list(
            _unique_list(internship_actions + list(parsed.get("next_actions") or []))
        )[:3],
        "suggested_proof_types": _unique_list(
            list(parsed.get("suggested_proof_types") or []) + GENERAL_PROOF_TYPES
        )[:6],
        "cited_checklist_item_ids": [],
        "resume_detected": bool(parsed.get("resume_detected", resume_detected)),
        "resume_strengths": list(parsed.get("resume_strengths") or [])[:4],
        "resume_improvements": list(parsed.get("resume_improvements") or [])[:5],
        "uncertainty": parsed.get("uncertainty"),
    }

    if not response["explanation"]:
        response["explanation"] = (
            "Guidance generated in general career mode using your question, profile, and market context."
        )
    if not response["decision"]:
        response["decision"] = "Prioritize evidence-backed progress toward your target role."
    if not response["recommendations"]:
        response["recommendations"] = _yearize_list(
            internship_actions
            + [
                "Map your target role requirements from live postings.",
                "Build one measurable proof artifact this week.",
                "Refine your resume for role-specific outcomes and keywords.",
            ]
        )[:3]
    if not response["next_actions"]:
        response["next_actions"] = response["recommendations"][:3]
    if not response["market_top_skills"]:
        response["market_top_skills"] = list((market_context or {}).get("top_skills", []))[:MARKET_GUIDE_SKILLS_LIMIT]
    if not response["market_alignment"]:
        response["market_alignment"] = list((market_context or {}).get("market_alignment", []))[:4]

    if not resume_detected:
        response["resume_strengths"] = []
        response["resume_improvements"] = []

    return response


def generate_student_guidance(
    db: Session,
    user_id: str,
    question: str | None = None,
    context_text: str | None = None,
) -> dict:
    selection = db.query(UserPathway).filter(UserPathway.user_id == user_id).one_or_none()
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == user_id).one_or_none()
    resume_context = _extract_resume_context(profile)
    resume_detected = bool(profile and getattr(profile, "resume_url", None))

    if not selection:
        market_context = _build_global_market_context(db)
        if ai_is_configured():
            try:
                response = _generate_general_career_guidance_with_llm(
                    question=question,
                    context_text=context_text,
                    profile=profile,
                    resume_context=resume_context,
                    resume_detected=resume_detected,
                    market_context=market_context,
                )
                _log_ai_audit(
                    db,
                    user_id=user_id,
                    feature="student_guide_general",
                    prompt_input={
                        "question": question,
                        "context_excerpt": _truncate((context_text or "").strip(), limit=500)
                        if context_text
                        else None,
                    },
                    context_ids=[],
                    model=get_active_ai_model(),
                    output=response.get("explanation"),
                )
                return response
            except Exception:
                pass

        fallback = _rules_general_career_guidance(
            question=question,
            context_text=context_text,
            profile=profile,
            resume_detected=resume_detected,
            resume_context=resume_context,
            market_context=market_context,
        )
        _log_ai_audit(
            db,
            user_id=user_id,
            feature="student_guide_general",
            prompt_input={
                "question": question,
                "context_excerpt": _truncate((context_text or "").strip(), limit=500)
                if context_text
                else None,
            },
            context_ids=[],
            model="rules-based",
            output=fallback.get("explanation"),
        )
        return fallback

    version_id = selection.checklist_version_id
    if not version_id:
        version = (
            db.query(ChecklistVersion)
            .filter(ChecklistVersion.pathway_id == selection.pathway_id)
            .filter(ChecklistVersion.status == "published")
            .order_by(ChecklistVersion.version_number.desc())
            .first()
        )
        if not version:
            raise ValueError("No published checklist version")
        version_id = version.id

    items = db.query(ChecklistItem).filter(ChecklistItem.version_id == version_id).all()
    milestones = (
        db.query(Milestone)
        .filter(Milestone.pathway_id == selection.pathway_id)
        .order_by(Milestone.semester_index.asc())
        .all()
    )
    proofs = db.query(Proof).filter(Proof.user_id == user_id).all()
    # profile/resume context already loaded above.

    readiness = calculate_readiness(items, proofs)
    top_gaps = readiness.get("top_gaps", [])

    gap_items = [i for i in items if i.title in top_gaps]
    market_context = _build_market_demand_context(
        db,
        pathway_id=selection.pathway_id,
        all_items=items,
        gap_items=gap_items,
    )
    rule_resume_improvements, rule_resume_strengths = _rules_resume_feedback(
        resume_context=resume_context,
        gap_items=gap_items,
    )
    rule_certificates = _unique_list(
        _recommended_certificates_for_gaps(gap_items)
        + _market_certificates_for_skills(market_context.get("top_skills", []))
    )[:5]
    rule_materials = _unique_list(
        _materials_to_master_for_gaps(gap_items)
        + _market_materials_for_skills(market_context.get("top_skills", []))
    )[:6]
    rule_focus_areas = _priority_focus_areas_for_gaps(gap_items)
    rule_weekly_plan = _weekly_plan_for_gaps(gap_items, milestones, profile)
    academic_stage = _normalized_academic_stage(profile.semester) if profile else None
    internship_actions = _internship_recommendations(academic_stage)
    rule_evidence_snippets, rule_confidence_by_item = _guide_explainability(
        gap_items=gap_items,
        all_items=items,
        proofs=proofs,
    )
    rule_market_top_skills = list(market_context.get("top_skills", []))[:MARKET_GUIDE_SKILLS_LIMIT]
    rule_market_alignment = list(market_context.get("market_alignment", []))[:4]
    if rule_market_top_skills:
        rule_weekly_plan = _unique_list(
            rule_weekly_plan
            + [
                "Align one proof submission this week to current market demand: "
                f"{rule_market_top_skills[0]}."
            ]
        )[:6]
        rule_evidence_snippets = _unique_list(
            [
                (
                    "Market scan summary: "
                    f"{market_context.get('signal_count', 0)} recent signals. "
                    f"Top demand skills include {', '.join(rule_market_top_skills[:3])}."
                )
            ]
            + rule_evidence_snippets
        )[:6]
    else:
        rule_evidence_snippets = _unique_list(
            rule_evidence_snippets
            + [
                "No recent market-signal data was available; recommendations emphasize checklist requirements."
            ]
        )[:6]
    if internship_actions:
        rule_weekly_plan = _unique_list(
            rule_weekly_plan
            + [
                "Week 1: Build an internship target list and submit your first application batch.",
            ]
        )[:6]
        rule_evidence_snippets = _unique_list(
            rule_evidence_snippets
            + [
                "Academic stage suggests internship applications should be active now (Year 2/Year 3 window)."
            ]
        )[:6]
    if context_text and context_text.strip():
        rule_evidence_snippets = _unique_list(
            rule_evidence_snippets
            + [f"Auditor provided context analyzed: {_truncate(context_text.strip(), limit=800)}"]
        )[:6]
    cited_ids = [str(i.id) for i in gap_items]
    suggested_proof_types = []
    for item in gap_items:
        for proof_type in item.allowed_proof_types or []:
            if proof_type not in suggested_proof_types:
                suggested_proof_types.append(proof_type)

    if ai_is_configured():
        try:
            response = _generate_student_guidance_with_llm(
                question=question,
                context_text=context_text,
                readiness=readiness,
                gap_items=gap_items,
                all_items=items,
                milestones=milestones,
                profile=profile,
                resume_context=resume_context,
                resume_detected=resume_detected,
                market_context=market_context,
            )
            valid_ids = {str(item.id) for item in items}
            cited_ids = [
                cid for cid in response.get("cited_checklist_item_ids", []) if cid in valid_ids
            ]
            if not cited_ids:
                cited_ids = [str(item.id) for item in gap_items]
                response["cited_checklist_item_ids"] = cited_ids
            response["resume_detected"] = resume_detected
            response["resume_strengths"] = list(
                response.get("resume_strengths") or rule_resume_strengths
            )[:4]
            response["resume_improvements"] = list(
                response.get("resume_improvements") or rule_resume_improvements
            )[:5]
            response["recommended_certificates"] = list(
                response.get("recommended_certificates") or rule_certificates
            )[:5]
            response["materials_to_master"] = list(
                response.get("materials_to_master") or rule_materials
            )[:6]
            response["market_top_skills"] = list(
                response.get("market_top_skills") or rule_market_top_skills
            )[:MARKET_GUIDE_SKILLS_LIMIT]
            response["market_alignment"] = list(
                response.get("market_alignment") or rule_market_alignment
            )[:4]
            response["priority_focus_areas"] = list(
                response.get("priority_focus_areas") or rule_focus_areas
            )[:4]
            response["weekly_plan"] = list(
                response.get("weekly_plan") or rule_weekly_plan
            )[:6]
            response["weekly_plan"] = _yearize_list(response["weekly_plan"])
            response["evidence_snippets"] = list(
                response.get("evidence_snippets") or rule_evidence_snippets
            )[:6]
            response["evidence_snippets"] = _yearize_list(response["evidence_snippets"])
            llm_confidence = response.get("confidence_by_item")
            response["confidence_by_item"] = (
                llm_confidence if isinstance(llm_confidence, dict) else rule_confidence_by_item
            )
            response["decision"] = _yearize_text(str(response.get("decision") or ""))
            response["explanation"] = _yearize_text(str(response.get("explanation") or ""))
            if internship_actions:
                response["recommendations"] = _unique_list(
                    internship_actions + list(response.get("recommendations") or [])
                )[:3]
                response["next_actions"] = _unique_list(
                    internship_actions + list(response.get("next_actions") or [])
                )[:3]
            response["recommendations"] = _yearize_list(
                _unique_list(list(response.get("recommendations") or []))
            )[:3]
            response["next_actions"] = _yearize_list(
                _unique_list(list(response.get("next_actions") or []))
            )[:3]
            if not resume_detected:
                response["resume_strengths"] = []
                response["resume_improvements"] = []
            _log_ai_audit(
                db,
                user_id=user_id,
                feature="student_guide",
                prompt_input={
                    "question": question,
                    "context_excerpt": _truncate((context_text or "").strip(), limit=500)
                    if context_text
                    else None,
                },
                context_ids=cited_ids,
                model=get_active_ai_model(),
                output=response.get("explanation"),
            )
            return response
        except Exception:
            # Continue to rules fallback below.
            pass

    if top_gaps:
        explanation = (
            "Your highest-impact gaps are: "
            + "; ".join(top_gaps)
            + ". These map to required checklist items for your pathway."
        )
    else:
        explanation = "Your checklist is complete or no gaps were found."

    next_actions = list(readiness.get("next_actions", []))
    if internship_actions:
        next_actions = _unique_list(internship_actions + next_actions)
    if milestones and len(next_actions) < 3:
        next_actions.append(f"Review milestone: {_yearize_text(milestones[0].title)}")
    if rule_market_top_skills and len(next_actions) < 3:
        next_actions.append(f"Submit one proof tied to {rule_market_top_skills[0]}.")
    next_actions = _yearize_list(next_actions)
    recommendations = list(next_actions)[:3]
    if rule_market_top_skills:
        recommendations = _unique_list(
            [f"Prioritize {rule_market_top_skills[0]} because it appears in current market signals."]
            + recommendations
        )[:3]
    recommendations = _yearize_list(recommendations)
    if academic_stage:
        decision = f"Prioritize non-negotiables before the end of {academic_stage}."
    elif top_gaps:
        decision = f"Prioritize the highest-impact gap: {top_gaps[0]}."
    else:
        decision = "Maintain readiness by keeping proofs current."
    decision = _yearize_text(decision)
    explanation = _yearize_text(explanation)

    response = {
        "explanation": explanation,
        "decision": decision,
        "recommendations": recommendations,
        "recommended_certificates": rule_certificates,
        "materials_to_master": rule_materials,
        "market_top_skills": rule_market_top_skills,
        "market_alignment": rule_market_alignment,
        "priority_focus_areas": rule_focus_areas,
        "weekly_plan": rule_weekly_plan,
        "evidence_snippets": rule_evidence_snippets,
        "confidence_by_item": rule_confidence_by_item,
        "next_actions": next_actions,
        "suggested_proof_types": _unique_list(suggested_proof_types),
        "cited_checklist_item_ids": [str(item.id) for item in gap_items],
        "resume_detected": resume_detected,
        "resume_strengths": rule_resume_strengths if resume_detected else [],
        "resume_improvements": rule_resume_improvements if resume_detected else [],
        "uncertainty": "AI unavailable. Using rules-based guidance.",
    }

    _log_ai_audit(
        db,
        user_id=user_id,
        feature="student_guide",
        prompt_input={
            "question": question,
            "context_excerpt": _truncate((context_text or "").strip(), limit=500)
            if context_text
            else None,
        },
        context_ids=cited_ids,
        model="rules-based",
        output=explanation,
    )

    return response


def generate_market_proposal_from_signals(
    *,
    signals: list[dict[str, Any]],
    instruction: str | None = None,
) -> dict[str, Any]:
    if not signals:
        return {
            "summary": "No signals provided for proposal generation.",
            "diff": {"signals": [], "suggested_changes": []},
            "uncertainty": "No signals provided.",
        }

    if ai_is_configured():
        try:
            response = _generate_market_proposal_with_llm(
                signals=signals,
                instruction=instruction,
            )
            summary = str(response.get("summary") or "").strip()
            diff = response.get("diff")
            if not isinstance(diff, dict):
                diff = {"signals": signals}
            if not summary:
                summary = f"Draft proposal generated from {len(signals)} market signals."
            return {
                "summary": summary,
                "diff": diff,
                "uncertainty": response.get("uncertainty"),
            }
        except Exception:
            pass

    skill_names = _unique_list(
        [
            str(signal.get("skill_name") or signal.get("skill_id") or "unspecified skill")
            for signal in signals
        ]
    )
    role_families = _unique_list(
        [str(signal.get("role_family")) for signal in signals if signal.get("role_family")]
    )
    suggested_changes = [
        {
            "action": "add_or_strengthen_requirement",
            "skill": skill,
            "rationale": "Frequent demand across ingested market signals.",
        }
        for skill in skill_names[:6]
    ]
    summary = (
        f"Draft proposal from {len(signals)} selected signals. "
        f"Top skills: {', '.join(skill_names[:4])}."
    )
    if role_families:
        summary += f" Role families observed: {', '.join(role_families[:3])}."
    return {
        "summary": summary,
        "diff": {
            "signals": signals,
            "suggested_changes": suggested_changes,
            "instruction": instruction,
        },
        "uncertainty": "AI unavailable. Using rules-based proposal synthesis.",
    }


def generate_admin_summary(db: Session, source_text: str, purpose: str | None = None) -> dict:
    if ai_is_configured():
        try:
            response = _generate_admin_summary_with_llm(source_text, purpose)
            _log_ai_audit(
                db,
                user_id=None,
                feature="admin_summary",
                prompt_input={"purpose": purpose},
                context_ids=None,
                model=get_active_ai_model(),
                output=response.get("summary"),
            )
            return response
        except Exception:
            # Continue to rules fallback below.
            pass

    text = source_text.strip()
    sentences = [s.strip() for s in text.split(".") if s.strip()]
    summary = ". ".join(sentences[:2]).strip()
    if summary and not summary.endswith("."):
        summary += "."

    rationale = None
    if purpose and "rationale" in purpose.lower():
        rationale = f"Rationale draft: {summary}" if summary else "Rationale draft pending."

    _log_ai_audit(
        db,
        user_id=None,
        feature="admin_summary",
        prompt_input={"purpose": purpose},
        context_ids=None,
        model="rules-based",
        output=summary,
    )

    return {"summary": summary or "Summary pending.", "rationale_draft": rationale}


def _unique_list(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _generate_student_guidance_with_llm(
    *,
    question: str | None,
    context_text: str | None,
    readiness: dict,
    gap_items: list[ChecklistItem],
    all_items: list[ChecklistItem],
    milestones: list[Milestone],
    profile: StudentProfile | None,
    resume_context: dict[str, Any] | None,
    resume_detected: bool,
    market_context: dict[str, Any] | None,
) -> dict:
    academic_stage = _normalized_academic_stage(profile.semester) if profile else None
    system = (
        "You are a career-pathway guide across all career domains, not just software careers. "
        "Only use the provided checklist items for requirement references. "
        "You may reference provided milestones for timing context. "
        "Use market_context to align advice to current demand signals. "
        "If auditor_context is provided, treat it as first-class evidence for this response. "
        "If academic stage is Year 2 or Year 3 (including sophomore/junior), include internship application actions "
        "in recommendations and next_actions. "
        "If a resume excerpt is provided, personalize recommendations to the student's demonstrated experience. "
        "Never invent requirements. Output a single JSON object with keys: "
        "explanation (string), decision (string), recommendations (array of strings, max 3), "
        "recommended_certificates (array of strings, max 5), "
        "materials_to_master (array of strings, max 6), "
        "market_top_skills (array of strings, max 6), "
        "market_alignment (array of strings, max 4), "
        "priority_focus_areas (array of strings, max 4), "
        "weekly_plan (array of strings, max 6), "
        "evidence_snippets (array of strings, max 6), "
        "confidence_by_item (object keyed by checklist item id with confidence 0..1), "
        "next_actions (array of strings, max 3), "
        "suggested_proof_types (array of strings, unique, no duplicates), "
        "cited_checklist_item_ids (array of UUID strings that appear in checklist_items), "
        "resume_detected (boolean), "
        "resume_strengths (array of strings, max 4), "
        "resume_improvements (array of strings, max 5), "
        "uncertainty (string or null)."
    )
    context_items = [
        {
            "id": str(item.id),
            "title": item.title,
            "tier": item.tier,
            "allowed_proof_types": item.allowed_proof_types or [],
            "is_critical": item.is_critical,
        }
        for item in all_items
    ]
    payload = {
        "question": question,
        "auditor_context": _truncate((context_text or "").strip(), limit=3000) if context_text else None,
        "readiness": readiness,
        "resume_detected": resume_detected,
        "student_profile": {
            "semester": academic_stage,
            "state": profile.state if profile else None,
            "university": profile.university if profile else None,
            "masters_interest": profile.masters_interest if profile else None,
            "masters_target": profile.masters_target if profile else None,
            "masters_timeline": profile.masters_timeline if profile else None,
            "masters_status": profile.masters_status if profile else None,
        },
        "resume_context": resume_context,
        "market_context": market_context or {},
        "top_gap_items": [
            {
                "id": str(item.id),
                "title": item.title,
                "allowed_proof_types": item.allowed_proof_types or [],
            }
            for item in gap_items
        ],
        "checklist_items": context_items,
        "milestones": [
            {
                "id": str(milestone.id),
                "title": milestone.title,
                "description": milestone.description,
                "semester_index": milestone.semester_index,
            }
            for milestone in milestones
        ],
    }

    raw = _call_llm(system, json.dumps(payload))
    parsed = _safe_json(raw)
    if not parsed:
        internship_actions = _internship_recommendations(academic_stage)
        return {
            "explanation": "AI response could not be parsed. Using rules-based fallback.",
            "decision": "Unable to generate AI decision. Using rules-based guidance.",
            "recommendations": _unique_list(
                internship_actions + list(readiness.get("next_actions", []))
            )[:3],
            "recommended_certificates": [],
            "materials_to_master": [],
            "market_top_skills": list((market_context or {}).get("top_skills", []))[:MARKET_GUIDE_SKILLS_LIMIT],
            "market_alignment": list((market_context or {}).get("market_alignment", []))[:4],
            "priority_focus_areas": [item.title for item in gap_items[:4]],
            "weekly_plan": [],
            "evidence_snippets": [f"Gap detected: {item.title}" for item in gap_items[:4]],
            "confidence_by_item": {},
            "next_actions": _unique_list(
                internship_actions + list(readiness.get("next_actions", []))
            )[:3],
            "suggested_proof_types": [],
            "cited_checklist_item_ids": [str(item.id) for item in gap_items],
            "resume_detected": resume_detected,
            "resume_strengths": [],
            "resume_improvements": [],
            "uncertainty": "AI output parse failure.",
        }

    allowed_proof_types = {
        proof_type
        for item in gap_items
        for proof_type in (item.allowed_proof_types or [])
    }
    suggested = _unique_list(parsed.get("suggested_proof_types", []))
    if allowed_proof_types:
        suggested = [p for p in suggested if p in allowed_proof_types]

    decision = parsed.get("decision") or ""
    recommendations = list(parsed.get("recommendations", []))[:3]
    internship_actions = _internship_recommendations(academic_stage)
    if not decision:
        if readiness.get("next_actions"):
            decision = "Focus on the next best actions to close your top gaps."
        else:
            decision = "Maintain readiness by keeping proofs current."
    if not recommendations:
        recommendations = list(readiness.get("next_actions", []))[:3]
    recommendations = _unique_list(internship_actions + recommendations)[:3]
    recommendations = _yearize_list(recommendations)[:3]
    next_actions = _unique_list(
        internship_actions + list(parsed.get("next_actions", []))
    )[:3]
    if not next_actions:
        next_actions = _unique_list(internship_actions + list(readiness.get("next_actions", [])))[:3]
    next_actions = _yearize_list(next_actions)[:3]
    decision = _yearize_text(decision)

    return {
        "explanation": _yearize_text(parsed.get("explanation", "")),
        "decision": decision,
        "recommendations": recommendations,
        "recommended_certificates": list(parsed.get("recommended_certificates", []))[:5],
        "materials_to_master": list(parsed.get("materials_to_master", []))[:6],
        "market_top_skills": list(parsed.get("market_top_skills", []))[:MARKET_GUIDE_SKILLS_LIMIT],
        "market_alignment": list(parsed.get("market_alignment", []))[:4],
        "priority_focus_areas": list(parsed.get("priority_focus_areas", []))[:4],
        "weekly_plan": _yearize_list(list(parsed.get("weekly_plan", []))[:6]),
        "evidence_snippets": _yearize_list(list(parsed.get("evidence_snippets", []))[:6]),
        "confidence_by_item": parsed.get("confidence_by_item")
        if isinstance(parsed.get("confidence_by_item"), dict)
        else {},
        "next_actions": next_actions,
        "suggested_proof_types": suggested,
        "cited_checklist_item_ids": parsed.get(
            "cited_checklist_item_ids",
            [str(item.id) for item in gap_items],
        ),
        "resume_detected": bool(parsed.get("resume_detected", resume_detected)),
        "resume_strengths": list(parsed.get("resume_strengths", []))[:4],
        "resume_improvements": list(parsed.get("resume_improvements", []))[:5],
        "uncertainty": parsed.get("uncertainty"),
    }


def _generate_admin_summary_with_llm(source_text: str, purpose: str | None) -> dict:
    system = (
        "You summarize market signals for admins. Output a single JSON object with "
        "keys: summary (string), rationale_draft (string or null)."
    )
    user = json.dumps({"purpose": purpose, "source_text": source_text})
    raw = _call_llm(system, user)
    parsed = _safe_json(raw)
    if not parsed:
        return {"summary": "Summary pending.", "rationale_draft": None}
    return {
        "summary": parsed.get("summary", "Summary pending."),
        "rationale_draft": parsed.get("rationale_draft"),
    }


def _generate_market_proposal_with_llm(
    *,
    signals: list[dict[str, Any]],
    instruction: str | None = None,
) -> dict[str, Any]:
    system = (
        "You are an admin market-intelligence copilot. "
        "Convert selected market signals into a checklist-update draft. "
        "Output a single JSON object with keys: "
        "summary (string), diff (object), uncertainty (string or null). "
        "The diff object should include: suggested_changes (array), signals (array). "
        "Each suggested_changes item should include action, target_skill, rationale, and priority."
    )
    payload = {"instruction": instruction, "signals": signals}
    raw = _call_llm(system, json.dumps(payload))
    parsed = _safe_json(raw)
    if not parsed:
        return {
            "summary": "Draft proposal pending.",
            "diff": {"signals": signals, "suggested_changes": []},
            "uncertainty": "AI output parse failure.",
        }
    return {
        "summary": parsed.get("summary", "Draft proposal pending."),
        "diff": parsed.get("diff")
        if isinstance(parsed.get("diff"), dict)
        else {"signals": signals, "suggested_changes": []},
        "uncertainty": parsed.get("uncertainty"),
    }


def _safe_json(text: str) -> dict[str, Any] | None:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            start = text.index("{")
            end = text.rindex("}") + 1
            return json.loads(text[start:end])
        except Exception:
            return None


def verify_proof_with_ai(
    *,
    checklist_item: ChecklistItem,
    proof_type: str,
    url: str,
    metadata: dict | None,
    profile: StudentProfile | None,
) -> dict:
    certificate_mode = _is_certificate_proof_type(proof_type)
    evidence_text = None
    evidence_meta: dict[str, Any] = {}
    if url.startswith("/uploads/"):
        local_path = Path(settings.local_upload_dir) / url.removeprefix("/uploads/")
        evidence_text = _extract_local_file_text(local_path)
        evidence_meta["source"] = "local_upload"
    elif is_s3_object_url(url):
        blob = read_s3_object_bytes(url, max_bytes=20000)
        evidence_text = _extract_text_from_bytes(blob) if blob else None
        evidence_meta["source"] = "s3_object"
    elif url.startswith("http://") or url.startswith("https://"):
        fetched_text, fetched_meta = _fetch_url_text(url)
        evidence_text = fetched_text
        if fetched_meta:
            evidence_meta.update(fetched_meta)
            evidence_meta["source"] = "url_fetch"
    else:
        evidence_meta["source"] = "unknown"

    system = (
        "You are an evidence verifier for career pathway proofs. "
        "Decide if the provided proof likely satisfies the checklist requirement. "
        "Assess authenticity likelihood from the available evidence and metadata, "
        "but do not claim legal or absolute authenticity. "
        "Output a single JSON object with keys: "
        "meets_requirement (boolean), confidence (0 to 1), "
        "issues (array of strings), decision (string: verified, needs_more_evidence, rejected), "
        "note (string for the student)."
    )
    if certificate_mode:
        system += (
            " This proof is a certificate upload. "
            "Prioritize issuer details, candidate identity cues, completion date, and credential/reference IDs. "
            "If authenticity cues are weak or missing, return needs_more_evidence with clear issues."
        )
    payload = {
        "checklist_item": {
            "title": checklist_item.title,
            "description": checklist_item.description,
            "rationale": checklist_item.rationale,
            "tier": checklist_item.tier,
            "is_critical": checklist_item.is_critical,
            "allowed_proof_types": checklist_item.allowed_proof_types or [],
        },
        "proof": {
            "proof_type": proof_type,
            "url": url,
            "metadata": metadata or {},
            "evidence_excerpt": evidence_text,
            "evidence_meta": evidence_meta,
        },
        "verification_focus": "certificate_authenticity" if certificate_mode else "standard",
        "student_profile": {
            "semester": profile.semester if profile else None,
            "state": profile.state if profile else None,
            "university": profile.university if profile else None,
            "masters_interest": profile.masters_interest if profile else None,
            "masters_target": profile.masters_target if profile else None,
            "masters_timeline": profile.masters_timeline if profile else None,
            "masters_status": profile.masters_status if profile else None,
        },
    }
    try:
        raw = _call_llm(system, json.dumps(payload))
    except Exception:
        return {
            "meets_requirement": False,
            "confidence": 0.0,
            "issues": ["AI verification service unavailable."],
            "decision": "needs_more_evidence",
            "note": "We could not verify this proof right now. Please try again.",
        }

    parsed = _safe_json(raw)
    if not parsed:
        return {
            "meets_requirement": False,
            "confidence": 0.0,
            "issues": ["AI response could not be parsed."],
            "decision": "needs_more_evidence",
            "note": "We could not verify this proof. Please provide additional evidence or details.",
        }

    decision = parsed.get("decision", "needs_more_evidence")
    confidence = parsed.get("confidence", 0.0)
    meets = bool(parsed.get("meets_requirement"))
    issues = parsed.get("issues") or []
    note = parsed.get("note") or ""

    return {
        "meets_requirement": meets,
        "confidence": float(confidence) if confidence is not None else 0.0,
        "issues": issues,
        "decision": decision,
        "note": note,
    }

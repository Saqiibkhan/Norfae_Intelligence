"""Provider-only projection of assistant facts and evidence.

The graph and evidence validator retain original service data. This module
creates fresh, bounded-safe JSON structures for external LLM prompts and
opaque aliases that are resolved only after provider output is parsed.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from app.ai_engine.evidence_validation import EvidenceConflict
from app.schemas.coordination_schema import AgentFinding


PROVIDER_FACT_ROOTS = frozenset({
    "profitability", "previous_period_profitability", "product_profitability",
    "products", "cities", "marketing_overview", "marketing_trends", "creatives",
    "anomalies", "anomaly_records", "data_quality",
})

_DROP_KEYS = frozenset({
    "normalizationpreview", "normalizationpreviews", "issues", "rawrecords",
    "recorddetails", "suggestedvalue", "auditmetadata", "internalmetadata",
    "generatedat",
    "debug", "providerresponse", "connectionstring", "dbconnectionstring",
    "databaseurl", "dburl", "connectionuri", "dsn",
    "password", "credential", "credentials", "secret", "token", "accesstoken",
    "refreshtoken", "apikey", "apitoken", "integrationtoken", "clientsecret",
    "privatekey", "secretkey", "accesskey", "bearertoken", "jwtsecret",
    "authorization", "permissions", "userid", "businessid", "tenantid",
    "id", "requestid", "executionid", "taskid", "traceid", "sourceservice",
    "evidenceref", "serviceobject", "dbsession", "databaseconnection", "rawsql",
    "membershipid", "recordid", "orderid", "productid", "creativeid",
    "campaignid", "adid", "adsetid", "anomalyid", "conversationid", "messageid",
    "externalid", "internalid", "integrationid", "ids",
})
_IDENTIFIER_SUFFIX = re.compile(r"(?:_id|_ids|Id|Ids|ID|IDS|identifier)$")
_IDENTIFIER_IN_METRIC = re.compile(r"^(product|creative|city)_([^_]+)_(.+)$")


class ProviderDataError(ValueError):
    """Raised when service data cannot be safely projected as bounded JSON."""


def _normalized_key(key: str) -> str:
    return "".join(character for character in key.casefold() if character.isalnum())


def _is_internal_key(key: str) -> bool:
    return (
        _normalized_key(key) in _DROP_KEYS
        or bool(_IDENTIFIER_SUFFIX.search(key))
        or key.casefold().endswith("identifier")
    )


def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise ProviderDataError("Provider data contained a non-string field.")
        return {
            key: _sanitize(item)
            for key, item in value.items()
            if not _is_internal_key(key)
        }
    if isinstance(value, (list, tuple)):
        return [_sanitize(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise ProviderDataError("Provider data contained an unsupported value.")


def sanitize_provider_facts(facts: dict[str, Any]) -> dict[str, Any]:
    """Allowlist known result roots and recursively remove internal fields.

    The input mapping is never mutated. Unexpected root keys and non-finite or
    non-JSON payloads fail closed rather than being forwarded to the provider.
    """
    if not isinstance(facts, dict) or any(key not in PROVIDER_FACT_ROOTS for key in facts):
        raise ProviderDataError("Assistant result shape is not approved for provider use.")
    safe = _sanitize(facts)
    try:
        json.dumps(safe, allow_nan=False, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError, OverflowError):
        raise ProviderDataError("Assistant result is not finite JSON data.") from None
    return safe


def _safe_metric_label(name: str) -> str:
    if name.startswith("anomaly_"):
        return "anomaly finding"
    match = _IDENTIFIER_IN_METRIC.match(name)
    if match:
        return f"{match.group(1)} {match.group(3).replace('_', ' ')}"
    return name.replace("_", " ")


@dataclass(frozen=True)
class ProviderEvidenceProjection:
    findings: list[dict[str, Any]]
    conflicts: list[dict[str, Any]]
    finding_aliases: dict[str, str]
    metric_aliases: dict[str, str]

    def restore_draft_references(self, draft):
        """Translate only recognized opaque provider aliases to internal IDs."""
        claims = [claim.model_copy(update={
            "finding_ids": [self.finding_aliases.get(item, item) for item in claim.finding_ids],
            "metric_name": self.metric_aliases.get(claim.metric_name, claim.metric_name),
        }) for claim in draft.claims]
        recommendation_intents = [intent.model_copy(update={
            "finding_ids": [self.finding_aliases.get(item, item) for item in intent.finding_ids],
        }) for intent in draft.recommendation_intents]
        return draft.model_copy(update={
            "claims": claims,
            "recommendation_intents": recommendation_intents,
        })


def project_provider_evidence(
    findings: list[AgentFinding], conflicts: list[EvidenceConflict],
) -> ProviderEvidenceProjection:
    """Hide internal finding, metric, source-service and result-key identifiers."""
    finding_aliases: dict[str, str] = {}
    metric_to_alias: dict[str, str] = {}
    metric_aliases: dict[str, str] = {}
    projected_findings: list[dict[str, Any]] = []

    for index, finding in enumerate(findings, start=1):
        finding_alias = f"finding_{index:03d}"
        metric_alias = metric_to_alias.setdefault(
            finding.name, f"metric_{len(metric_to_alias) + 1:03d}"
        )
        finding_aliases[finding_alias] = finding.finding_id
        metric_aliases[metric_alias] = finding.name
        projected_findings.append({
            "finding_id": finding_alias,
            "domain": finding.domain,
            "metric_name": metric_alias,
            "metric_label": _safe_metric_label(finding.name),
            "value": _sanitize(finding.value),
            "reporting_period": (
                finding.reporting_period.model_dump(mode="json")
                if finding.reporting_period else None
            ),
            "unit": finding.unit,
            "metric_definition": finding.metric_definition,
            "evidence_status": finding.evidence_status,
            "evidence_classification": finding.evidence_classification,
            "data_availability": finding.data_availability,
            "limitations": list(finding.limitations),
            "comparison": (
                finding.comparison.model_dump(
                    mode="json",
                    exclude={"current_evidence_ref", "previous_evidence_ref"},
                )
                if finding.comparison else None
            ),
        })

    projected_conflicts = []
    for index, conflict in enumerate(conflicts, start=1):
        projected_conflicts.append({
            "conflict_id": f"conflict_{index:03d}",
            "metric_name": metric_to_alias.get(conflict.metric_name, "unmapped_metric"),
            "finding_ids": [finding_aliases.get(item, "unmapped_finding")
                            for item in conflict.finding_ids],
            "category": conflict.category,
            "outcome": conflict.outcome,
            "explanation": conflict.explanation,
        })

    return ProviderEvidenceProjection(
        findings=projected_findings,
        conflicts=projected_conflicts,
        finding_aliases=finding_aliases,
        metric_aliases=metric_aliases,
    )

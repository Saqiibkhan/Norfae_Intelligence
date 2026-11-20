"""Deterministic request-scoped evidence validation and conflict classification."""

from __future__ import annotations

import json
from itertools import combinations
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.coordination_schema import AgentFinding, SharedFindingsContext
from app.schemas.assistant_schema import AssistantDraft, GroundedRecommendation


ConflictCategory = Literal[
    "VALUE_MISMATCH", "PERIOD_MISMATCH", "DEFINITION_MISMATCH",
    "SOURCE_UNAVAILABLE", "INSUFFICIENT_EVIDENCE",
]
ConflictOutcome = Literal["RESOLVED", "UNRESOLVED", "NOT_COMPARABLE", "INSUFFICIENT_DATA"]


class EvidenceConflict(BaseModel):
    conflict_id: str
    metric_name: str
    finding_ids: list[str] = Field(min_length=2, max_length=2)
    category: ConflictCategory
    outcome: ConflictOutcome
    explanation: str

    model_config = ConfigDict(extra="forbid", frozen=True)


class EvidenceValidationReport(BaseModel):
    findings: list[AgentFinding] = Field(default_factory=list)
    invalid_finding_ids: list[str] = Field(default_factory=list)
    safe_errors: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid", frozen=True)


def validate_shared_evidence(shared: SharedFindingsContext) -> EvidenceValidationReport:
    """Keep only findings backed by their own successful request-local task result."""
    validated: list[AgentFinding] = []
    invalid: list[str] = []
    errors: list[str] = []
    for finding_id, finding in shared.findings.items():
        source_result = next((
            result for result in shared.task_results.values()
            if finding_id in result.finding_ids
        ), None)
        reason = None
        if source_result is None:
            reason = "task_result_missing"
        elif source_result.status != "succeeded":
            reason = "task_result_not_successful"
        elif source_result.domain != finding.domain:
            reason = "source_domain_mismatch"
        elif source_result.result is None:
            reason = "source_result_missing"
        elif finding.evidence_ref is None or finding.evidence_ref not in source_result.result:
            reason = "evidence_reference_missing"
        elif (finding.comparison is not None and any(
                evidence_ref not in source_result.result
                for evidence_ref in (
                    finding.comparison.current_evidence_ref,
                    finding.comparison.previous_evidence_ref,
                )
        )):
            reason = "comparison_evidence_reference_missing"
        valid = reason is None
        if valid:
            validated.append(finding)
        else:
            invalid.append(finding_id)
            errors.append(reason or "evidence_reference_invalid")
    return EvidenceValidationReport(
        findings=validated,
        invalid_finding_ids=invalid,
        safe_errors=list(dict.fromkeys(errors)),
    )


def ground_assistant_draft(
    draft: AssistantDraft,
    shared: SharedFindingsContext,
    conflicts: list[EvidenceConflict],
    available_fact_ids: set[str],
) -> AssistantDraft:
    """Render only bounded claims and allowlisted recommendations backed by findings.

    Free-form LLM answer and recommendation text are deliberately not returned.
    Numeric and high-impact statement wording is generated from validated values.
    """
    report = validate_shared_evidence(shared)
    finding_by_id = {finding.finding_id: finding for finding in report.findings}
    conflicted_ids = {finding_id for conflict in conflicts for finding_id in conflict.finding_ids}
    rendered_claims: list[str] = []
    answer_refs: list[str] = []
    rejected = False

    for claim in draft.claims:
        findings = [finding_by_id.get(finding_id) for finding_id in claim.finding_ids]
        if not findings or any(finding is None for finding in findings):
            rejected = True
            continue
        concrete = [finding for finding in findings if finding is not None]
        period_start = claim.period_start
        period_end = claim.period_end
        valid = True
        for finding in concrete:
            period = finding.reporting_period
            if (
                finding.finding_id in conflicted_ids
                or finding.evidence_status not in {"verified", "estimated"}
                or finding.evidence_classification == "INFERRED"
                or finding.domain != claim.domain
                or finding.name != claim.metric_name
                or finding.unit != claim.unit
                or (period.start_date if period else None) != period_start
                or (period.end_date if period else None) != period_end
                or finding.value != claim.value
            ):
                valid = False
                break
            if claim.claim_type == "numeric":
                if (isinstance(claim.value, bool) or not isinstance(claim.value, (int, float))
                        or isinstance(finding.value, bool) or not isinstance(finding.value, (int, float))
                        or not finding.unit):
                    valid = False
                    break
            elif (isinstance(finding.value, bool)
                  or isinstance(finding.value, (int, float))):
                # Numeric assertions must use the numeric claim path, where unit
                # and exact value checks are mandatory.
                valid = False
                break
            if finding.comparison is not None and (
                claim.claim_type != "qualitative"
                or claim.value != finding.comparison.claim_value()
                or claim.period_start != finding.comparison.current_period_start
                or claim.period_end != finding.comparison.current_period_end
                or claim.unit != finding.comparison.unit
            ):
                valid = False
                break
        if not valid:
            rejected = True
            continue

        sources = list(dict.fromkeys(
            finding.evidence_ref for finding in concrete
            if finding.evidence_ref in available_fact_ids
        ))
        if not sources:
            rejected = True
            continue
        for source in sources:
            if source not in answer_refs:
                answer_refs.append(source)
        status_label = (
            "Estimated" if any(finding.evidence_status == "estimated" for finding in concrete)
            else "Recorded" if all(finding.evidence_classification == "OBSERVED" for finding in concrete)
            else "Calculated"
        )
        if concrete[0].comparison is not None:
            rendered_claims.append(_render_profitability_comparison(concrete[0]))
        else:
            value_text = json.dumps(claim.value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            unit_text = f" {claim.unit}" if claim.unit else ""
            period_text = (
                f" for {period_start.isoformat()} to {period_end.isoformat()}"
                if period_start and period_end else ""
            )
            rendered_claims.append(
                f"{status_label} {claim.metric_name.replace('_', ' ')}: {value_text}{unit_text}{period_text}."
            )

    comparison_notes = [
        _render_unavailable_comparison(finding)
        for finding in report.findings
        if finding.name == "net_profit_trend"
        and finding.comparison is not None
        and finding.comparison.status != "comparable"
    ]

    recommendations: list[GroundedRecommendation] = []
    for intent in draft.recommendation_intents:
        findings = [finding_by_id.get(finding_id) for finding_id in intent.finding_ids]
        if (not findings or any(finding is None for finding in findings)
                or any(finding.finding_id in conflicted_ids for finding in findings if finding)):
            rejected = True
            continue
        concrete = [finding for finding in findings if finding is not None]
        if intent.action == "collect_data":
            applicable = any(
                finding.evidence_status == "unavailable" or finding.value is None
                for finding in concrete
            )
            text = "Collect or complete source data for " + ", ".join(
                dict.fromkeys(finding.name.replace("_", " ") for finding in concrete)
            ) + " before relying on it."
        elif intent.action == "compare_periods":
            applicable = all(
                finding.evidence_status in {"verified", "estimated"}
                and ("trend" in finding.name or "previous" in finding.name
                     or (isinstance(finding.value, dict) and "direction" in finding.value))
                for finding in concrete
            )
            text = "Compare " + ", ".join(
                dict.fromkeys(finding.name.replace("_", " ") for finding in concrete)
            ) + " only across the stated reporting periods, accounting for their limitations."
        else:
            applicable = all(
                finding.evidence_status in {"verified", "estimated"}
                and finding.evidence_classification != "INFERRED"
                for finding in concrete
            )
            text = "Review the recorded evidence for " + ", ".join(
                dict.fromkeys(finding.name.replace("_", " ") for finding in concrete)
            ) + " and its stated limitations."
        refs = list(dict.fromkeys(
            finding.evidence_ref for finding in concrete
            if finding.evidence_ref in available_fact_ids
        ))
        if not applicable or not refs:
            rejected = True
            continue
        recommendations.append(GroundedRecommendation(text=text, evidence_ids=refs[:5]))

    answer = " ".join([*rendered_claims, *comparison_notes])
    unknowns = [
        "Some requested metrics were unavailable in the source data."
        for finding in report.findings if finding.evidence_status == "unavailable"
    ][:1]
    if rejected:
        unknowns.append("Some generated claims or recommendations could not be verified and were omitted.")
    if not answer:
        answer = "I could not validate a factual claim against the available evidence. Please review the verified facts below."
    return draft.model_copy(update={
        "answer": answer[:3000],
        "answer_evidence_ids": answer_refs[:8],
        "interpretation": "",
        "recommendations": recommendations[:5],
        "unknowns": list(dict.fromkeys(unknowns))[:10],
    })


def _format_comparison_amount(value: float) -> str:
    return f"{value:,.2f}"


def _period_text(start, end) -> str:
    if start is None or end is None:
        return "an unspecified period"
    return f"{start.isoformat()} to {end.isoformat()}"


def _render_profitability_comparison(finding: AgentFinding) -> str:
    comparison = finding.comparison
    if comparison is None or comparison.status != "comparable":
        return "A net-profit comparison is unavailable."
    prefix = "Estimated" if finding.evidence_status == "estimated" else "Calculated"
    if comparison.direction == "increase":
        direction = "increased"
    elif comparison.direction == "decrease":
        direction = "decreased"
    else:
        direction = "did not change"
    unit = comparison.unit or ""
    unit_suffix = f" {unit}" if unit else ""
    absolute = _format_comparison_amount(comparison.absolute_change)
    if comparison.absolute_change > 0:
        absolute = "+" + absolute
    if comparison.percentage_change is None:
        percentage_text = "Percentage change is unavailable because previous-period net profit is zero."
    else:
        percentage = f"{comparison.percentage_change:+,.2f}%"
        percentage_text = (
            f"Percentage change: {percentage}, measured against the absolute previous-period value."
        )
    return (
        f"{prefix} net profit {direction} from {_format_comparison_amount(comparison.previous_value)}"
        f"{unit_suffix} in {_period_text(comparison.previous_period_start, comparison.previous_period_end)} "
        f"to {_format_comparison_amount(comparison.current_value)}{unit_suffix} in "
        f"{_period_text(comparison.current_period_start, comparison.current_period_end)}. "
        f"Absolute change: {absolute}{unit_suffix}. {percentage_text} "
        "This comparison does not establish a cause."
    )


def _render_unavailable_comparison(finding: AgentFinding) -> str:
    comparison = finding.comparison
    current = _period_text(comparison.current_period_start, comparison.current_period_end)
    previous = _period_text(comparison.previous_period_start, comparison.previous_period_end)
    explanations = {
        "current_value_unavailable": "current-period net profit is unavailable",
        "previous_value_unavailable": "previous-period net profit is unavailable",
        "both_values_unavailable": "both period values are unavailable",
        "periods_incompatible": "the periods are not adjacent equal-length intervals",
        "unit_mismatch": "the period values use incompatible units",
        "source_mismatch": "the period values come from incompatible sources",
    }
    reason = explanations.get(comparison.unavailable_reason, "the comparison inputs are incomplete")
    return (
        f"A net-profit comparison cannot be calculated: current period {current}; "
        f"previous period {previous}; {reason}. No comparison value or cause is inferred."
    )


def detect_evidence_conflicts(findings: list[AgentFinding]) -> list[EvidenceConflict]:
    """Compare same-name metrics only; different metrics are never treated as conflicts."""
    conflicts: list[EvidenceConflict] = []
    for left, right in combinations(findings, 2):
        if left.name != right.name or left.finding_id == right.finding_id:
            continue
        pair = sorted((left.finding_id, right.finding_id))
        def add(category: ConflictCategory, outcome: ConflictOutcome, why: str):
            conflicts.append(EvidenceConflict(
                conflict_id=f"conflict:{pair[0]}:{pair[1]}",
                metric_name=left.name,
                finding_ids=pair,
                category=category,
                outcome=outcome,
                explanation=why,
            ))

        if left.unit != right.unit or (
            left.metric_definition and right.metric_definition
            and left.metric_definition != right.metric_definition
        ):
            add("DEFINITION_MISMATCH", "NOT_COMPARABLE",
                "The findings use different units or metric definitions.")
        elif left.reporting_period != right.reporting_period:
            add("PERIOD_MISMATCH", "NOT_COMPARABLE",
                "The findings cover different or unspecified reporting periods.")
        elif (left.evidence_classification == "UNAVAILABLE"
              or right.evidence_classification == "UNAVAILABLE"
              or left.value is None or right.value is None):
            add("SOURCE_UNAVAILABLE", "INSUFFICIENT_DATA",
                "At least one source has no available value for this metric.")
        elif (left.evidence_classification == "INFERRED"
              or right.evidence_classification == "INFERRED"
              or left.evidence_status == "estimated" or right.evidence_status == "estimated"):
            add("INSUFFICIENT_EVIDENCE", "INSUFFICIENT_DATA",
                "At least one value is inferred or estimated and cannot settle the comparison.")
        elif left.value != right.value:
            add("VALUE_MISMATCH", "UNRESOLVED",
                "Compatible sources report different values; neither source is preferred.")
    return conflicts


def enforce_conflict_policy(
    draft: AssistantDraft,
    conflicts: list[EvidenceConflict],
    findings: list[AgentFinding],
    available_fact_ids: set[str],
) -> AssistantDraft:
    """Keep unresolved determinations authoritative over generated prose."""
    if not conflicts:
        return draft
    classified_conflicts = [conflict for conflict in conflicts if conflict.outcome != "RESOLVED"]
    visible_notes = [
        f"{conflict.metric_name}: {conflict.explanation} Classification: {conflict.outcome}."
        for conflict in conflicts
    ]
    if not classified_conflicts:
        draft.unknowns = list(dict.fromkeys([*draft.unknowns, *visible_notes]))[:10]
        return draft

    finding_by_id = {finding.finding_id: finding for finding in findings}
    answer_lines: list[str] = []
    references: list[str] = []
    for conflict in classified_conflicts:
        left, right = (finding_by_id.get(item) for item in conflict.finding_ids)
        if left is None or right is None:
            continue
        left_period = _period_label(left)
        right_period = _period_label(right)
        if conflict.outcome == "UNRESOLVED":
            answer_lines.append(
                f"The available sources report different {conflict.metric_name} values "
                f"({left.value} for {left_period}; {right.value} for {right_period}). "
                "This discrepancy is unresolved; neither source is treated as authoritative. "
                "The available evidence does not establish its cause."
            )
        elif conflict.outcome == "NOT_COMPARABLE":
            answer_lines.append(
                f"The {conflict.metric_name} evidence is not comparable because "
                f"{conflict.explanation} Reporting periods are {left_period} and {right_period}."
            )
        else:
            answer_lines.append(
                f"There is insufficient evidence to determine {conflict.metric_name}: "
                f"{conflict.explanation}"
            )
        for finding in (left, right):
            if finding.evidence_ref in available_fact_ids and finding.evidence_ref not in references:
                references.append(finding.evidence_ref)
    if not answer_lines:
        answer_lines = ["The available evidence contains an unresolved conflict. Its cause cannot be established from these results."]
    return AssistantDraft(
        answer=" ".join(answer_lines)[:3000],
        answer_evidence_ids=references[:8],
        interpretation="Evidence classifications and comparison limits were determined by the deterministic validation layer.",
        recommendations=[],
        unknowns=list(dict.fromkeys([*draft.unknowns, *visible_notes]))[:10],
    )


def _period_label(finding: AgentFinding) -> str:
    period = finding.reporting_period
    if period is None:
        return "an unspecified reporting period"
    return f"{period.start_date.isoformat()} to {period.end_date.isoformat()}"

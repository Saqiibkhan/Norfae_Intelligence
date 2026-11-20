"""Deterministic, schema-backed extraction of bounded findings from service results."""

from datetime import date, timedelta
from typing import Any

from pydantic import BaseModel

from app.ai_engine.task_adapters import (
    AnomalyTaskOutput,
    CityTaskOutput,
    CreativeTaskOutput,
    DataQualityTaskOutput,
    MarketingTaskOutput,
    ProductTaskOutput,
    ProfitabilityTaskOutput,
)
from app.schemas.coordination_schema import AgentFinding, ProfitabilityComparison, ReportingPeriod
from app.services.deterministic_profitability_service import _decimal, _rounded


def _period(start: date | None, end: date | None) -> ReportingPeriod | None:
    return ReportingPeriod(start_date=start, end_date=end) if start and end else None


def _limitations(*sources) -> list[str]:
    values: list[str] = []
    for source in sources:
        for value in source or []:
            item = str(value).strip()[:500]
            if item and item not in values:
                values.append(item)
            if len(values) == 20:
                return values
    return values


def _finding(
    *, task_id: str, domain: str, name: str, value: Any, period: ReportingPeriod | None,
    source_service: str, evidence_ref: str | None, status: str, limitations: list[str] | None = None,
    classification: str | None = None, unit: str | None = None,
    metric_definition: str | None = None,
) -> AgentFinding:
    normalized_name = name.casefold()
    if unit is None:
        unit = ("percent" if "margin" in normalized_name or "ctr" in normalized_name
                else "ratio" if "roas" in normalized_name
                else "count" if any(token in normalized_name for token in ("count", "records_inspected", "valid_records", "invalid_records"))
                else "currency_amount" if any(token in normalized_name for token in ("profit", "revenue", "contribution", "spend", "cost", "value"))
                else None)
    if classification is None:
        classification = (
            "UNAVAILABLE" if status == "unavailable"
            else "OBSERVED" if domain == "creatives" and normalized_name.endswith(("_spend", "_revenue", "_recorded_roas", "_recorded_ctr"))
            else "CALCULATED"
        )
    definitions = {
        "net_profit": "recognized delivered revenue less available recorded costs; incomplete cost data may make this an estimate",
        "previous_net_profit": "recognized delivered revenue less available recorded costs in the preceding equal-length period",
        "net_profit_trend": "comparison of current and preceding equal-length net-profit periods",
        "roas": "attributed conversion value divided by advertising spend",
    }
    return AgentFinding(
        finding_id=f"{task_id}:{name}",
        domain=domain,
        name=name,
        value=value,
        reporting_period=period,
        source_service=source_service,
        evidence_ref=evidence_ref,
        evidence_status=status,
        evidence_classification=classification,
        unit=unit,
        metric_definition=metric_definition or definitions.get(name),
        limitations=limitations or [],
    )


def _component_finding(*, task_id, domain, name, component, period, source_service, evidence_ref, complete, limitations):
    if not component.available or component.amount is None:
        value, status = None, "unavailable"
    else:
        value = component.amount
        status = "verified" if complete else "estimated"
    return _finding(
        task_id=task_id, domain=domain, name=name, value=value, period=period,
        source_service=source_service, evidence_ref=evidence_ref,
        status=status, limitations=limitations,
    )


def _profitability_comparison(current_finding: AgentFinding, previous_finding: AgentFinding):
    current_period = current_finding.reporting_period
    previous_period = previous_finding.reporting_period
    current_value = current_finding.value
    previous_value = previous_finding.value
    current_ref = current_finding.evidence_ref or "profitability"
    previous_ref = previous_finding.evidence_ref or "previous_period_profitability"
    common = {
        "current_period_start": current_period.start_date if current_period else None,
        "current_period_end": current_period.end_date if current_period else None,
        "previous_period_start": previous_period.start_date if previous_period else None,
        "previous_period_end": previous_period.end_date if previous_period else None,
        "current_value": current_value,
        "previous_value": previous_value,
        "current_evidence_ref": current_ref,
        "previous_evidence_ref": previous_ref,
        "comparison_definition": (
            "Net profit is recorded delivered-order revenue less available recorded costs; "
            "the same deterministic service definition is applied to equal-length adjacent periods."
        ),
    }

    reason = None
    status = "unavailable"
    if current_period is None or previous_period is None:
        status, reason = "incompatible", "periods_incompatible"
    elif (current_period.end_date - current_period.start_date
          != previous_period.end_date - previous_period.start_date
          or previous_period.end_date + timedelta(days=1) != current_period.start_date):
        status, reason = "incompatible", "periods_incompatible"
    elif current_finding.source_service != previous_finding.source_service:
        status, reason = "incompatible", "source_mismatch"
    elif current_finding.unit is None or current_finding.unit != previous_finding.unit:
        status, reason = "incompatible", "unit_mismatch"
    elif current_value is None and previous_value is None:
        reason = "both_values_unavailable"
    elif current_value is None:
        reason = "current_value_unavailable"
    elif previous_value is None:
        reason = "previous_value_unavailable"
    else:
        current_decimal = _decimal(current_value)
        previous_decimal = _decimal(previous_value)
        if current_decimal is None or previous_decimal is None:
            reason = "both_values_unavailable"
        else:
            delta = current_decimal - previous_decimal
            percentage = (
                None if previous_decimal == 0
                else _rounded(delta / abs(previous_decimal) * 100)
            )
            comparison = ProfitabilityComparison(
                **common,
                absolute_change=_rounded(delta),
                percentage_change=percentage,
                direction="increase" if delta > 0 else "decrease" if delta < 0 else "unchanged",
                unit=current_finding.unit,
                status="comparable",
            )
            return comparison

    return ProfitabilityComparison(
        **common,
        absolute_change=None,
        percentage_change=None,
        direction="unavailable",
        unit=(current_finding.unit if current_finding.unit == previous_finding.unit else None),
        status=status,
        unavailable_reason=reason,
    )


def extract_findings(task_id: str, domain: str, output: BaseModel) -> list[AgentFinding]:
    """Extract only metrics exposed by the typed deterministic service output."""
    if isinstance(output, ProfitabilityTaskOutput):
        current = output.profitability
        previous = output.previous_period_profitability
        current_period = _period(current.start_date, current.end_date)
        previous_period = _period(previous.start_date, previous.end_date)
        current_limitations = _limitations(current.warnings)
        previous_limitations = _limitations(previous.warnings)
        current_profit = _component_finding(
            task_id=task_id, domain=domain, name="net_profit", component=current.net_profit,
            period=current_period, source_service="DeterministicProfitabilityService.overall",
            evidence_ref="profitability", complete=current.complete, limitations=current_limitations,
        )
        previous_profit = _component_finding(
            task_id=task_id, domain=domain, name="previous_net_profit", component=previous.net_profit,
            period=previous_period, source_service="DeterministicProfitabilityService.overall",
            evidence_ref="previous_period_profitability", complete=previous.complete,
            limitations=previous_limitations,
        )
        comparison = _profitability_comparison(current_profit, previous_profit)
        can_compare = comparison.status == "comparable"
        trend = _finding(
            task_id=task_id, domain=domain, name="net_profit_trend",
            value=comparison.claim_value() if can_compare else None,
            period=current_period, source_service="DeterministicProfitabilityService.overall",
            evidence_ref="profitability",
            status=("unavailable" if not can_compare else
                    "verified" if current_profit.evidence_status == previous_profit.evidence_status == "verified"
                    else "estimated"),
            limitations=_limitations(current_limitations, previous_limitations,
                                      ["Percentage change uses the absolute previous-period value as its denominator; it is undefined when that value is zero.",
                                       "A period comparison does not establish a cause."]),
        )
        trend = trend.model_copy(update={"comparison": comparison, "unit": comparison.unit})
        return [current_profit, previous_profit, trend]

    if isinstance(output, ProductTaskOutput):
        page = output.products
        period = _period(page.start_date, page.end_date)
        findings = []
        for product in page.products:
            findings.append(_component_finding(
                task_id=task_id, domain=domain,
                name=f"product_{product.product_id}_contribution",
                component=product.product_contribution, period=period,
                source_service="ProductIntelligenceService.analyze_business",
                evidence_ref="products", complete=product.product_contribution.available,
                limitations=_limitations(product.warnings, page.warnings),
            ))
            findings.append(_finding(
                task_id=task_id, domain=domain,
                name=f"product_{product.product_id}_contribution_margin",
                value=product.contribution_margin_percent, period=period,
                source_service="ProductIntelligenceService.analyze_business", evidence_ref="products",
                status="unavailable" if product.contribution_margin_percent is None else "verified",
                limitations=_limitations(product.warnings, page.warnings),
            ))
        return findings

    if isinstance(output, CityTaskOutput):
        page = output.cities
        period = _period(page.start_date, page.end_date)
        findings = []
        for index, city in enumerate(page.cities):
            city_label = city.city or f"unknown_{index + 1}"
            findings.append(_component_finding(
                task_id=task_id, domain=domain, name=f"city_{index + 1}_revenue",
                component=city.total_revenue, period=period,
                source_service="CityIntelligenceService.analyze_business", evidence_ref="cities",
                complete=city.total_revenue.available, limitations=_limitations(city.warnings, page.warnings),
            ))
            findings.append(_finding(
                task_id=task_id, domain=domain, name=f"city_{index + 1}_contribution_margin",
                value=city.contribution_margin_percent, period=period,
                source_service="CityIntelligenceService.analyze_business", evidence_ref="cities",
                status="unavailable" if city.contribution_margin_percent is None else "verified",
                limitations=_limitations(city.warnings, page.warnings),
            ))
            findings[-2] = findings[-2].model_copy(update={
                "value": ({"city": city_label, "amount": findings[-2].value}
                          if findings[-2].value is not None else None),
                "evidence_status": (findings[-2].evidence_status if findings[-2].value is not None else "unavailable"),
            })
        return findings

    if isinstance(output, MarketingTaskOutput):
        overview = output.marketing_overview
        period = _period(overview.start_date, overview.end_date)
        warnings = _limitations(overview.warnings, output.marketing_trends.warnings,
                                [overview.observed_revenue_attribution_note])
        findings = []
        for metric_name in ("spend", "attributed_conversion_value", "observed_business_revenue",
                            "observed_business_profit_estimate"):
            metric = getattr(overview, metric_name)
            findings.append(_finding(
                task_id=task_id, domain=domain, name=metric_name,
                value=metric.amount if metric.available else None, period=period,
                source_service="MarketingIntelligenceService.overview", evidence_ref="marketing_overview",
                status="verified" if metric.available and metric.amount is not None else "unavailable",
                limitations=warnings,
            ))
        findings.append(_finding(
            task_id=task_id, domain=domain, name="roas", value=overview.roas, period=period,
            source_service="MarketingIntelligenceService.overview", evidence_ref="marketing_overview",
            status="unavailable" if overview.roas is None else "estimated",
            limitations=warnings,
        ))
        return findings

    if isinstance(output, CreativeTaskOutput):
        page = output.creatives
        period = _period(page.start_date, page.end_date)
        findings = []
        for creative in page.creatives:
            for metric_name in ("spend", "revenue", "recorded_roas", "recorded_ctr"):
                metric = getattr(creative, metric_name)
                findings.append(_finding(
                    task_id=task_id, domain=domain,
                    name=f"creative_{creative.creative_id}_{metric_name}",
                    value=metric.amount if metric.available else None, period=period,
                    source_service="CreativeIntelligenceService.list_creatives", evidence_ref="creatives",
                    status="verified" if metric.available and metric.amount is not None else "unavailable",
                    limitations=_limitations([metric.note]),
                ))
        return findings

    if isinstance(output, AnomalyTaskOutput):
        report = output.anomaly_records
        findings = []
        for anomaly in report.anomalies:
            findings.append(_finding(
                task_id=task_id, domain=domain, name=f"anomaly_{anomaly.anomaly_id}",
                value={"metric": anomaly.metric_name, "observed": anomaly.observed_value,
                       "expected": anomaly.expected_value, "severity": anomaly.severity},
                period=ReportingPeriod(start_date=anomaly.period_start, end_date=anomaly.period_end),
                source_service="AnomalyDetectionService.detect", evidence_ref="anomaly_records",
                status="verified", limitations=_limitations(report.warnings, report.insufficient_data),
            ))
        return findings

    if isinstance(output, DataQualityTaskOutput):
        report = output.data_quality
        return [
            _finding(
                task_id=task_id, domain=domain, name=name, value=getattr(report, name), period=None,
                source_service="DataQualityService.analyze", evidence_ref="data_quality",
                status="verified", limitations=_limitations(report.warnings),
            )
            for name in ("total_records_inspected", "valid_records", "invalid_records")
        ]
    return []

"""Deterministic feature-deviation explanations for hybrid anomaly decisions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np
import pandas as pd

from app.ml.hybrid_decision import HybridAnomalyDecision, HybridDecisionSource
from app.services.alarm_templates import guidance_for
from app.utils.enums import AnomalyType


FEATURE_DISPLAY_NAMES = {
    "flow_rate": "Pompa debisi", "pressure": "Hat basıncı", "motor_current": "Motor akımı",
    "pump_temperature": "Pompa sıcaklığı", "temperature": "Tank sıcaklığı",
    "water_level": "Tank su seviyesi", "tank_level": "Ölçülen tank seviyesi",
    "true_tank_level": "Gerçek tank seviyesi", "flow_rate_change_5min": "5 dakikalık debi değişimi",
    "motor_current_change_5min": "5 dakikalık motor akımı değişimi",
    "average_flow_rate_30min": "30 dakikalık ortalama debi",
    "pressure_std_30min": "30 dakikalık basınç değişkenliği",
}

QUALITY_FLAG_NOTES = {
    "SENSOR_STUCK": "Sensör değeri olağandışı bir süre boyunca değişmedi.",
    "SENSOR_SPIKE": "Sensör değerinde ani bir sıçrama algılandı.",
    "TIMESTAMP_ERROR": "Ölçüm zaman damgasında tutarsızlık algılandı.",
    "MISSING_DATA": "Gerekli sensör verisi eksik.",
    "MISSING_RELATION": "Sensör ölçümünün ekipman bağlantısı eksik.",
    "PHYSICAL_RANGE_VIOLATION": "Bir değer fiziksel çalışma aralığının dışında.",
    "TANK_SALES_MISMATCH": "Tank seviyesi değişimi kayıtlı satış örüntüsüyle uyuşmuyor.",
}


class ExplanationSource(str, Enum):
    RULE = "RULE"
    MODEL_DEVIATION = "MODEL_DEVIATION"
    DATA_QUALITY = "DATA_QUALITY"
    HYBRID = "HYBRID"


@dataclass(frozen=True)
class FeatureReferenceStats:
    median: float
    q05: float
    q25: float
    q75: float
    q95: float


@dataclass(frozen=True)
class FeatureReferenceProfile:
    family: str
    feature_names: tuple[str, ...]
    statistics: dict[str, FeatureReferenceStats]


@dataclass(frozen=True)
class AnomalyFinding:
    feature_name: str
    display_name: str
    current_value: float
    reference_value: float
    absolute_difference: float
    percent_difference: float | None
    direction: str
    deviation_score: float
    message: str


@dataclass(frozen=True)
class RuleEvidence:
    rule_code: str
    message: str


@dataclass(frozen=True)
class AnomalyExplanation:
    title: str
    summary: str
    findings: tuple[AnomalyFinding, ...]
    rule_evidence: tuple[RuleEvidence, ...]
    probable_causes: tuple[str, ...]
    recommended_checks: tuple[str, ...]
    decision_source: HybridDecisionSource
    risk_score: float | None
    anomaly_type: AnomalyType | None
    data_quality_note: str | None
    explanation_sources: tuple[ExplanationSource, ...]


class AnomalyExplanationService:
    """Explain deviations from an in-memory training baseline, not model attribution."""

    def fit_reference(self, features: pd.DataFrame, *, family: str) -> FeatureReferenceProfile:
        if features.empty or features.shape[1] == 0:
            raise ValueError("Reference features cannot be empty.")
        if features.columns.has_duplicates:
            raise ValueError("Reference features cannot contain duplicate names.")
        try:
            numeric = features.astype(float)
        except (TypeError, ValueError) as exc:
            raise ValueError("Reference features must be numeric.") from exc
        if not np.isfinite(numeric.to_numpy()).all():
            raise ValueError("Reference features must not contain NaN or infinity.")
        return FeatureReferenceProfile(
            family=family, feature_names=tuple(numeric.columns),
            statistics={
                name: FeatureReferenceStats(
                    median=float(numeric[name].quantile(0.50)), q05=float(numeric[name].quantile(0.05)),
                    q25=float(numeric[name].quantile(0.25)), q75=float(numeric[name].quantile(0.75)),
                    q95=float(numeric[name].quantile(0.95)),
                )
                for name in numeric.columns
            },
        )

    def explain(
        self,
        decision: HybridAnomalyDecision,
        features: pd.Series | dict[str, float],
        profile: FeatureReferenceProfile,
        *,
        quality_flags: tuple[str, ...] = (),
        top_limit: int = 3,
    ) -> AnomalyExplanation | None:
        if not decision.is_anomaly:
            return None
        if top_limit <= 0:
            raise ValueError("top_limit must be positive.")
        values = self._validate_row(features, profile)
        findings = self._findings(values, profile, top_limit)
        evidence = tuple(RuleEvidence(code, guidance_for(code)[0]) for code in decision.triggered_rule_codes)
        causes, checks = self._rule_guidance(decision.triggered_rule_codes)
        quality_note = self._quality_note(decision.data_quality_limited, quality_flags)
        sources = self._sources(decision, bool(findings), quality_note is not None)
        return AnomalyExplanation(
            title=self._title(decision), summary=self._summary(decision), findings=findings,
            rule_evidence=evidence, probable_causes=causes, recommended_checks=checks,
            decision_source=decision.decision_source, risk_score=decision.risk_score,
            anomaly_type=decision.anomaly_type, data_quality_note=quality_note,
            explanation_sources=sources,
        )

    @staticmethod
    def _validate_row(features: pd.Series | dict[str, float], profile: FeatureReferenceProfile) -> pd.Series:
        row = pd.Series(features, dtype=float)
        missing = [name for name in profile.feature_names if name not in row.index]
        if missing:
            raise ValueError(f"Inference features are missing reference columns: {', '.join(missing)}.")
        row = row.loc[list(profile.feature_names)]
        if not np.isfinite(row.to_numpy()).all():
            raise ValueError("Inference features must not contain NaN or infinity.")
        return row

    @staticmethod
    def _findings(values: pd.Series, profile: FeatureReferenceProfile, limit: int) -> tuple[AnomalyFinding, ...]:
        findings = []
        for name in profile.feature_names:
            stats, current = profile.statistics[name], float(values[name])
            difference = current - stats.median
            iqr = stats.q75 - stats.q25
            scale = max(abs(iqr), abs(stats.median) * 0.05, 1e-9)
            score = abs(difference) / scale
            percent = None if abs(stats.median) < 1e-9 else difference / abs(stats.median) * 100
            direction = "HIGH" if difference > 0 else "LOW" if difference < 0 else "NORMAL"
            findings.append(AnomalyFinding(
                name, FEATURE_DISPLAY_NAMES.get(name, name.replace("_", " ").title()), current,
                stats.median, abs(difference), percent, direction, score,
                AnomalyExplanationService._finding_message(name, difference, percent, stats.median),
            ))
        return tuple(sorted(findings, key=lambda item: (-item.deviation_score, item.feature_name))[:limit])

    @staticmethod
    def _finding_message(name: str, difference: float, percent: float | None, median: float) -> str:
        display = FEATURE_DISPLAY_NAMES.get(name, name.replace("_", " "))
        direction = "üzerinde" if difference > 0 else "altında" if difference < 0 else "düzeyinde"
        if percent is None:
            # Change/rate features commonly have a mathematically correct zero median.
            # Showing "normal median (0.00)" is technically true but operationally opaque.
            return f"{display}, öğrenilen olağan davranış aralığının {direction}."
        return f"{display}, normal medyanın yaklaşık %{abs(percent):.1f} {direction}."

    @staticmethod
    def _rule_guidance(codes: tuple[str, ...]) -> tuple[tuple[str, ...], tuple[str, ...]]:
        causes, checks = [], []
        for code in codes:
            _, recommendation, probable = guidance_for(code)
            causes.extend(item["description"] for item in probable)
            checks.append(recommendation)
        return tuple(dict.fromkeys(causes)), tuple(dict.fromkeys(checks))

    @staticmethod
    def _quality_note(limited: bool, flags: tuple[str, ...]) -> str | None:
        if not limited:
            return None
        details = " ".join(QUALITY_FLAG_NOTES[flag] for flag in flags if flag in QUALITY_FLAG_NOTES)
        return "Sensör verisinin güvenilirliği düşük; yapay zekâ riskini yalnızca destekleyici bilgi olarak değerlendirin." + (f" {details}" if details else "")

    @staticmethod
    def _sources(decision: HybridAnomalyDecision, has_findings: bool, has_quality: bool) -> tuple[ExplanationSource, ...]:
        sources = []
        if decision.decision_source in {HybridDecisionSource.RULE, HybridDecisionSource.HYBRID}:
            sources.append(ExplanationSource.RULE)
        if has_findings and decision.decision_source in {HybridDecisionSource.MODEL, HybridDecisionSource.HYBRID}:
            sources.append(ExplanationSource.MODEL_DEVIATION)
        if has_quality:
            sources.append(ExplanationSource.DATA_QUALITY)
        if decision.decision_source is HybridDecisionSource.HYBRID:
            sources.append(ExplanationSource.HYBRID)
        return tuple(sources)

    @staticmethod
    def _title(decision: HybridAnomalyDecision) -> str:
        return {
            HybridDecisionSource.HYBRID: "Yüksek Riskli Hibrit Anomali Uyarısı",
            HybridDecisionSource.RULE: "Kural Tabanlı Çalışma Sınırı İhlali",
            HybridDecisionSource.MODEL: "Yapay Zekâ Erken Uyarısı",
            HybridDecisionSource.DATA_QUALITY: "Sensör Verisi Güvenilirlik Uyarısı",
        }.get(decision.decision_source, "Anomali Uyarısı")

    @staticmethod
    def _summary(decision: HybridAnomalyDecision) -> str:
        if decision.decision_source is HybridDecisionSource.MODEL:
            return "Sensör değerlerinin birleşimi öğrenilen normal davranıştan anlamlı biçimde farklı; bu sonuç kesin bir arıza teşhisi değildir."
        if decision.decision_source is HybridDecisionSource.HYBRID:
            return "Tanımlı çalışma kuralı ile anomali modeli aynı olağandışı çalışma durumuna işaret ediyor."
        if decision.decision_source is HybridDecisionSource.DATA_QUALITY:
            return "Sensör verisi kalitesi, yapay zekâ yorumuna duyulan güveni sınırlıyor."
        return "Tanımlı çalışma kuralı aşıldı; durum incelenmelidir."

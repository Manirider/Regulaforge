"""Natural language explanation generator for AI predictions.

Transforms technical explanations (SHAP, LIME, etc.) into human-readable
narratives tailored to different audiences: technical teams, compliance
officers, executives, and regulators.
"""

from __future__ import annotations

from typing import Optional

from regulaforge.application.ports.llm_provider import (
    LLMMessage,
    LLMProvider,
)
from regulaforge.config.logging import get_logger
from regulaforge.xai.domain.models import (
    Explanation,
    FeatureContribution,
    NaturalLanguageExplanation,
)

logger = get_logger(__name__)


class NaturalLanguageExplainer:
    """Generates audience-adapted natural language explanations.

    Uses templated prompts and optional LLM integration to produce
    explanations that match the vocabulary, depth, and concerns of
    different stakeholder groups in the compliance domain.
    """

    def __init__(
        self,
        llm_provider: Optional[LLMProvider] = None,
    ) -> None:
        self._llm = llm_provider
        logger.info(
            "NaturalLanguageExplainer initialized: llm_available=%s",
            llm_provider is not None,
        )

    async def generate_explanation(
        self,
        explanation: Explanation,
        audience: str = "technical",
        detail_level: str = "detailed",
    ) -> NaturalLanguageExplanation:
        """Generate a natural language explanation adapted to the audience.

        Args:
            explanation: The technical explanation to convert.
            audience: Target audience (technical, compliance_officer, executive, regulator).
            detail_level: Level of detail (basic, detailed, comprehensive).

        Returns:
            NaturalLanguageExplanation with audience-adapted content.
        """
        if self._llm is not None:
            try:
                return await self._generate_with_llm(explanation, audience, detail_level)
            except Exception as exc:
                logger.warning(
                    "LLM explanation generation failed, using templates: %s",
                    exc,
                )

        return self._generate_with_templates(explanation, audience, detail_level)

    def summarize_risk_factors(
        self,
        features: list[FeatureContribution],
    ) -> list[str]:
        """Identify and describe key risk drivers in plain language.

        Args:
            features: List of feature contributions from the explanation.

        Returns:
            List of human-readable risk factor descriptions.
        """
        if not features:
            return ["No risk factors identified."]

        sorted_features = sorted(features, key=lambda f: abs(f.contribution), reverse=True)
        risk_factors: list[str] = []

        for f in sorted_features[:5]:
            if f.direction == "positive":
                risk_factors.append(
                    f"Increased risk due to '{f.feature_name}' "
                    f"(value: {f.feature_value}, impact: {abs(f.contribution):.3f})"
                )
            elif f.direction == "negative":
                risk_factors.append(
                    f"Decreased risk due to '{f.feature_name}' "
                    f"(value: {f.feature_value}, impact: {abs(f.contribution):.3f})"
                )
            else:
                risk_factors.append(
                    f"No significant risk impact from '{f.feature_name}'"
                )

        return risk_factors

    def generate_recommendations(
        self,
        explanation: Explanation,
    ) -> list[str]:
        """Generate actionable recommendations based on the explanation.

        Args:
            explanation: The explanation to derive recommendations from.

        Returns:
            List of actionable recommendation strings.
        """
        recommendations: list[str] = []
        high_risk_features = [
            f for f in explanation.features
            if f.direction == "positive" and abs(f.contribution) > 0.1
        ]

        for feature in sorted(
            high_risk_features, key=lambda f: abs(f.contribution), reverse=True
        )[:3]:
            recommendations.append(
                f"Review and consider reducing '{feature.feature_name}' "
                f"(current value: {feature.feature_value}) to lower risk by "
                f"approximately {abs(feature.contribution):.2f} points."
            )

        if not recommendations:
            recommendations.append(
                "No high-impact risk factors detected. Continue monitoring."
            )

        return recommendations

    def cite_regulations(
        self,
        risk_factors: list[str],
    ) -> list[str]:
        """Link risk factors to relevant regulatory sources.

        Args:
            risk_factors: List of risk factor descriptions.

        Returns:
            List of regulatory citations relevant to the identified risks.
        """
        citations: list[str] = []

        keywords_to_citations = {
            "data": [
                "GDPR Article 5 - Principles relating to processing of personal data",
                "CCPA §1798.100 - Right to know what personal information is collected",
            ],
            "privacy": [
                "GDPR Article 6 - Lawfulness of processing",
                "CCPA §1798.115 - Right to delete personal information",
            ],
            "financial": [
                "SOX §302 - Corporate responsibility for financial reports",
                "Basel III - Operational risk management requirements",
            ],
            "risk": [
                "ISO 31000:2018 - Risk management guidelines",
                "COSO ERM - Enterprise risk management framework",
            ],
            "compliance": [
                "ISO 37301:2021 - Compliance management systems",
                "US Sentencing Guidelines §8B2.1 - Effective compliance program",
            ],
            "security": [
                "NIST SP 800-53 - Security and privacy controls",
                "ISO 27001:2022 - Information security management",
            ],
            "fraud": [
                "AML Directive (EU) 2018/843 - Anti-money laundering",
                "Bank Secrecy Act - Anti-fraud reporting requirements",
            ],
        }

        for factor in risk_factors:
            factor_lower = factor.lower()
            matched = False
            for keyword, refs in keywords_to_citations.items():
                if keyword in factor_lower:
                    for ref in refs:
                        if ref not in citations:
                            citations.append(ref)
                    matched = True
                    break
            if not matched and "GDPR Article 5" not in citations:
                citations.append("GDPR Article 5 - Principles relating to processing of personal data")

        return citations[:5]

    async def _generate_with_llm(
        self,
        explanation: Explanation,
        audience: str,
        detail_level: str,
    ) -> NaturalLanguageExplanation:
        """Generate explanation using an LLM provider."""
        if self._llm is None:
            raise RuntimeError("LLM provider is not configured")

        audience_prompts = {
            "technical": "You are a senior ML engineer explaining a model's decision. Use precise technical terms, feature names, and SHAP values. Be specific about numerical contributions.",  # noqa: E501
            "compliance_officer": "You are a compliance analyst explaining a model's decision for regulatory review. Focus on regulatory implications, risk factors, and compliance impact.",  # noqa: E501
            "executive": "You are a business consultant explaining an AI decision to C-suite executives. Focus on business impact, strategic implications, and actionable recommendations. Avoid technical jargon.",  # noqa: E501
            "regulator": "You are an expert witness providing formal testimony about an AI model's decision. Use precise, evidence-based language. Reference specific features and their regulatory significance.",  # noqa: E501
        }

        system_prompt = audience_prompts.get(
            audience,
            "You are an AI explainability expert providing clear explanations.",
        )

        detail_instruction = {
            "basic": "Provide a brief 2-3 sentence summary focusing only on the most important factor.",
            "detailed": "Provide a thorough explanation covering key factors, their impact, and context.",
            "comprehensive": "Provide an exhaustive analysis including all feature contributions, interactions, statistical confidence, and detailed recommendations.",  # noqa: E501
        }.get(detail_level, "Provide a detailed explanation.")

        features_text = "\n".join(
            f"- {f.feature_name} (value={f.feature_value}, "
            f"contribution={f.contribution:.4f}, direction={f.direction})"
            for f in explanation.features[:15]
        )

        messages = [
            LLMMessage(
                role="system",
                content=f"{system_prompt}\n\n{detail_instruction}",
            ),
            LLMMessage(
                role="user",
                content=(
                    f"Explain the following AI model prediction:\n"
                    f"Model: {explanation.model_name}\n"
                    f"Type: {explanation.explanation_type.value}\n"
                    f"Confidence: {explanation.confidence:.2f}\n\n"
                    f"Feature Contributions:\n{features_text}\n\n"
                    f"Provide:\n"
                    f"1. A clear explanation of the prediction\n"
                    f"2. Key factors that influenced the decision\n"
                    f"3. A risk level statement\n"
                    f"4. Recommended actions\n"
                    f"5. Relevant regulatory considerations\n"
                    f"6. Any uncertainty in the explanation"
                ),
            ),
        ]

        response = await self._llm.generate(messages, temperature=0.2)
        content = response.content if response else ""

        return NaturalLanguageExplanation(
            explanation_text=content,
            key_factors=[f.feature_name for f in explanation.features[:5]],
            risk_level_statement=self._extract_risk_statement(content),
            recommended_actions=self.generate_recommendations(explanation),
            citations=self.cite_regulations(
                [f.feature_name for f in explanation.features[:5]]
            ),
            uncertainty_statement=(
                f"Explanation confidence: {explanation.confidence:.0%}"
                if explanation.confidence < 0.9
                else None
            ),
        )

    def _generate_with_templates(
        self,
        explanation: Explanation,
        audience: str,
        detail_level: str,
    ) -> NaturalLanguageExplanation:
        """Generate explanation using templates (no LLM)."""
        key_factors = self.summarize_risk_factors(explanation.features)
        recommendations = self.generate_recommendations(explanation)
        risk_factors_for_citations = [f.feature_name for f in explanation.features[:5]]
        citations = self.cite_regulations(risk_factors_for_citations)

        explanation_text = self._build_template_text(
            explanation, audience, detail_level
        )

        risk_level = self._assess_risk_level(explanation.features)
        risk_statement = (
            f"Risk Assessment: The model indicates {risk_level} risk level "
            f"based on {len(explanation.features)} contributing factors."
        )

        uncertainty = (
            f"Explanation confidence is {explanation.confidence:.0%}. "
            f"Consider gathering additional data for higher certainty."
            if explanation.confidence < 0.9
            else None
        )

        return NaturalLanguageExplanation(
            explanation_text=explanation_text,
            key_factors=key_factors[:5],
            risk_level_statement=risk_statement,
            recommended_actions=recommendations,
            citations=citations,
            uncertainty_statement=uncertainty,
        )

    def _build_template_text(
        self,
        explanation: Explanation,
        audience: str,
        detail_level: str,
    ) -> str:
        """Build audience-appropriate explanation text from templates."""
        top_features = sorted(
            explanation.features,
            key=lambda f: abs(f.contribution),
            reverse=True,
        )[:5]

        if not top_features:
            return "No feature contributions available for this prediction."

        if audience == "executive":
            lines = ["Executive Summary"]
            lines.append(
                f"The AI model '{explanation.model_name}' assessed this case "
                f"with {explanation.confidence:.0%} confidence."
            )
            positive = [f for f in top_features if f.direction == "positive"]
            negative = [f for f in top_features if f.direction == "negative"]
            if positive:
                lines.append(
                    f"Key risk drivers: {', '.join(f.feature_name for f in positive[:3])}."
                )
            if negative:
                lines.append(
                    f"Risk mitigators: {', '.join(f.feature_name for f in negative[:3])}."
                )
            return " ".join(lines)

        if audience == "compliance_officer":
            lines = ["Compliance Explanation"]
            for f in top_features:
                impact = "increases" if f.direction == "positive" else "decreases" if f.direction == "negative" else "does not significantly affect"  # noqa: E501
                lines.append(
                    f"Feature '{f.feature_name}' (value: {f.feature_value}) "
                    f"{impact} the risk score by {abs(f.contribution):.3f}."
                )
            return "\n".join(lines)

        if audience == "regulator":
            lines = ["Formal Explanation of AI Model Decision"]
            lines.append(f"Model: {explanation.model_name}")
            lines.append(f"Explanation Type: {explanation.explanation_type.value}")
            lines.append(f"Confidence: {explanation.confidence:.0%}")
            lines.append("")
            lines.append("Contributing Factors:")
            for f in top_features:
                lines.append(
                    f"- {f.feature_name}: contribution of {f.contribution:+.4f} "
                    f"({f.direction} direction)"
                )
            if detail_level == "comprehensive":
                lines.append("")
                lines.append("This explanation is based on quantitative analysis of model behavior.")
            return "\n".join(lines)

        # technical (default)
        lines = [f"Model: {explanation.model_name}"]
        lines.append(f"Type: {explanation.explanation_type.value}")
        lines.append(f"Confidence: {explanation.confidence:.2f}")
        lines.append(f"Features analyzed: {len(explanation.features)}")
        lines.append("")
        for f in top_features:
            lines.append(
                f"  {f.feature_name}: contribution={f.contribution:+.4f}, "
                f"value={f.feature_value}, direction={f.direction}"
            )
        return "\n".join(lines)

    def _extract_risk_statement(self, text: str) -> str:
        """Extract risk level statement from LLM-generated text."""
        lines = text.lower().split("\n")
        for line in lines:
            if "risk" in line and any(
                level in line
                for level in ["critical", "high", "medium", "low", "negligible"]
            ):
                return line.strip()
        return "Risk level assessment not explicitly stated."

    def _assess_risk_level(self, features: list[FeatureContribution]) -> str:
        """Assess overall risk level from feature contributions."""
        if not features:
            return "unknown"

        total_positive = sum(
            f.contribution for f in features if f.direction == "positive"
        )
        total_negative = abs(
            sum(f.contribution for f in features if f.direction == "negative")
        )

        net_risk = total_positive - total_negative
        if net_risk > 0.5:
            return "critical" if net_risk > 1.0 else "high"
        if net_risk > 0.1:
            return "medium"
        if net_risk > -0.1:
            return "low"
        return "negligible"

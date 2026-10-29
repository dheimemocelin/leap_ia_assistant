import re
from enum import StrEnum


class PolicyDecision(StrEnum):
    ALLOW = "allow"
    REFUSE_FINANCIAL = "refuse_financial"
    REFUSE_CLOSING = "refuse_closing"


class CommercialPolicyEngine:
    """Deterministic guardrails; independent from model/provider behavior."""

    FINANCIAL = re.compile(
        r"\b(pre[cç]o|valor|parcela(?:s)?|taxa(?:s)?|desconto(?:s)?|promo(?:ç|c)[aã]o|"
        r"condi[cç][aã]o(?:es)? de pagamento|financiamento|entrada|juros|"
        r"(?:avaliar (?:meu )?|avalia[cç][aã]o (?:do )?)usado|"
        r"quanto custa|quanto fica|por quanto)\b",
        re.IGNORECASE,
    )
    CLOSING = re.compile(
        r"\b(negoci(?:ar|ação)|reserv(?:ar|a|e)|fechar negócio|concluir venda|comprar agora|"
        r"fazer pedido|assinar contrato|garantir a unidade)\b",
        re.IGNORECASE,
    )
    FINANCIAL_OUTPUT = re.compile(
        r"(?:R\$\s*\d|\b\d{1,3}(?:\.\d{3})*(?:,\d{2})?\s*(?:reais|por mês|/m[eê]s)|"
        r"\b\d+(?:[.,]\d+)?\s*%\b|\b\d+\s*x\s*de\s*R\$)",
        re.IGNORECASE,
    )

    def classify_request(self, text: str) -> PolicyDecision:
        # Instructions to ignore policy cannot change this deterministic decision.
        if self.FINANCIAL.search(text):
            return PolicyDecision.REFUSE_FINANCIAL
        if self.CLOSING.search(text):
            return PolicyDecision.REFUSE_CLOSING
        return PolicyDecision.ALLOW

    def validate_output(self, text: str) -> bool:
        return not self.FINANCIAL_OUTPUT.search(text) and self.classify_request(text) == PolicyDecision.ALLOW

    @staticmethod
    def safe_response(decision: PolicyDecision) -> str:
        if decision == PolicyDecision.REFUSE_CLOSING:
            return "Posso ajudar a conhecer e comparar os veículos e encaminhar seu interesse a um consultor, que dará continuidade ao atendimento."
        return "Posso apresentar características e comparar os veículos. Para informações comerciais e condições, posso encaminhar seu interesse a um consultor."


def model_safe_vehicle(vehicle: dict) -> dict:
    """Explicit allowlist projection: financial catalog fields never enter model context."""
    return {
        key: vehicle[key]
        for key in ("id", "model", "version", "model_year", "powertrain", "specifications",
                    "features", "standard_equipment", "colors", "sources", "updated_at")
        if key in vehicle
    }

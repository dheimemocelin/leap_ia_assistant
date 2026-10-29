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
        return (
            not self.FINANCIAL_OUTPUT.search(text)
            and self.classify_request(text) == PolicyDecision.ALLOW
        )

    @staticmethod
    def safe_response(decision: PolicyDecision) -> str:
        if decision == PolicyDecision.REFUSE_CLOSING:
            return "Posso ajudar a conhecer e comparar os veículos e encaminhar seu interesse a um consultor, que dará continuidade ao atendimento."
        return "Posso apresentar características e comparar os veículos. Para informações comerciais e condições, posso encaminhar seu interesse a um consultor."


# Explicit structural allowlist: unrecognized dictionaries/lists are never forwarded.
TECHNICAL_NUMBERS = {
    "range_km",
    "battery_kwh",
    "power_kw",
    "power_cv",
    "torque_nm",
    "trunk_liters",
    "length_mm",
    "width_mm",
    "height_mm",
}
PUBLIC_SCALARS = {"id", "model", "version", "model_year", "powertrain", "updated_at"}


def model_safe_vehicle(vehicle: dict) -> dict:
    """Copy only known technical leaves; internal objects remain untouched."""

    def project(value, allowed):
        if not isinstance(value, dict):
            return {}
        result = {}
        for key, item in value.items():
            if key not in allowed:
                continue
            if key in TECHNICAL_NUMBERS:
                if type(item) in (int, float) and item >= 0:
                    result[key] = item
            elif key == "model_year":
                if item is None or type(item) is int and 2000 <= item <= 2100:
                    result[key] = item
            elif isinstance(item, str) and CommercialPolicyEngine().validate_output(item):
                result[key] = item
        return result

    def technical(value):
        if isinstance(value, list):
            return [
                clean for item in value if isinstance(item, dict) and (clean := technical(item))
            ]
        if not isinstance(value, dict):
            return {}
        clean = project(value, TECHNICAL_NUMBERS)
        for key in ("battery", "dimensions", "motor", "motors"):
            if key in value and isinstance(value[key], (dict, list)):
                child = technical(value[key])
                if child:
                    clean[key] = child
        return clean

    result = project(vehicle, PUBLIC_SCALARS)
    result["specifications"] = technical(vehicle.get("specifications", {}))
    # Free-form features, equipment, source notes and colors are intentionally excluded
    # until they have typed, reviewed identifiers instead of arbitrary document text.
    return result

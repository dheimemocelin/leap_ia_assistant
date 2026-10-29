# Correção P0 — limite de saída e projeção de contexto

Baseline: 21fe8b7 e alterações locais preexistentes. Escopo: P0-01/P0-02 do engineering-baseline-review; P0-03 (cobertura semântica de regex) continua aberto.

Antes: `python3 -B -m pytest -q tests/unit/test_commercial_boundary.py -p no:cacheprovider` reproduziu 3 falhas: construtor e model_validate serializavam preço; specs.price, descontos em listas e texto financeiro permaneciam na projeção.

Depois: validador obrigatório no AssistantResponse aplica fallback com handoff; serializador revalida objetos construídos/copied por APIs Pydantic que pulam validação. Objetos são frozen e rejeitam campos extras. IDs de fontes aceitam apenas identificadores, não texto livre. Fábrica validated reutiliza o mesmo caminho.

CommercialOutputBoundary é registrado globalmente no FastAPI para rotas /v1/. Somente resposta JSON no schema AssistantResponse pode sair. Erros, exceções, resultados brutos de ferramenta, payload excessivo e formatos não validados recebem fallback. Streaming SSE fica bloqueado; JSON fragmentado é acumulado (máximo 64 KiB) e validado antes de enviar. Não há streaming de tokens autorizado nesta etapa. Probes /health não passam pela política comercial.

Projeção model_safe_vehicle copia somente metadados permitidos e medidas técnicas numéricas por allowlist recursiva (battery/dimensions/motor/motors). Campos desconhecidos, estruturas financeiras, textos livres de features/equipment/colors e notas/fontes não são encaminhados. Dados internos originais não são alterados. Adicionar capacidades requer expandir o schema revisado; não basta liberar texto livre. SalesTools list/details/compare já usam essa projeção.

Gates finais: 14 testes passaram (1.02s) em test_commercial_boundary, test_commercial_policy e test_health; Ruff passou nos arquivos alterados; compileall e git diff --check passaram. Testes HTTP usam FastAPI/TestClient e cobrem caminho normal, dados financeiros, resultado de ferramenta, erro 400, exceção 500 e SSE. Sem chamadas externas ou inferência. Suíte de mídia não alterada/não incluída nestes gates; quatro falhas preexistentes da auditoria não foram corrigidas.

Limites: respostas livres continuam sujeitas à cobertura lexical do CommercialPolicyEngine; paráfrases financeiras, pagamentos e fechamento não cobertos pelo motor seguem risco residual P0-03. Identificadores não comprovam existência/validade de fonte; medidas não comprovam verdade documental. Não há integração LLM/WhatsApp ou avaliação adversarial de modelo. Todas as futuras rotas de atendimento devem permanecer sob /v1/ e usar o envelope validado; formatos adicionais precisam de contrato explícito. Não declarar segurança comercial global aprovada por estes testes.

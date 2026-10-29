# Agente local de pré-vendas — primeira integração

Implementação: porta LLMAdapter independente de fornecedor; adapter Ollama HTTP opt-in (endpoint /api/chat, tools, stream=false). Sem modelo/servidor configurado, provider disabled falha fechado e oferece consultor. Não houve inferência real nesta entrega. O modelo escolhido pelo operador precisa suportar tool calling; nenhum modelo é baixado ou selecionado automaticamente.

Grafo LangGraph compilado: guard → select → tools → compose → output, com ramificações para esclarecer, abster ou handoff. Solicitações financeiras/negociação/reserva são interrompidas antes do modelo. Modelo+motorização claros seguem rota determinística; seleção indefinida pode usar uma chamada de planejamento com uma única ferramenta validada. Até duas chamadas por turno (uma em consultas identificadas), timeout configurável, sem retry automático, contexto até 16 mil caracteres e geração limitada a 300 tokens no adapter. Uso input/output é coletado quando informado e registrado sem texto/identificador do cliente nos logs.

Allowlist: list_vehicles (máximo seis resumos de identidade), get_vehicle_details (projeção técnica existente), search_vehicle_media (biblioteca determinística, máximo três mídias aprovadas). Ferramentas de CRM, compra, oferta ou negociação não são registradas nem despacháveis. Resultados de mídia enviados ao modelo contêm apenas id/categoria; nenhum arquivo, caminho, storage URI ou base64 é serializado. Manuais/PDF não são consultados.

Resposta: AssistantResponse com text, confidence, source_ids, media_ids e handoff_required. Fontes são IDs gerados pelo servidor a partir da URL e data da fonte do veículo consultado; não são IDs inventados pelo LLM. Media IDs vêm apenas dos resultados aprovados da ferramenta no turno. O texto passa pela validação obrigatória e serialização do CommercialPolicyEngine e pela barreira HTTP. A extensão media_ids mantém a validação sintática e é zerada em fallback financeiro. Respostas brutas de ferramenta não atravessam a barreira.

Memória local em processo, por (hash do token de sessão, conversation_id), com lock por conversa; últimos dois pares de mensagens truncados, modelo/motorização/intenção de foto e uso do último turno. Limite 128 sessões; reiniciar perde memória. Sem persistência Postgres/Redis e sem expiração/exclusão administrativa nesta etapa; não usar dados pessoais reais no piloto local.

## Execução local

Instalar dependências do pyproject e iniciar FastAPI conforme README. Configurar APP_API_KEY com segredo local, LLM_PROVIDER=ollama, LLM_MODEL com modelo local já disponível, LLM_BASE_URL (padrão http://127.0.0.1:11434), LLM_TIMEOUT_SECONDS (padrão 15). O destino é configuração exclusiva do operador, nunca argumento do cliente ou modelo. httpx é dependência de runtime; testes usam transporte simulado sem rede.

POST /v1/conversations/{conversation_id}/messages com JSON {"text":"Quero fotos do B10 BEV"}, Authorization: Bearer <APP_API_KEY> e X-Session-Token secreto aleatório com 32 a 200 caracteres. Reutilizar ID e token preserva contexto; outro token isola o mesmo ID. O backend do cliente deve guardar a chave de API, não embuti-la num widget público. Não há gestão de identidade multiusuário/SSO; token de sessão funciona como capacidade local e deve permanecer secreto.

O catálogo real permanece pending_review: suas consultas retornam falta de material aprovado/handoff, não fotos reais. Aprovação exige processo editorial externo a esta integração.

## Evidências e limites

Testes com LLM fake e httpx.MockTransport: fotos B10 BEV/REEV/C10 BEV, características, ambiguidade e continuidade, preços/negociação/reserva, fontes/mídias, isolamento de conversa e token, ferramentas proibidas, limite de chamadas, timeout, falha de ferramenta, fallback de texto financeiro do modelo, API/autorização e bloqueio de catálogo real pendente. Nenhum serviço LLM, WhatsApp ou Syonet foi chamado.

Cobertura determinística não comprova grounding semântico ou robustez completa contra prompt injection. O motor lexical mantém limitações P0-03 da auditoria; não há verificação automática de toda alegação livre nem avaliação humana de modelo real. Mídia é somente referência, não entrega. Persistência, gestão de usuários, lifecycle de sessões, entrega de arquivos e validação de modelos reais ficam para etapas posteriores. O readiness Postgres/Redis preexistente não foi corrigido neste escopo. LangGraph emite aviso de depreciação transitiva de JsonPlusSerializer; não há checkpoint desserializado nem alteração de versão nesta entrega.

Referências usadas para compatibilidade: https://docs.ollama.com/api/chat e https://docs.langchain.com/oss/python/langgraph/graph-api .

Gates finais desta execução: `ruff check app tests --no-cache` passou; `python3 -B -m pytest -q -p no:cacheprovider` → 66 passed (1.87s), com um aviso transitivo de depreciação LangGraph; `python3 -m compileall -q app tests` e `git diff --check` passaram. Toda inferência dos testes foi simulada. Não há evidência de desempenho/latência/grounding de modelo real.

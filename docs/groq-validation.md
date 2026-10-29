# Validação Groq — 2026-10-29

Baseline 95d0b29. Resultado: **PARCIAL** para validação global; transporte real Groq, integração ao grafo/barreira HTTP e gates automatizados passaram. Tool calling real e grounding factual de catálogo real não foram exercitados.

## Configuração e implementação

Não existia adapter Groq. Adicionado GroqAdapter ao contrato LLMAdapter existente, selecionado por build_agent quando LLM_PROVIDER=groq; nenhum segundo grafo foi criado. Usa httpx já instalado, endpoint fixo HTTPS https://api.groq.com/openai/v1/chat/completions, timeout configurável, sem retries automáticos e sem redirecionamentos. Parsing de tool_calls.function.arguments JSON, saída normalizada ModelReply e tokens usage.prompt_tokens/completion_tokens. Métricas recentes limitadas a 32 chamadas, sem prompts, respostas ou credenciais. Erros HTTP/conexão/timeout/payload inválido são sanitizados.

Settings carrega GROQ_API_KEY em SecretStr excluído do repr. Confirmado LLM_PROVIDER=groq e chave presente, nunca registrada. O valor inicial de LLM_MODEL não correspondia a modelo disponível; consulta GET /models retornou 200 e confirmou openai/gpt-oss-20b disponível. O usuário autorizou explicitamente esse modelo; somente LLM_MODEL foi corrigido no .env ignorado pelo Git. Nenhuma chave foi alterada ou commitada.

## Testes automatizados

74 testes passaram (1.73s), incluindo suites preexistentes de histórico/isolation, orçamento de chamadas e política. Novos testes: protocolo Groq de tool calling, parsing estruturado/tokens, erros 401/429/500 sem retry nem conteúdo sensível, JSON de ferramenta inválido, timeout sanitizado, segredo mascarado, Groq simulado no mesmo grafo (duas chamadas, resultado financeiro convertido em fallback) e erro do provedor convertido em handoff. httpx.MockTransport em todos os testes Groq: nenhum teste automatizado usa rede ou API paga.

Ruff, compilação Python e git diff --check passaram. Aviso transitivo de depreciação LangGraph já existente permanece; nenhuma mudança de grafo ou CommercialPolicyEngine.

## Três interações reais controladas

Somente após confirmação da chave/modelo. POSTs pela aplicação em TestClient (FastAPI e barreira HTTP reais), com Groq real, sem cliente externo. Catálogo sintético criado em diretório temporário e aprovado apenas como fixture em memória. Nenhuma aprovação ou modificação do catálogo real; build_agent também confirmado com GroqAdapter e 12 mídias reais ainda pending_review. Imagens sintéticas não foram enviadas ao modelo; somente IDs/categoria e evidência técnica da fixture. Não houve chamadas adicionais de inferência além das duas abaixo.

1. Fotos B10 REEV: HTTP 200; search_vehicle_media retornou b10-reev-front e uma fonte sintética. Uma chamada real Groq; modelo efetivo openai/gpt-oss-20b; 231 tokens de entrada, 249 de saída; latência da interação 1059.94 ms (provedor 1031.32 ms). Política de saída passou, handoff false.
2. Características C10 BEV: HTTP 200; get_vehicle_details retornou identidade/especificações da fixture e uma fonte sintética. Uma chamada real; modelo efetivo openai/gpt-oss-20b; 269 tokens de entrada, 171 de saída; latência da interação 605.58 ms (provedor 592.83 ms). Política de saída passou, handoff false. A fixture não contém ficha técnica real, portanto o resultado não comprova correção factual do veículo.
3. Preço/negociação: HTTP 200; bloqueado no guard antes de ferramenta/provedor; zero chamadas/tokens de provedor; latência 5.99 ms; handoff true, sem fontes/mídias.

Total: 3 interações, 2 chamadas reais de inferência, 500 tokens de entrada e 420 de saída. Ambas chamadas HTTP Groq retornaram 200. A consulta GET /models foi preflight, não inferência. Sem falhas do provedor no teste real; falhas e timeouts exercitados somente por simulação.

## Limites e rastreabilidade

Caminhos determinísticos selecionaram ferramentas antes do LLM: as chamadas reais foram de composição, com zero tool_calls devolvidas pelo provedor. Protocolo de tool calling foi testado por simulação, não inferência real. Não aumentar a cota de interações para esse teste sem nova autorização.

O rótulo confidence=grounded significa associação às fontes da ferramenta, não avaliação semântica independente de todas as frases. Limitações lexicais P0-03 do motor, riscos de alucinação e falta de avaliação factual humana permanecem. As fontes são sintéticas e não são documentação técnica real. Dados reais pendentes continuam bloqueando o atendimento. Não houve Syonet, Evolution API, mensagens a clientes, merge, push ou deploy.

Evidência sanitizada versionada: groq-validation-evidence.json. Saídas completas do provedor não foram armazenadas; hashes do texto final permitem identificar as respostas sem registrá-las. Métricas são observações pontuais, não benchmark.

Referências primárias consultadas: https://console.groq.com/docs/tool-use/overview e https://console.groq.com/docs/openai .

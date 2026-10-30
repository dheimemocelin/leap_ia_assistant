# SDR comercial v2 — evidências e revisão

Baseline: `8b833c2`. Data: 2026-10-30. Branch: `fix/sdr-context-continuity`.

## Mudança de comportamento

O diagnóstico foi registrado em [sdr-v2-diagnosis.md](sdr-v2-diagnosis.md) antes da ampliação v2. A correção local já iniciada para o print foi preservada. A causa foi reproduzida com teste inicialmente falhando, não inferida apenas pela imagem.

A Lia permanece no mesmo LangGraph/Groq. A decisão comercial reutiliza o perfil e as transições existentes: WELCOME, DISCOVER, SHOWCASE, EDUCATE, ENGAGE, QUALIFY, HANDOFF e RESPECT_DECLINE. A política de contexto escolhe exploração/esclarecimento; seleção canônica direciona apresentação/educação; sinais espontâneos qualificam. Identidade é apresentada uma vez, independentemente da ação relevante. As ações não exigem passagem por etapas anteriores.

**Regra final do usuário: handoff somente quando o cliente pedir explicitamente atendimento humano.** Visita, compra, preço, falha de ferramenta e ausência de fato técnico não disparam oferta, coleta de contato ou `handoff_required`. O pedido explícito exige consentimento antes da coleta/preparação. Uma pergunta de outro assunto pausa coleta pendente, impedindo que um “sim” posterior autorize uma pergunta antiga. Recusa é respeitada; um pedido posterior explícito pode reabrir o assunto.

A frase de confirmação por consultor citada no print foi retirada dos caminhos normais e de erro do agente. Não se alteraram CommercialPolicyEngine, AssistantResponse, barreira HTTP, autenticação ou isolamento. O limite de saída do agente também neutraliza sugestões de encaminhamento vindas do modelo sem solicitação; ao substituir texto, não conserva fontes que deixaram de ser usadas. A barreira comercial independente continua validando a resposta resultante.

Viagem no singular, prioridade de economia, distância de viagem e acesso à recarga agora entram na memória existente. Economia é uma necessidade declarada, nunca uma promessa do veículo. A resposta curta de distância pode levar ao contexto de recarga; “em casa” é reconhecido sem nova busca técnica nem pergunta repetida. Nenhum benefício, rentabilidade ou categoria de aplicativo é inferido.

Fotos aprovadas permanecem proativas e isoladas por veículo/motorização. A apresentação objetiva não termina obrigatoriamente com pergunta. Consultas gerais excluem fotos já apresentadas. Pedidos explícitos de ângulo mantêm a possibilidade de rever uma imagem.

A composição consultiva continua limitada a formulações autorizadas escolhidas pelo modelo. Fatos técnicos só usam IDs/afirmações revisados. A listagem de identidades aprovadas passou a ser renderizada deterministicamente, sem segunda chamada de geração livre. Isso limita improvisação, mas não equivale a compreensão semântica irrestrita ou fluência comprovada.

## Transcrições para revisão

- Print: [antes](evaluations/screenshot-before.json), [depois](evaluations/screenshot-after.json).
- Jornada SDR completa: [antes](evaluations/sdr-v2-before.json), [depois](evaluations/sdr-v2-after.json).

O nome da conversa do print foi substituído por **Pessoa Sintetica**. Telefones de teste são sintéticos. Os arquivos são execuções reais do software local com **LLM simulado**, não conversas de clientes nem inferências pagas.

As execuções “antes” carregaram `app` e `data` de um `git archive 8b833c2` em diretório temporário isolado, usando o mesmo harness de avaliação e os arquivos de mídia existentes em leitura. O diretório foi removido automaticamente; o workspace e imagens não foram restaurados/sobrescritos. O rótulo `implementation` distingue baseline de working-tree. Os arquivos antigos `sdr-before/after.json` permanecem como histórico da etapa anterior.

Na reprodução do print, a fala de viagem/economia passa a reconhecer os trajetos e perguntar sua distância. Depois da distância, a conversa explora possibilidade de recarga. Não aparece indicação de consultor e não é prometida economia.

Na jornada completa, nome e escolha B10/BEV levam à apresentação visual; Uber gera descoberta profissional; família e primeira experiência elétrica preservam continuidade; preço é bloqueado sem handoff; visita é registrada sem solicitar dados; recusa é respeitada; troca para C10 atualiza fotos e autonomia fundamentada. Somente “Quero falar com um consultor”, seguido de autorização, permite preparar resumo privado, nunca enviado.

## Avaliação além de snapshots

Os testes verificam estado, decisão, transições de consentimento, identidade canônica, fontes, ausência de repetição de mídia, ausência de informações financeiras e contagem de perguntas. O teste completo observa as oito ações, nenhuma oferta humana antes de pedido explícito e resumo `prepared_not_sent` somente depois da autorização. Testes de falha do provedor, ferramenta proibida, fontes revogadas, fatos inventados e isolamento permanecem ativos.

As expectativas antigas de handoff em falhas/abstenção foram atualizadas para a nova regra expressa pelo usuário; os testes continuam exigindo bloqueio de informações proibidas e ausência de vazamentos. A redução de chamadas na listagem foi verificada com transporte Groq simulado, preservando os testes de adapter e limite de ferramentas. Não se alteraram testes da política comercial ou da barreira HTTP para relaxar proteções.

Inspeção qualitativa: melhor reconhecimento e continuidade nas jornadas cobertas; perguntas mais ligadas à rotina; apresentação visual objetiva; encaminhamento sob controle do cliente. Encantamento, naturalidade ampla e potencial de conversão ainda precisam de revisão humana independente. Não há pontuação subjetiva apresentada como medição objetiva.

## Gates executados

```bash
python3 -B -m pytest -q -p no:cacheprovider --tb=short
ruff check app tests scripts/evaluate_conversation.py --no-cache
python3 -m compileall -q app tests scripts/evaluate_conversation.py
git diff --check
PYTHONPATH=. python3 -B scripts/evaluate_conversation.py --scenario screenshot --output docs/evaluations/screenshot-after.json
PYTHONPATH=. python3 -B scripts/evaluate_conversation.py --scenario sdr-v2 --output docs/evaluations/sdr-v2-after.json
```

**145 testes passaram.** Ruff, compilação e diff check aprovados. Um aviso upstream LangChainPendingDeprecationWarning permanece. As avaliações não consumiram Groq real; os contadores de tokens do simulador não são custos observáveis de produção.

## Limites e estado operacional

Reconhecimento ainda lexical, formulações limitadas e catálogo técnico incompleto. Variações linguísticas, negações complexas e novos retornos curtos precisam ampliar a avaliação. Memória continua local ao processo, sem nova persistência. Testes determinísticos não aprovam segurança adversarial ampla ou prontidão de produção.

Não houve alteração de aprovação ou publicação de imagens, integração externa, merge, push, deploy ou reinício do backend. Para testar a nova versão no navegador será necessário reiniciar o processo de teste, conforme autorização operacional.

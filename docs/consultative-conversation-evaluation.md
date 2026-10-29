# Experiência consultiva — avaliação local

Data: 2026-10-29. Base: `5cac503`. Skills utilizadas: Engineering OS (roteamento), ai-engineering, software-engineering, fde-delivery e git-quality.

## Implementação

O mesmo StateGraph passa por `consult → guard → select → tools → compose → output`. O novo módulo `app/agent/consultative.py` mantém qualificação determinística; Groq, ferramentas autorizadas, CommercialPolicyEngine e barreira HTTP permanecem existentes. Não existe segundo agente, integração CRM ou ação externa nova.

O estado por `(owner, conversation_id)` registra seleção canônica, uso, prioridades, objeções, conhecimento da marca, interesse em visita/compra, prazo espontâneo, próxima ação, perguntas já feitas, fatos e imagens apresentados. Classificação interna frio/morno/quente acompanha razões observáveis; visita ou intenção explícita de compra indicam quente. Não se apresenta pontuação ao cliente.

A seleção inequívoca inicia apresentação visual com até três imagens aprovadas e fatos revisados disponíveis. Consultas técnicas explícitas continuam no fluxo de grounding. As buscas gerais seguintes excluem imagens já mostradas; pedidos explícitos de ângulo podem revisitar imagens. Trocas de veículo invalidam consentimento e contato anteriores, conservando prioridades de uso. Uma única variante canônica aprovada permite resolver C10 sem sugerir uma versão inexistente no catálogo carregado; isso não afirma estoque ou disponibilidade.

Consentimento é explícito e ligado à seleção atual. Nome e telefone são solicitados separadamente após autorização. O resumo fica privado, com status `prepared_not_sent`; nenhuma ferramenta de envio é habilitada. Recusa remove contato e resumo, e impede novas solicitações de contato até iniciativa explícita do cliente. Dados coletados e contatos espontâneos são omitidos do histórico enviado ao modelo. Não há novos logs de conteúdo ou credenciais.

## Evidências reproduzíveis

As transcrições completas estão em `evaluations/consultative-before.json` e `evaluations/consultative-after.json`. São conversas **sintéticas**, executadas no código real com adapter simulado: não são avaliações da Groq em produção nem depoimentos de clientes. A primeira foi gravada antes de alterar o serviço. As duas usam o mesmo roteiro e catálogo interno revisado. As fotos desse catálogo de teste já tinham autorização registrada; o catálogo original e seus estados pendentes não foram modificados.

Exemplos do resultado atual:

- “Tenho interesse no B10” esclarece BEV/REEV, sem mostrar fotos de motorizações misturadas.
- “BEV” apresenta imagens aprovadas e fatos revisados; antes, a resposta pedia autorização adicional para mostrar fotos.
- “Uso mais na cidade” registra uso urbano; “Tenho dois filhos e preciso de espaço” conecta a prioridade ao fato revisado sobre porta-malas, sem prometer adequação à família.
- Receio de carro elétrico gera esclarecimento sobre recarga/autonomia, sem tranquilização técnica inventada.
- Interesse em visita solicita consentimento. Recusa é respeitada inclusive na pergunta posterior sobre preço, sem revelar valores.
- Troca para C10 atualiza seleção e imagens; a prioridade de uso permanece.

A naturalidade foi inspecionada manualmente nas transcrições: respostas reconhecem contexto e variam por intenção. Isso não substitui avaliação humana independente. Testes verificam limites observáveis: isolamento, uma pergunta no roteiro, ausência de repetição automática de imagens, fontes revisadas, abstenção, memória, consentimento e privacidade.

Comandos executados:

```bash
PYTHONPATH=. python3 -B scripts/evaluate_conversation.py --output docs/evaluations/consultative-after.json
python3 -B -m pytest -q -p no:cacheprovider --tb=short
ruff check app tests scripts/evaluate_conversation.py --no-cache
python3 -m compileall -q app tests scripts/evaluate_conversation.py
git diff --check
```

Resultado: 122 testes passaram; Ruff, compilação e diff check passaram. Um aviso upstream `LangChainPendingDeprecationWarning` permanece. A suíte inclui importador/mídia, grounding, proteção comercial, isolamento HTTP e chat web, além das jornadas novas. Nenhuma API paga foi chamada. Contadores de tokens do adapter simulado não representam consumo real; custo e latência Groq não foram medidos.

## Limitações e próximos passos

- A memória continua local ao processo, limitada a 128 sessões, sem persistência ou expiração temporal nova. Contatos privados vivem nessa memória até revogação, exclusão da sessão ou reinício; retenção durável e LGPD operacional precisam de desenho antes de produção.
- Reconhecimento determinístico cobre expressões testadas, não toda linguagem natural, negações compostas ou todas as objeções. Novas paráfrases precisam de avaliação e expansão controlada.
- Fatos aprovados disponíveis são poucos. Sem evidência, o agente se abstém; não inventa benefícios de conforto, segurança, recarga ou adequação urbana.
- O roteiro é evidência determinística, sem avaliação independente, adversarial ampla ou piloto com clientes. Encantamento/conversão não estão comprovados por esses testes.
- O resumo ainda não tem consumidor externo. Não houve envio ao Syonet/WhatsApp, deploy, reinício do servidor ou ativação automática no chat já aberto.

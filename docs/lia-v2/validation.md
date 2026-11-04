# Lia V2 — evidências de validação

## Reprodução e correção

Antes da implementação, `python3 -m pytest tests/unit/test_lia_v2.py -q` executou quatro testes e os quatro falharam: reenvio, encerramento/retorno com nome, pausa e retomada com veículo. O [diagnóstico](diagnosis.md) registra causas e funções relacionadas.

Após implementação, os **44 casos V2** passaram. Cobrem conversas completas, sessões no mesmo dia/dia seguinte/período prolongado com relógio controlado, reinício, nome atualizado/desconhecido, expiração da retenção, exclusão, migração legada idempotente, isolamento por identidade, agradecimento com continuidade, interesse em visita, recusa, autorização em duas etapas, dados mínimos, mídia, falhas de envio, recibos, timeout e submissões concorrentes, idempotência e webhook duplicado.

Pedido “me fala daquele carro” usa a seleção persistida e a recuperação factual existente; “onde paramos” e “quero continuar” usam a memória, sem inventar fatos. A melhoria desse caminho foi seguida novamente pelos 43 casos V2 existentes naquele momento; o caso adicional de oportunidade autorizada sem veículo identificado foi coberto pela rodada completa final.

## Gates executados

| Comando | Resultado observado |
| --- | --- |
| `python3 -m pytest tests/unit/test_lia_v2.py -q` — reprodução inicial | 4 falhas, antes da correção. |
| `python3 -m pytest tests/unit/test_lia_v2.py tests/unit/test_sales_delivery.py tests/unit/test_evolution.py tests/unit/test_pilot_persistence.py -q` — primeira rodada focada | 53 passaram, quando os testes V2 ainda eram quatro. |
| `python3 -m pytest -q` — primeira rodada completa | 530 passaram, 5 ignorados, 1 falhou por ausência de `pymupdf`, dependência opcional do módulo Knowledge. |
| `PYTHONPATH=/home/ubuntu/.t3/projects/leap-ia-assistant/.local/knowledge-deps python3 -m pytest -q --tb=short` — rodada completa com dependências já existentes | **545 passaram**. Nenhum pacote foi instalado; dependências opcionais já existentes foram disponibilizadas somente ao processo de teste. |
| `python3 -m pytest tests/unit/test_lia_v2.py -q --tb=short` — após último ajuste de retomada | **43 passaram**. |
| `python3 -m ruff check app tests scripts` | Aprovado. |
| `python3 -m compileall -q app tests scripts` | Aprovado. |
| `git diff --check` | Aprovado. |
| `python3 -m scripts.evaluate_lia_v2` | 7 cenários × antes/depois: **14 conversas**, 78 turnos sintéticos. Zero chamadas pagas. |

A rodada completa final executou o código final e todos os 44 casos V2. O único aviso restante é `LangChainPendingDeprecationWarning`, upstream, sem alteração nesta entrega.

## Qualidade e segurança: alcance da evidência

- As [conversas comparativas](conversations.md) e o [JSON](transcripts.json) contêm resultados do grafo executado, fontes, mídias, origem de composição, fallbacks e estados; não são snapshots escritos como se fossem execuções.
- Cobertura determinística: memória, transições, consentimento, falha/recibo de entrega, bloqueios comerciais, controle de ferramentas e deduplicação.
- Entrega a consultor: **somente adapter sintético nos testes**; local real só prepara/enfileira. Nenhuma prova de integração externa ou recebimento por vendedor real.
- Aprovação e arquivo de imagens são verificados pelo fluxo existente; testes não alteram aprovação persistida das fotos reais. Proposta de mídia não equivale a entrega confirmada.
- `CommercialPolicyEngine`, barreira HTTP e biblioteca de mídia não foram modificados.
- Não houve avaliação de naturalidade com modelo real, revisão humana independente, teste de longa duração ou avaliação adversarial semântica completa. Métricas de redação/fallback não comprovam eficácia comercial.
- Não houve migração do banco de produção, alteração de `.env` do piloto, reinício, envio real, inferência paga, merge ou push.

## Limitações operacionais

O banco e as sessões continuam no modelo de piloto de um processo; não se adicionou persistência distribuída. A detecção de despedidas cobre expressões testadas e usa controles determinísticos para não transformar a vontade do cliente em ações do modelo; paráfrases e ambiguidades ainda precisam de avaliação.

A confirmação depende de um recibo confiável do adapter e da operação do canal futuro. Após claim/crash ou timeout, não há retry cego; a fila precisa de revisão. Exclusão/revogação local não remove cópias já recebidas por terceiros nem backups históricos. Não há interface administrativa ou callback externo de confirmação nesta etapa.

**Situação:** funcionalidade implementada e validada localmente para revisão; ativação no piloto e integração externa não executadas. O serviço continua no commit `8416720`, branch `deploy/lia-typing-8416720`, ativo.

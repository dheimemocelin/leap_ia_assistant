# Reação social não é consulta técnica

Data: 2026-10-30. Baseline: `e9b8c87`. Branch: `fix/sdr-context-continuity`. Skills: ai-engineering, software-engineering e git-quality, conforme Engineering OS existente.

## Diagnóstico reproduzido

No fluxo real, `consult()` só interrompia o roteamento para mudanças de perfil/consentimento ou necessidades reconhecidas. “Que legal” não alterava esses campos. `select()` reaproveitava B10/BEV e escolhia `get_vehicle_details` por padrão. `tools()` consultava o catálogo, mas a GroundingPolicy não encontrava fatos pertinentes à reação. `compose()` retornava a frase fixa “Ainda não tenho esse detalhe técnico confirmado…”. **A frase vinha de template Python, não da Groq.**

Com nome sintético fornecido antes das fotos, os sete casos sociais inicialmente falharam no teste de ausência de ferramenta técnica: Que legal, Gostei, Muito bonito, Interessante, Não gostei, Tenho dúvidas e Quero saber mais. Com pergunta de nome pendente, outro erro podia mascarar a falha: uma reação curta era aceita como nome. Ambos foram corrigidos. A variação “Uso para trabalhar” revelou também falta de reconhecimento do verbo trabalhar, corrigida no mesmo limite de intenção.

## Correção no grafo existente

`app/agent/social.py` distingue reações positivas/negativas, dúvida inespecífica e interesse em continuar. O reconhecimento é de mensagem completa: misturas como “Gostei, qual a autonomia?” permanecem no caminho técnico; perguntas financeiras e pedidos explícitos de atendimento humano preservam seus caminhos originais.

`consult()` usa esse ato conversacional antes de `select()`. Reações não acionam ferramentas de catálogo, não repetem mídia e não entram no fallback de especificação ausente. Reações positivas, objeções e interesse são registrados nos sinais existentes. O modelo recebe contexto compacto de modelo/motorização, uso, necessidades, perguntas feitas e fatos revisados já apresentados. Não recebe nome, telefone, arquivos, base64 ou catálogo inteiro.

O LLM escreve um reconhecimento **em texto**, não escolhe uma frase por índice. Uma pergunta é opcional e separada por chave semântica; perguntas repetidas ou de uso já conhecido são suprimidas. Perguntas anteriores relevantes permanecem disponíveis para respostas curtas, inclusive quilometragem após uma reação intermediária.

A saída social tem schema próprio, tamanho limitado e validação independente: vocabulário social permitido, política comercial, quantidade de perguntas, correspondência do veículo e separação de afirmações técnicas. O modelo pode compor frases diferentes; não pode introduzir números, atributos técnicos, promessas, encaminhamentos ou outro veículo nessa superfície. Fatos e especificações continuam no GroundingPolicy existente. Há fallback social somente para erro, timeout ou saída inválida, sem ausência artificial de evidência técnica e sem pergunta obrigatória.

CommercialPolicyEngine, barreira HTTP e regras de consentimento não foram alterados. O reconhecimento de reação apenas impede armazená-la como nome, inclusive durante coleta autorizada. Pedido explícito de humano e autorização continuam necessários para preparar contato. Não há novo agente, grafo, integração ou dependência.

## Transcrições reais locais com modelo simulado

- [Antes](evaluations/social-before.json): código `app/data` do commit baseline carregado de arquivo Git em diretório temporário, sem modificar o workspace.
- [Depois](evaluations/social-after.json): implementação corrigida.

Ambas usam o mesmo roteiro, ferramentas locais e modelo simulado. O primeiro nome é sintético. A avaliação registra nomes das ferramentas efetivamente executadas, respostas, consumo reportado pelo simulador e estado.

Trecho da execução corrigida:

> Cliente: Que legal
>
> Lia: O visual do B10 BEV chamou sua atenção. Como você pretende usar o carro no dia a dia?

Esse reconhecimento foi produzido pelo adapter simulado e aceito pelo compositor. O turno não executou `get_vehicle_details` nem retornou fotos/fontes. Reações seguintes não repetem a mesma pergunta. Outros testes aceitam diferentes textos compostos pelo modelo, inclusive respostas sem pergunta; não dependem apenas desse snapshot.

## Gates e cobertura

```bash
python3 -B -m pytest -q -p no:cacheprovider --tb=short
ruff check app tests scripts/evaluate_conversation.py --no-cache
python3 -m compileall -q app tests scripts/evaluate_conversation.py
git diff --check
PYTHONPATH=. python3 -B scripts/evaluate_conversation.py --scenario social --output docs/evaluations/social-after.json
```

**167 testes passaram.** Ruff, compilação e diff check passaram. Mantém-se um aviso upstream LangChainPendingDeprecationWarning.

Cobertura nova: nove falas solicitadas, nome não confundido com reação, variação do texto efetivamente escrito pelo modelo, pergunta opcional, não repetição, contexto e fatos previamente apresentados, sigilo do nome, veículo incorreto, resposta financeira, atributo inventado, promessa para aplicativos, encaminhamento não solicitado, timeout, pergunta técnica misturada à reação e continuidade de distância/coleta após uma reação. Demais regressões de catálogo, mídia, autorização, grounding e política permanecem executadas.

## Limitações e estado operacional

Sem inferência Groq real e sem consumo pago. O vocabulário social é conservador: pode rejeitar formulações legítimas; nesses casos usa fallback. Reconhecimento lexical não cobre todas as paráfrases, emojis ou mensagens mistas. Não se afirma qualidade humana, segurança adversarial ampla ou fluência universal com base nesses testes. Um piloto real precisa de autorização e limite de chamadas.

Sem push, deploy ou reinício do backend nesta execução. A versão do chat em execução precisa ser reiniciada para carregar este código.

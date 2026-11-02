# Conhecimento oficial e linguagem para o comprador

## Diagnóstico

As capturas do piloto demonstraram quatro problemas distintos: cobertura técnica insuficiente; pergunta de autonomia em estrada sem termo `autonomia` não recuperada; mensagens sobre revisão/aprovação expostas ao cliente; e referências como `a primeira opção` sem IDs ordenados no estado. A questão não era apenas o modelo ou o prompt.

O trabalho mantém o único SalesAgent/LangGraph, Groq, ferramentas e banco. Não altera CommercialPolicyEngine, autenticação, mídias, consentimento, Docker ou envio externo.

## Fontes e revisão

Foram consultadas diretamente em HTTPS as páginas brasileiras oficiais:
- https://www.leapmotor.com.br/b10.html
- https://www.leapmotor.com.br/c10.html
- https://www.leapmotor.com.br/sobre-a-leapmotor.html

A extração real encontrou 26 registros técnicos do B10 e 29 do C10. O novo extrator lê os componentes HTML/JSON usados pelo site e grava candidatos locais como `pending_review`, sem promover conteúdo para o runtime. URL, data e SHA-256 são registrados. Financeiro, botões comerciais e seção de garantia/serviços não são usados nesta carga. Comando repetível:

```bash
python3 -m scripts.extract_official_catalog --output .local/knowledge-candidates
```

O catálogo interno de validação recebeu revisão de fonte explicitamente registrada como `internal-source-verification (Codex)`: não é aprovação humana, jurídica ou da fabricante. São 21 fatos numéricos e 21 afirmações técnicas curtas, além de uma apresentação institucional e definições acessíveis. Não houve aprovação automática das fotografias ou do catálogo original. A seleção curada não é uma cópia integral dos documentos.

Cobertura: B10 BEV, B10 REEV e C10 BEV; autonomia qualificada, bateria quando publicada, recarga AC/DC com janelas percentuais, potência/torque quando não conflitantes, dimensões, porta-malas, conectividade, teto e airbags. Não se transferem equipamentos exclusivos entre motorizações.

Para o B10 elétrico, o site informa 288 km no Inmetro. Isso não é transformado em medição específica de rodovia. Para o ultra-híbrido, 68 km somente elétricos (PBEV/Inmetro) e até 900 km combinados (WLTP) são tratados separadamente. Não se comparam ciclos como se fossem equivalentes nem se calcula autonomia rodoviária por extrapolação.

Potência e torque do C10 encontrados em páginas oficiais divergentes foram excluídos da expansão. Não se importaram preços, ofertas, promessas de estoque, benefícios comerciais, garantia sem ano-modelo ou aceitação em aplicativos.

## Recuperação e composição

`ReviewedTextFact` amplia GroundingPolicy com afirmações revisadas e vinculadas a veículo, fonte, seção e digest. Campos de revisão/evidência bruta não são serializados para o modelo. O runtime revalida aprovação, veículo e fonte; rejeita valores numéricos ausentes da evidência e associações incompatíveis. A seleção determinística fica limitada a cinco fatos pertinentes por consulta. Não há embeddings, catálogo completo, PDF ou imagens no contexto do LLM.

Uma falha limitada de formulação pode retornar somente os fatos ainda verificados, descartando texto, perguntas e IDs do modelo. Tentativas de falsificar IDs ou adicionar campos não autorizados continuam rejeitadas. A validação de prosa permanece heurística e não constitui prova geral de entailment; dados locais revisados continuam sendo uma fronteira de confiança.

## Experiência sem jargão interno

Listas e legendas apresentam `B10 elétrico`, `B10 ultra-híbrido` e `C10 elétrico`. IDs e motorizações canônicos permanecem internos. Explicações explícitas de siglas usam definições institucionais revisadas, sem selecionar automaticamente um carro.

`offered_vehicle_ids` preserva a ordem efetivamente apresentada, por conversa, e permite `primeira/segunda/terceira opção`. IDs são novamente conferidos e mídias mantêm aprovação e isolamento. Não se adivinha uma opção sem oferta ou fora da lista. Uma compatibilidade pontual reconhece apenas o template exato dos antigos menus enviados pelo servidor, nunca texto de usuário. Uma mudança explícita de modelo invalida o menu antigo.

Falas como `base aprovada`, `resumo institucional revisado` e contexto técnico preservado não são explicações ao comprador. Os detalhes ficam na telemetria; o cliente recebe uma apresentação ou limitação compreensível. Não se adicionou uma allowlist geral de palavras sociais.

## Troca e visita

A orientação operacional fornecida pelo responsável do piloto é incentivar a visita para avaliação presencial do carro atual. Não se informa nem aceita valor de troca, não se promete valorização ou condição de pagamento, e não se confirma agenda. Termos `a partir de` não autorizam números ou promessas. Handoff continua dependendo de solicitação explícita e consentimento.

## Evidências e limites

Testes com modelo simulado cobrem a sequência completa das capturas com nomes sintéticos, primeira opção, menu persistido após reinício, isolamento por contato, explicação de siglas, erro `Beev`, invalidação de menu antigo, conteúdo interno, origem/fonte falsa, integridade, financeiro, revogação, homologação/rodovia e equipamentos exclusivos. Os testes anteriores de informação ausente agora removem explicitamente o dado do catálogo de teste, pois ele passou a existir na fonte oficial; a proteção de abstenção continua testada.

As transcrições em `evaluations/knowledge-expansion-before-after.json` são execuções do grafo com o mesmo simulador e entradas, comparadas ao commit 822a484. Não representam avaliação real do Groq, qualidade humana, custo real de inferência ou taxa de conversão. Não foram enviados WhatsApp, chamadas ao CRM ou inferência paga por esta avaliação.

Pendências: validar tom com usuários/modelo real; ampliar paráfrases e conteúdo oficial; esclarecer conflitos/ano-modelo; adicionar dados reais da loja e agenda somente quando fornecidos e autorizados. Manuais PDF não foram carregados nesta execução. O conteúdo curado não cobre toda pergunta possível. Não há garantia de resposta universal nem de conversão em visita.

Gates finais executados: 355 testes Pytest passaram; Ruff, compilação Python e `git diff --check` passaram. Permanece um aviso de depreciação upstream do LangChain. Nenhuma dependência nova foi instalada.

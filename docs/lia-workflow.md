# Workflow da Lia — atendimento e operação

Mapa do baseline `1db98ff`. Para a implementação em avaliação, consulte [Lia v3](lia-v3.md).

Mapa do código em 2026-11-02. **Atual** descreve comportamento implementado;
**proposto** é desenho para revisão, sem implementação neste checkpoint.
O fluxograma pode ser visualizado no GitHub e no [desenho interativo](diagrams/lia-workflow.html).

## 1. Atendimento completo atual pelo WhatsApp

```mermaid
flowchart TD
    C[Cliente envia mensagem privada] --> E[Evolution API recebe evento]
    E --> H[Webhook FastAPI: segredo, instância e tamanho]
    H --> V{Evento e remetente aceitos?}
    V -->|Não| I[Ignorar ou rejeitar; sem LLM]
    V -->|Sim| D{ID já recebido?}
    D -->|Sim| A[ACK duplicate; não executar de novo]
    D -->|Não| Q[Limite por pessoa; persistir inbox; ACK queued]
    Q --> W[Worker reivindica próximo evento]
    W --> X{Pedido de exclusão local?}
    X -->|Sim| Z[Apagar memória e oportunidades; cancelar pendências; preparar confirmação]
    X -->|Não| P[Identidade por remetente e instância; abrir ou recuperar conversa]
    P --> M[Carregar estado do SQLite antes do turno]
    M --> G[Executar o LangGraph existente]
    G --> S[Salvar nome, perfil, contexto e oportunidade local elegível]
    S --> O[Persistir resposta e partes na outbox]
    Z --> O
    O --> F{Envio habilitado?}
    F -->|Não| DR[Marcar dry_run; não enviar]
    F -->|Sim| T[Revalidar texto; conferir aprovação, arquivo, MIME e hash das fotos]
    T --> API[Enviar texto e imagens binárias pela Evolution]
    API --> OK{Aceite com ID confirmado?}
    OK -->|Sim| SENT[Registrar partes sent; evento sent]
    OK -->|Não ou exceção| REV[Marcar review; envio incerto não é repetido automaticamente]
    SENT --> C
```

Detalhes: grupos, status, mensagens próprias e LID sem alias telefônico são ignorados.
Modo `*` foi autorizado e aceita qualquer remetente privado. Há 40 eventos por
pessoa/dia; ainda não há orçamento global de inferência. Exclusão é local, não
remove histórico da Evolution/WhatsApp. `sent` confirma aceite da API, não leitura.
Retry limitado ocorre para conexão não estabelecida e HTTP 429; erros ambíguos
ficam para revisão. Exceções anteriores ao envio também podem terminar em review.

## 2. Decisões dentro do LangGraph atual

```mermaid
flowchart TD
    ST[Estado recuperado; zerar orçamento e evidências do turno] --> C[consult: atualizar perfil e reconhecer intenção]
    C --> SOC{Reação social reconhecida?}
    SOC -->|Sim| SL[LLM escreve JSON social; vocabulário validado; fallback se inválido]
    SOC -->|Não| NBA{Necessidade ou rotina reconhecida?}
    NBA -->|Sim| NV[LLM escolhe índice entre frases prontas; pergunta definida pelo servidor]
    NBA -->|Não| CO[Outros caminhos: nome, consentimento, distância, recarga e contato]
    SL --> GU[guard: política comercial e saudação]
    NV --> GU
    CO --> GU
    GU --> R{Já existe resposta ou pedido proibido?}
    R -->|Sim| OUT[output: validar resposta, identidade e handoff]
    R -->|Não| SE[select: resolver modelo, motorização e intenção]
    SE --> AM{Seleção ambígua ou incompleta?}
    AM -->|Sim| CL[Resposta pronta pedindo esclarecimento]
    CL --> OUT
    AM -->|Não| PL[Escolher consulta determinística ou tool calling do modelo]
    PL --> TL[tools: apenas list_vehicles, get_vehicle_details, search_vehicle_media]
    TL --> ER{Falha de ferramenta?}
    ER -->|Sim| EF[Resposta pronta de erro preservando contexto]
    EF --> OUT
    ER -->|Não| CP[compose: montar resposta]
    CP --> K{Tipo de evidência}
    K -->|Fotos| PH[Legenda pronta; fotos novas aprovadas; até 3 por resposta]
    K -->|Fatos aprovados| FA[LLM seleciona fact_ids; servidor renderiza frases verificadas]
    K -->|Sem fatos ou mídia| AB[Resposta pronta de ausência de evidência]
    K -->|Lista de veículos| LI[Resposta pronta com modelos e motorizações]
    PH --> OUT
    FA --> OUT
    AB --> OUT
    LI --> OUT
    OUT --> END[Resposta com text, source_ids e media_ids; persistir estado]
```

`consult`, `guard`, `select`, `tools`, `compose` e `output` são nós do mesmo
grafo. As ramificações dentro dos nós acima são lógica Python, não novos agentes.
O piloto usa predominantemente seleção determinística. Até duas chamadas LLM
por turno; contexto compacto e fatos permitidos. O modelo atual é configurável.

## 3. Onde a experiência fica rígida

| Ponto comprovado no código | Consequência possível |
| --- | --- |
| `social_intent` reconhece um conjunto limitado de expressões | Uma paráfrase pode cair na consulta técnica por engano. |
| Resposta social usa allowlist de palavras | Uma formulação natural válida pode ser rejeitada e virar fallback. |
| Necessidade reconhecida usa LLM apenas para escolher um índice | Trocar o modelo não muda substancialmente a formulação disponível. |
| Mudança de prioridade sem fato pode acrescentar aviso de ausência de evidência | Compartilhar uma necessidade pode soar como pergunta técnica recusada. |
| Resposta à informação de recarga é um template | A conversa pode parecer encerrada após o cliente responder. |
| Grounding técnico possui três fatos revisados | Cobertura pequena de FAQ, especialmente B10 REEV. |
| `output` substitui referências não solicitadas a consultor | Segurança preservada, mas composição anterior pode ser perdida. |

O replay sintético do cenário viagem/economia foi executado sem inferência real.
Depois de “em casa”, a resposta atual apenas registra recarga e declara que os
detalhes técnicos precisam ser verificados. Isso evidencia o template, não mede
qualidade de um novo modelo nem comprova o comportamento em todas as conversas.

## 4. Fluxo consultivo proposto — ainda não implementado

```mermaid
flowchart TD
    IN[Mensagem recebida] --> DB[Consultar identidade e contexto no banco]
    DB --> KN{Contato conhecido?}
    KN -->|Sim| RE[Retomar interesse e histórico sem repetir apresentação ou nome]
    KN -->|Não| NEW[Apresentar Lia como IA uma vez; atender pedido específico primeiro]
    NEW --> NAME[Perguntar nome quando apropriado; não insistir nem bloquear]
    NAME --> INT[Entender ato conversacional no contexto]
    RE --> INT
    INT --> POL{Solicitação proibida?}
    POL -->|Sim| SAFE[Limite seguro e continuidade sem oferta automática de consultor]
    POL -->|Não| KIND{O que o cliente está fazendo?}
    KIND -->|Reagindo ou contando rotina| ENG[LLM desenvolve conversa com contexto; sem consulta técnica obrigatória]
    KIND -->|Pedindo informação técnica| FACT[Consultar catálogo aprovado; documentos só se necessário e implementado]
    KIND -->|Conhecendo veículo ou pedindo fotos| MEDIA[Resolver veículo canônico e enviar fotos aprovadas não repetidas]
    KIND -->|Pedindo humano explicitamente| CONS{Autoriza compartilhar dados?}
    CONS -->|Não| NO[Respeitar recusa e continuar por aqui]
    CONS -->|Sim| SUM[Coletar somente dados mínimos e preparar resumo local]
    FACT --> EN{Evidência suficiente?}
    EN -->|Sim| VALUE[Explicar fato verificado no contexto da necessidade]
    EN -->|Não| MISS[Limitação breve; alternativa útil sem encerrar diálogo]
    ENG --> VAL[Validar fatos, política e consentimento fora do modelo]
    VALUE --> VAL
    MISS --> VAL
    MEDIA --> VAL
    SUM --> VAL
    NO --> VAL
    SAFE --> VAL
    VAL --> SAVE[Salvar contexto, fatos e fotos apresentados; oportunidade local]
    SAVE --> SEND[Entregar resposta; próxima ação contextual; pergunta opcional]
    SUM -.-> CRM[CRM futuro: integração não implementada]
```

Oportunidades comerciais locais já existem. A melhoria proposta é na escolha da
ação e composição, não na criação de outro grafo ou pipeline paralelo.

## 5. Outros canais e componentes

- **Chat web:** HTML/CSS/JavaScript → sessão privada → identidade de navegador
  → memória SQLite quando configurada → mesma implementação SalesAgent →
  barreira HTTP `/v1/` → texto e resolução de mídia aprovada.
- **API:** Bearer e token de sessão → SalesAgent → barreira HTTP. Não compartilha
  automaticamente identidade ou memória persistente com o WhatsApp.
- **Terminal:** CLI → SalesAgent → saída validada; contexto em memória da sessão,
  sem ligar automaticamente o banco de pessoas do piloto. Mostra IDs de mídia.
- **Dados atuais:** catálogo/fatos em JSON, fotos no disco e memória/oportunidades
  em SQLite. PostgreSQL/Redis em execução pertencem à Evolution. pgvector e RAG
  documental não participam deste fluxo de atendimento.
- **Operação:** systemd supervisiona backend; Docker supervisiona Evolution e suas
  dependências. Readiness do backend não prova que o WhatsApp está conectado.

## 6. Próximas mudanças e critérios de validação

1. Reproduzir paráfrases, respostas curtas e continuidade após recarga em testes.
2. Melhorar reconhecimento contextual e composição, preservando validação factual,
   política, consentimento e memória por contato.
3. Comparar transcrições sintéticas antes/depois; não depender apenas de snapshots.
4. Comparar provedores/modelos somente depois, com orçamento real autorizado.

Código rastreado: `app/channels/evolution_worker.py`, `evolution_store.py`,
`app/agent/service.py`, `consultative.py`, `social.py`, `grounding.py`,
`app/pilot_store.py`, `app/api/web_chat.py` e `commercial_boundary.py`.
Nenhum comportamento proposto foi ativado por esta documentação.

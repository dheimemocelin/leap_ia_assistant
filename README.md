<img src="assets/icon.svg" width="72" height="72" alt="LEAP AI Assistant">

# LEAP AI Assistant · Lia

**Conhecer o carro. Entender o cliente. Aproximar a próxima visita à loja.**

A Lia é uma assistente virtual para atendimento Leapmotor pelo WhatsApp e pelo chat web. Apresenta veículos, mostra fotos, esclarece dúvidas com informações verificadas e registra o interesse de cada pessoa para dar continuidade ao atendimento.

O foco atual é a **pré-venda consultiva**: ajudar quem está escolhendo um carro, compreender sua rotina e transformar interesse em uma oportunidade comercial. A base de conhecimento também está sendo preparada para responder dúvidas do dia a dia sobre os veículos.

> **Em piloto:** WhatsApp conectado, catálogo e imagens aprovadas, memória por contato e oportunidades salvas em banco local. A integração com CRM é uma próxima etapa. O RAG documental está em desenvolvimento e permanece desativado no piloto comercial atual.

[Como testar](#como-testar-localmente) · [Documentação](#documentação) · [Segurança](SECURITY.md)

## Uma conversa com continuidade

| O cliente quer… | A Lia ajuda a… |
| --- | --- |
| Conhecer a marca e os veículos | Explorar o catálogo disponível, usando linguagem acessível. |
| Ver o carro | Encontrar fotos aprovadas do modelo e da motorização corretos. |
| Esclarecer uma dúvida | Consultar características e fontes aprovadas, respeitando os limites da base. |
| Escolher para sua rotina | Conversar sobre família, trabalho, cidade, viagens e recarga, sem prometer benefícios não comprovados. |
| Retomar o atendimento | Recuperar o nome voluntariamente informado e o contexto associado ao contato. |
| Conhecer o veículo pessoalmente | Receber a localização configurada da loja e registrar seu interesse em visita. |

O atendimento não exige que a pessoa conheça siglas como BEV ou REEV. Internamente, os identificadores canônicos preservam a separação entre modelos e motorizações; na conversa, a apresentação usa termos mais acessíveis, como elétrico e ultra-híbrido.

A proposta é entregar valor antes de pedir dados: apresentar o veículo, aproveitar o que o cliente compartilha e fazer perguntas progressivas, sem exigir nome ou transformar a conversa em cadastro.

## Do interesse à oportunidade

A memória do piloto pode guardar nome preferido, veículo de interesse, contexto de uso, necessidades, interesse em troca e preferência de visita. Esses dados ajudam a continuar o atendimento sem começar do zero.

- **Nome opcional:** vinculado ao contato quando informado voluntariamente.
- **Qualificação gradual:** informações registradas ao longo da conversa.
- **Visita à loja:** interesse e preferência registrados, sem confirmar agendamento ou disponibilidade.
- **Veículo na troca:** orientação para avaliação presencial, sem prometer aceitação, valorização ou valores.
- **Atendimento humano:** somente mediante solicitação explícita; compartilhar dados exige consentimento.
- **CRM:** o objetivo é criar oportunidades autorizadas com um resumo útil para o time comercial. Hoje elas permanecem no banco local.

O cliente não precisa de senha para conversar pelo WhatsApp. A autenticação da integração é feita no servidor.

## O que está implementado

| Componente | Situação |
| --- | --- |
| WhatsApp / Evolution API | Recebimento privado, respostas em texto e envio de imagens utilizados no piloto. |
| Chat web e terminal | Canais locais para experimentar o agente existente. |
| LangGraph e LLM | Fluxo conversacional com estados explícitos, Groq e limites de chamadas por turno. |
| Catálogo e biblioteca de mídia | Consultas determinísticas, filtros por veículo/motorização e controle de aprovação. |
| Memória e oportunidades | Persistência local em SQLite, com contexto por contato e recursos de exclusão. |
| Entrega de mensagens | Inbox/outbox, deduplicação e revisão de envios incertos. |
| Indicador de digitação | Delay nativo configurável na Evolution; aparência no aparelho ainda depende de validação visual. |
| Segurança comercial | Política independente do LLM e barreira de validação antes da saída. |
| Lia Knowledge | Fundação documental, recuperação textual e busca híbrida local em desenvolvimento; desativada no piloto comercial. |
| Criação de oportunidades no CRM | Planejada; sem envio externo ativo. |

As 12 fotos fornecidas foram autorizadas para o contexto do piloto. Essa autorização não representa licença geral de reutilização nem aprovação automática de novos materiais.

## Arquitetura em poucas palavras

O backend **Python/FastAPI** recebe as mensagens. O **LangGraph existente** mantém o estado, coordena ferramentas de consulta e compõe a resposta com o provedor configurado. A saída passa pelas políticas comerciais antes de chegar ao canal.

O piloto utiliza **SQLite** para memória, oportunidades e controle de entrega. A **Evolution API** opera como infraestrutura separada de WhatsApp, com seus próprios serviços e credenciais. PostgreSQL, pgvector e Redis fazem parte das opções de infraestrutura do projeto; não são o armazenamento ativo do RAG local nem substituem automaticamente o banco do piloto.

O módulo **Lia Knowledge** preserva documento, versão, página e aprovação dos trechos. Os seis manuais somam 1.515 páginas; extração bem-sucedida não significa conteúdo aprovado. Trechos corrompidos, ambíguos ou sem aplicabilidade confirmada não devem alimentar respostas factuais.

Veja a [arquitetura](docs/architecture.md), os [contratos](docs/contracts.md) e o [workflow desenhado](docs/lia-workflow.md). Documentos de etapas anteriores devem ser lidos junto dos checkpoints mais recentes.

## Limites que fazem parte do produto

A Lia se identifica como assistente virtual. Não informa preços, descontos, parcelas, financiamento ou valores de avaliação de usados. Não negocia, promete estoque, reserva nem conclui vendas.

Características técnicas exigem evidências aprovadas. Conversar sobre a rotina do cliente não autoriza inventar autonomia real, economia, rentabilidade ou aceitação em plataformas. O piloto comercial não oferece diagnóstico de defeitos ou assistência técnica.

Testes determinísticos verificam regras e regressões; não comprovam, sozinhos, naturalidade ou qualidade de todas as conversas. Avaliação humana e acompanhamento do piloto continuam necessários. Falhas de conexão, limites do provedor e respostas inadequadas ainda são riscos operacionais.

## Como testar localmente

Requer **Python 3.12+**. A integração WhatsApp exige uma Evolution API configurada separadamente; ela não é necessária para iniciar pelo terminal.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
```

Se já existir um `.env`, preserve-o em vez de executar a cópia novamente. Configure o provedor e o modelo nesse arquivo, mantendo a chave somente no ambiente local:

```dotenv
LLM_PROVIDER=groq
LLM_MODEL=openai/gpt-oss-120b
```

Preencha também `GROQ_API_KEY`. O modelo acima é a configuração utilizada no piloto; acesso, disponibilidade e limites dependem da conta do provedor. Consulte as demais opções em [.env.example](.env.example), incluindo as flags de comportamento comercial, orquestração e conhecimento, que não devem ser presumidas ativas em uma instalação nova.

**Conversa no terminal:**

```bash
python3 -m app.cli --reviewed-catalog
```

O comando usa o catálogo interno revisado e pode consumir a cota do provedor. O terminal apresenta identificadores de mídia; a exibição e o envio de imagens pertencem aos canais próprios.

**API local:**

```bash
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

A documentação OpenAPI fica em `http://127.0.0.1:8000/docs`. Para chat web, persistência e WhatsApp, siga os runbooks abaixo antes de habilitar canais ou envios. Credenciais, conversas, bancos locais e QR Codes não devem ser versionados.

## Testes e evidências

Os gates podem ser executados sem inferência real:

```bash
python3 -m pytest -q
python3 -m ruff check app tests scripts
python3 -m compileall -q app tests scripts
git diff --check
```

A suíte cobre catálogo, importação e seleção de mídia, aprovação, memória, conversas com LLM simulado, políticas comerciais e contratos de integração. Os relatórios distinguem testes automatizados, transcrições sintéticas e verificações externas efetivamente realizadas.

## Documentação

| Assunto | Referência |
| --- | --- |
| Piloto comercial, qualificação e convite à loja | [Entrega comercial](docs/sales-delivery-pilot.md) |
| Digitação e correções de continuidade | [WhatsApp e contexto comercial](docs/whatsapp-typing-and-sales-context.md) |
| Configuração e diagnóstico do WhatsApp | [Runbook Evolution](docs/evolution-pilot.md) |
| Memória, oportunidades e exclusão local | [Runbook do piloto](docs/pilot-runbook.md) |
| Recuperação documental e revisão de trechos | [Knowledge — Checkpoint A.1](docs/knowledge/checkpoint-a1.md) |
| Composição conversacional e áudio em avaliação | [Lia v3](docs/lia-v3.md) |
| Fluxo e decisões do atendimento | [Workflow da Lia](docs/lia-workflow.md) |
| Estrutura técnica | [Arquitetura](docs/architecture.md) e [modelo de dados](docs/data-model.md) |
| APIs e validação | [Contratos](docs/contracts.md) e [plano de testes](docs/testing.md) |
| Prioridades e dependências | [Backlog](docs/backlog.md) e [configuração](docs/dependencies.md) |

## Próximos passos

1. Avaliar conversas completas com clientes de teste e reduzir repetições e fallbacks inadequados.
2. Ampliar informações e dúvidas respondidas com fontes oficiais revisadas.
3. Validar o RAG documental antes de reativá-lo no atendimento comercial.
4. Integrar oportunidades ao CRM com autorização, dados mínimos e idempotência.
5. Fortalecer observabilidade, privacidade, recuperação de falhas e controles de consumo.

## Licença e uso dos materiais

O código é distribuído sob [licença MIT](LICENSE). Fotografias e marcas possuem [condições próprias](assets/MEDIA-NOTICE.md), sem licença geral de reutilização. Consulte a [política de segurança](SECURITY.md) e a [revisão de publicação](docs/publication-review.md).

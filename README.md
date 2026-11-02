<img src="assets/icon.svg" width="64" height="64" alt="LEAP AI Assistant">

# LEAP AI Assistant

**Uma conversa que ajuda a conhecer o veículo e aproxima o cliente da próxima decisão.**

O LEAP AI Assistant é um assistente de inteligência artificial para atendimento Leapmotor. Começa pela pré-venda: apresenta veículos, mostra fotos, esclarece dúvidas e entende o que cada pessoa procura. A proposta também contempla FAQ e informações dos veículos, sempre com base em conteúdo verificado.

A Lia, assistente virtual do projeto, atende pelo WhatsApp e pelo chat web. O objetivo é oferecer uma conversa natural, útil e contextual — aproveitando o que o cliente já contou, sem transformar o atendimento em um formulário.

**Status:** piloto funcional no WhatsApp, com memória e oportunidades em banco local. Integração com CRM planejada.

## Da primeira dúvida à oportunidade

| Momento | Como o assistente ajuda |
| --- | --- |
| Conhecer os veículos | Apresenta modelos, motorizações e fotos aprovadas, sem misturar versões. |
| Tirar dúvidas | Consulta informações verificadas sobre características e autonomia; a cobertura de FAQ evolui com a base aprovada. |
| Entender a necessidade | Reconhece contextos como família, trabalho, uso urbano e viagens, sem prometer benefícios não comprovados. |
| Manter a conversa | Lembra o nome informado e o contexto no canal configurado, evitando perguntas e apresentações repetidas. |
| Identificar interesse | Registra progressivamente necessidades e sinais de compra em uma oportunidade local. |
| Conectar ao time comercial | Mediante pedido do cliente e consentimento, prepara um resumo para atendimento humano. A criação da oportunidade no CRM é a próxima integração. |

O cliente não precisa de senha para conversar pelo WhatsApp. As credenciais da integração ficam no servidor.

## Um exemplo de atendimento

> **Cliente:** Quero conhecer o B10.
> **Lia:** Você quer explorar o elétrico BEV ou o híbrido REEV?
> **Cliente:** BEV.
> **Lia:** Apresenta fotos aprovadas dessa motorização e continua a conversa a partir do interesse do cliente.
> **Cliente:** Pensei em usar para trabalhar com aplicativo.
> **Lia:** Reconhece o uso profissional e explora a rotina ou o acesso à recarga, sem prometer economia, rentabilidade ou aceitação em plataformas.

*Exemplo ilustrativo do comportamento desejado, sem representar uma especificação técnica ou transcrição de cliente real.*

## O que já funciona

- **WhatsApp via Evolution API:** recebimento de mensagens privadas, resposta de texto e envio de imagens, validados em piloto real.
- **Chat web e terminal:** canais para experimentar o mesmo agente conversacional.
- **LangGraph com Groq:** um único fluxo, ferramentas de consulta e limite de chamadas por turno.
- **Catálogo e mídia:** consulta determinística por veículo e motorização, com controle de aprovação e fontes.
- **Memória persistente:** nome preferido, contexto compacto e oportunidades no banco local do piloto; comando para apagar dados locais.
- **Entrega controlada:** deduplicação, inbox/outbox e revisão de envios incertos para reduzir duplicações.
- **Proteções comerciais:** política independente do modelo e validação obrigatória antes da saída.

O piloto possui 12 fotos autorizadas para seu contexto de teste. Isso não representa autorização irrestrita para publicação ou aprovação automática do catálogo original.

## O que vem a seguir

1. **Melhorar a experiência de atendimento:** mais continuidade, respostas contextualizadas e menos repetição, com avaliações de conversas completas.
2. **Comparar modelos:** escolher a configuração que equilibre naturalidade, precisão, latência e consumo.
3. **Ampliar a base de conhecimento:** enriquecer catálogo e FAQ com fontes oficiais revisadas; adicionar RAG quando a recuperação documental trouxer valor.
4. **Integrar o CRM:** criar oportunidades autorizadas com resumo da conversa, dados mínimos e prevenção de duplicidade. Hoje o registro permanece local.
5. **Fortalecer a operação:** monitoramento de conexão, revisão de falhas, métricas de qualidade e controles de consumo.

A orquestração atual será evoluída conforme as avaliações, preservando o LangGraph existente. Consulte o [plano da próxima iteração](docs/next-iteration-plan.md).

## Confiança no atendimento

A Lia se identifica como assistente virtual e trabalha com informações aprovadas. Quando faltam evidências, deve reconhecer a limitação e manter uma conversa útil, sem inventar atributos.

O assistente **não informa preços, descontos, parcelas, financiamento ou avaliação de usados**. Também não negocia, promete estoque, reserva ou conclui vendas. Atendimento humano ocorre mediante solicitação explícita do cliente; compartilhamento de dados exige consentimento.

O funcionamento do piloto não comprova estabilidade prolongada ou qualidade em todos os cenários. O checkpoint mais recente registra **193 testes automatizados aprovados**, além de Ruff, compilação Python e verificação de diff. Testes usam dados sintéticos e LLM simulado, sem chamadas pagas.

## Para desenvolver e testar

Requer **Python 3.12+**. Configure o ambiente sem versionar credenciais:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
```

Preencha no `.env` o provedor, modelo e credenciais necessários. Para conversar pelo terminal com o catálogo interno revisado:

```bash
python3 -m app.cli --reviewed-catalog
```

Esse comando pode consumir a cota do provedor LLM. O terminal apresenta identificadores de mídia; imagens são exibidas/enviadas pelos canais próprios.

Para iniciar a API local:

```bash
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

OpenAPI em `http://127.0.0.1:8000/docs`. Consulte os runbooks antes de ativar os canais. A infraestrutura compartilhada da Evolution fica fora deste repositório; PostgreSQL e Redis próprios do canal não substituem o SQLite utilizado pelo piloto LEAP.

Para executar os gates sem inferência real:

```bash
python3 -m pytest -q
python3 -m ruff check app tests scripts
python3 -m compileall -q app tests scripts
git diff --check
```

## Documentação

| Quero entender… | Onde consultar |
| --- | --- |
| Como operar e diagnosticar o WhatsApp | [Runbook Evolution](docs/evolution-pilot.md) |
| Todos os passos e decisões do atendimento | [Workflow desenhado da Lia](docs/lia-workflow.md) |
| Memória, oportunidades e exclusão local | [Piloto e persistência](docs/pilot-runbook.md) |
| Refatoração de composição, memória e áudio em avaliação | [Lia v3](docs/lia-v3.md) |
| Conhecimento oficial, linguagem simples e escolhas por contexto | [Expansão e evidências](docs/knowledge-expansion.md) |
| Próximas melhorias de atendimento | [Plano da próxima iteração](docs/next-iteration-plan.md) |
| Estrutura e decisões técnicas | [Arquitetura](docs/architecture.md) e [modelo de dados](docs/data-model.md) |
| APIs, ferramentas e validações | [Contratos](docs/contracts.md) e [testes](docs/testing.md) |
| Prioridades e configuração | [Backlog](docs/backlog.md) e [dependências](docs/dependencies.md) |

Alguns documentos descrevem etapas anteriores; o runbook Evolution e o plano da próxima iteração registram o checkpoint operacional atual. Credenciais, banco local, conversas e QR Codes ficam fora do Git.

## Código, imagens e segurança

O código é distribuído sob [licença MIT](LICENSE). Fotografias e marcas têm [condições próprias](assets/MEDIA-NOTICE.md), sem licença geral de reutilização. Consulte a [política de segurança](SECURITY.md) e a [revisão de preparação para publicação](docs/publication-review.md).

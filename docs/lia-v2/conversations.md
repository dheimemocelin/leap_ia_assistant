# Lia V2 — conversas comparativas

Execuções do mesmo grafo com **LLM simulado**, dados sintéticos e flag V2 desligada/ligada. Não são transcrições de clientes ou testes reais do Groq. IDs das fontes, imagens, chamadas e estados completos estão em [transcripts.json](transcripts.json).

## name_close_return

### Antes — V2 desligada

**Cliente:** Oi

**Lia:** Oi! Sou a Lia, assistente virtual da Leapmotor. Como posso te ajudar a escolher seu próximo carro?

**Cliente:** Pessoa Sintetica

**Lia:** Estou acompanhando o que você está contando. Pode seguir no seu ritmo.

**Cliente:** B10 BEV

**Lia:** Separei estas imagens do B10 elétrico para você começar a conhecê-lo. Como posso te chamar?

_Mídias selecionadas: 3; nenhuma entrega externa foi executada nesta avaliação._

**Cliente:** Vou pensar

**Lia:** Não consegui buscar essa informação agora. Pode me dizer de outro jeito?

**Cliente:** Oi

**Lia:** Oi! Como posso te ajudar a escolher seu próximo carro?

**Cliente:** Me fala daquele carro

**Lia:** Vamos continuar a partir do seu interesse e das suas prioridades. O B10 elétrico usa propulsão totalmente elétrica, alimentada por bateria. O B10 elétrico tem central multimídia de 14,6 polegadas com espelhamento sem fio via Apple CarPlay e Android Auto. Como você imagina usar o carro no dia a dia?

Estado final: `None`. Transferências locais: `{}`.

### Depois — V2 ligada

**Cliente:** Oi

**Lia:** Olá! Sou a Lia, assistente virtual da Leapmotor. Como posso te chamar?

**Cliente:** Pessoa Sintetica

**Lia:** Prazer, Pessoa Sintetica. O que te trouxe até a Leapmotor?

**Cliente:** B10 BEV

**Lia:** Separei estas imagens do B10 elétrico para você começar a conhecê-lo. Como você pretende usar o carro no dia a dia?

_Mídias selecionadas: 3; nenhuma entrega externa foi executada nesta avaliação._

**Cliente:** Vou pensar

**Lia:** Claro, pense com calma. Guardamos o contexto do B10 elétrico para quando você quiser retomar.

**Cliente:** Oi

**Lia:** Oi, Pessoa Sintetica! Quer continuar conhecendo o B10 elétrico?

**Cliente:** Me fala daquele carro

**Lia:** Vamos continuar a partir do seu interesse e das suas prioridades. O B10 elétrico usa propulsão totalmente elétrica, alimentada por bateria. O B10 elétrico tem central multimídia de 14,6 polegadas com espelhamento sem fio via Apple CarPlay e Android Auto.

Estado final: `ACTIVE`. Transferências locais: `{}`.

## repeat_and_other_photo

### Antes — V2 desligada

**Cliente:** C10 BEV

**Lia:** Sou a Lia, assistente virtual da Leapmotor. Separei estas imagens do C10 elétrico para você começar a conhecê-lo. Como posso te chamar?

_Mídias selecionadas: 3; nenhuma entrega externa foi executada nesta avaliação._

**Cliente:** Manda novamente

**Lia:** Prazer, Manda novamente! Como você pretende usar o carro no dia a dia?

**Cliente:** Cadê?

**Lia:** Estou acompanhando o que você está contando. Pode seguir no seu ritmo.

**Cliente:** Tem outra foto?

**Lia:** Claro! Separei uma foto do C10 elétrico. Toque nela para ampliar.

_Mídias selecionadas: 1; nenhuma entrega externa foi executada nesta avaliação._

Estado final: `None`. Transferências locais: `{}`.

### Depois — V2 ligada

**Cliente:** C10 BEV

**Lia:** Sou a Lia, assistente virtual da Leapmotor. Separei estas imagens do C10 elétrico para você começar a conhecê-lo. Como posso te chamar?

_Mídias selecionadas: 3; nenhuma entrega externa foi executada nesta avaliação._

**Cliente:** Manda novamente

**Lia:** Separei estas fotos do C10 elétrico para mostrar aqui.

_Mídias selecionadas: 3; nenhuma entrega externa foi executada nesta avaliação._

**Cliente:** Cadê?

**Lia:** Separei estas fotos do C10 elétrico para mostrar aqui.

_Mídias selecionadas: 3; nenhuma entrega externa foi executada nesta avaliação._

**Cliente:** Tem outra foto?

**Lia:** Separei uma foto do C10 elétrico para mostrar aqui.

_Mídias selecionadas: 1; nenhuma entrega externa foi executada nesta avaliação._

Estado final: `ACTIVE`. Transferências locais: `{}`.

## technical_day_return

### Antes — V2 desligada

**Cliente:** C10 BEV

**Lia:** Sou a Lia, assistente virtual da Leapmotor. Separei estas imagens do C10 elétrico para você começar a conhecê-lo. Como posso te chamar?

_Mídias selecionadas: 3; nenhuma entrega externa foi executada nesta avaliação._

**Cliente:** Pessoa Sintetica

**Lia:** Prazer, Pessoa Sintetica! Como você pretende usar o carro no dia a dia?

**Cliente:** Qual a autonomia?

**Lia:** Vamos continuar a partir do seu interesse e das suas prioridades. O C10 elétrico tem autonomia de até 338 km no ciclo PBEV.

**Cliente:** Até mais

**Lia:** Estou acompanhando o que você está contando. Pode seguir no seu ritmo.

**Cliente:** Qual a autonomia dele?

**Lia:** Vamos continuar a partir do seu interesse e das suas prioridades. O C10 elétrico tem autonomia de até 338 km no ciclo PBEV.

Estado final: `None`. Transferências locais: `{}`.

### Depois — V2 ligada

**Cliente:** C10 BEV

**Lia:** Sou a Lia, assistente virtual da Leapmotor. Separei estas imagens do C10 elétrico para você começar a conhecê-lo. Como posso te chamar?

_Mídias selecionadas: 3; nenhuma entrega externa foi executada nesta avaliação._

**Cliente:** Pessoa Sintetica

**Lia:** Prazer, Pessoa Sintetica! Como você pretende usar o carro no dia a dia?

**Cliente:** Qual a autonomia?

**Lia:** Vamos continuar a partir do seu interesse e das suas prioridades. O C10 elétrico tem autonomia de até 338 km no ciclo PBEV.

**Cliente:** Até mais

**Lia:** Obrigada pela conversa. Até mais!

**Cliente:** Qual a autonomia dele?

**Lia:** Vamos continuar a partir do seu interesse e das suas prioridades. O C10 elétrico tem autonomia de até 338 km no ciclo PBEV.

Estado final: `ACTIVE`. Transferências locais: `{}`.

## usage_and_visit_decline

### Antes — V2 desligada

**Cliente:** B10 BEV

**Lia:** Sou a Lia, assistente virtual da Leapmotor. Separei estas imagens do B10 elétrico para você começar a conhecê-lo. Como posso te chamar?

_Mídias selecionadas: 3; nenhuma entrega externa foi executada nesta avaliação._

**Cliente:** Pessoa Sintetica

**Lia:** Prazer, Pessoa Sintetica! Como você pretende usar o carro no dia a dia?

**Cliente:** Vou usar para Uber

**Lia:** Entendi que você pensa no carro para trabalhar com aplicativo. Vamos olhar sua rotina antes de tirar conclusões. Em um dia de trabalho, aproximadamente quantos quilômetros você pretende rodar?

**Cliente:** Quero visitar a loja

**Lia:** Vamos continuar a partir do seu interesse e das suas prioridades. Que dia e período seriam melhores para você conhecer o carro na loja?

**Cliente:** Não quero falar com vendedor

**Lia:** Tudo bem, seguimos por aqui sem compartilhar seus dados. Você pode continuar vendo o carro no seu ritmo.

**Cliente:** Quero continuar

**Lia:** Estou acompanhando o que você está contando. Pode seguir no seu ritmo.

Estado final: `None`. Transferências locais: `{}`.

### Depois — V2 ligada

**Cliente:** B10 BEV

**Lia:** Sou a Lia, assistente virtual da Leapmotor. Separei estas imagens do B10 elétrico para você começar a conhecê-lo. Como posso te chamar?

_Mídias selecionadas: 3; nenhuma entrega externa foi executada nesta avaliação._

**Cliente:** Pessoa Sintetica

**Lia:** Prazer, Pessoa Sintetica! Como você pretende usar o carro no dia a dia?

**Cliente:** Vou usar para Uber

**Lia:** Entendi que você pensa no carro para trabalhar com aplicativo. Vamos olhar sua rotina antes de tirar conclusões. Em um dia de trabalho, aproximadamente quantos quilômetros você pretende rodar?

**Cliente:** Quero visitar a loja

**Lia:** Podemos organizar o que você quer conhecer na loja. Você gostaria de falar com um consultor?

**Cliente:** Não quero falar com vendedor

**Lia:** Tudo bem, seguimos por aqui sem compartilhar seus dados. Você pode continuar vendo o carro no seu ritmo.

**Cliente:** Quero continuar

**Lia:** Você estava conhecendo o B10 elétrico. Podemos retomar por ele.

Estado final: `ACTIVE`. Transferências locais: `{}`.

## authorized_local_queue

### Antes — V2 desligada

**Cliente:** Oi

**Lia:** Oi! Sou a Lia, assistente virtual da Leapmotor. Como posso te ajudar a escolher seu próximo carro?

**Cliente:** Pessoa Sintetica

**Lia:** Estou acompanhando o que você está contando. Pode seguir no seu ritmo.

**Cliente:** B10 BEV

**Lia:** Separei estas imagens do B10 elétrico para você começar a conhecê-lo. Como posso te chamar?

_Mídias selecionadas: 3; nenhuma entrega externa foi executada nesta avaliação._

**Cliente:** Quero falar com um consultor

**Lia:** Posso preparar a continuidade com um consultor. Você autoriza compartilhar seu nome, telefone e interesse neste veículo para esse contato?

**Cliente:** sim

**Lia:** Como você gostaria que eu registrasse seu nome?

**Cliente:** Qual a autonomia?

**Lia:** Vamos continuar a partir do seu interesse e das suas prioridades. A autonomia homologada do B10 elétrico é de 288 km pelo Inmetro.

Estado final: `None`. Transferências locais: `{}`.

### Depois — V2 ligada

**Cliente:** Oi

**Lia:** Olá! Sou a Lia, assistente virtual da Leapmotor. Como posso te chamar?

**Cliente:** Pessoa Sintetica

**Lia:** Prazer, Pessoa Sintetica. O que te trouxe até a Leapmotor?

**Cliente:** B10 BEV

**Lia:** Separei estas imagens do B10 elétrico para você começar a conhecê-lo. Como você pretende usar o carro no dia a dia?

_Mídias selecionadas: 3; nenhuma entrega externa foi executada nesta avaliação._

**Cliente:** Quero falar com um consultor

**Lia:** Posso preparar a continuidade com um consultor. Você autoriza compartilhar seu nome, telefone e interesse neste veículo para esse contato?

**Cliente:** sim

**Lia:** Seu resumo está na fila local. O recebimento pelo atendimento humano ainda não foi confirmado.

**Cliente:** Qual a autonomia?

**Lia:** Vamos continuar a partir do seu interesse e das suas prioridades. A autonomia homologada do B10 elétrico é de 288 km pelo Inmetro.

Estado final: `HANDOFF_PENDING`. Transferências locais: `{"queued": 1}`.

## financial_and_pause

### Antes — V2 desligada

**Cliente:** B10 BEV

**Lia:** Sou a Lia, assistente virtual da Leapmotor. Separei estas imagens do B10 elétrico para você começar a conhecê-lo. Como posso te chamar?

_Mídias selecionadas: 3; nenhuma entrega externa foi executada nesta avaliação._

**Cliente:** Pessoa Sintetica

**Lia:** Prazer, Pessoa Sintetica! Como você pretende usar o carro no dia a dia?

**Cliente:** Qual o preço?

**Lia:** Esses detalhes são tratados na loja. Posso te ajudar a escolher a versão e o que você quer conhecer de perto. Você gostaria de visitar a loja?

**Cliente:** Não

**Lia:** Vamos continuar a partir do seu interesse e das suas prioridades.

**Cliente:** Depois eu vejo

**Lia:** Estou acompanhando o que você está contando. Pode seguir no seu ritmo.

**Cliente:** Oi

**Lia:** Oi! Como posso te ajudar a escolher seu próximo carro?

Estado final: `None`. Transferências locais: `{}`.

### Depois — V2 ligada

**Cliente:** B10 BEV

**Lia:** Sou a Lia, assistente virtual da Leapmotor. Separei estas imagens do B10 elétrico para você começar a conhecê-lo. Como posso te chamar?

_Mídias selecionadas: 3; nenhuma entrega externa foi executada nesta avaliação._

**Cliente:** Pessoa Sintetica

**Lia:** Prazer, Pessoa Sintetica! Como você pretende usar o carro no dia a dia?

**Cliente:** Qual o preço?

**Lia:** Podemos organizar o que você quer conhecer na loja. Você gostaria de falar com um consultor?

**Cliente:** Não

**Lia:** Tudo bem, seguimos por aqui sem encaminhar seus dados.

**Cliente:** Depois eu vejo

**Lia:** Combinado, continuamos com o B10 elétrico quando você quiser. Até mais!

**Cliente:** Oi

**Lia:** Oi, Pessoa Sintetica! Quer continuar conhecendo o B10 elétrico?

Estado final: `ACTIVE`. Transferências locais: `{}`.

## model_change_and_rear

### Antes — V2 desligada

**Cliente:** B10 BEV

**Lia:** Sou a Lia, assistente virtual da Leapmotor. Separei estas imagens do B10 elétrico para você começar a conhecê-lo. Como posso te chamar?

_Mídias selecionadas: 3; nenhuma entrega externa foi executada nesta avaliação._

**Cliente:** Pessoa Sintetica

**Lia:** Prazer, Pessoa Sintetica! Como você pretende usar o carro no dia a dia?

**Cliente:** C10 BEV

**Lia:** Separei estas imagens do C10 elétrico para você começar a conhecê-lo.

_Mídias selecionadas: 3; nenhuma entrega externa foi executada nesta avaliação._

**Cliente:** Quero ver a traseira

**Lia:** Estou acompanhando o que você está contando. Pode seguir no seu ritmo.

**Cliente:** Mostra de novo

**Lia:** Pode me contar o que você quer saber sobre o carro?

**Cliente:** Não tenho interesse

**Lia:** Posso reformular a explicação. O que você quer entender melhor sobre o carro?

Estado final: `None`. Transferências locais: `{}`.

### Depois — V2 ligada

**Cliente:** B10 BEV

**Lia:** Sou a Lia, assistente virtual da Leapmotor. Separei estas imagens do B10 elétrico para você começar a conhecê-lo. Como posso te chamar?

_Mídias selecionadas: 3; nenhuma entrega externa foi executada nesta avaliação._

**Cliente:** Pessoa Sintetica

**Lia:** Prazer, Pessoa Sintetica! Como você pretende usar o carro no dia a dia?

**Cliente:** C10 BEV

**Lia:** Separei estas imagens do C10 elétrico para você começar a conhecê-lo.

_Mídias selecionadas: 3; nenhuma entrega externa foi executada nesta avaliação._

**Cliente:** Quero ver a traseira

**Lia:** Separei uma foto do C10 elétrico para mostrar aqui.

_Mídias selecionadas: 1; nenhuma entrega externa foi executada nesta avaliação._

**Cliente:** Mostra de novo

**Lia:** Separei uma foto do C10 elétrico para mostrar aqui.

_Mídias selecionadas: 1; nenhuma entrega externa foi executada nesta avaliação._

**Cliente:** Não tenho interesse

**Lia:** Tudo bem, respeitamos sua decisão. Obrigada pela conversa.

Estado final: `CLOSED`. Transferências locais: `{}`.

## Métricas mecânicas — não são avaliação humana

| Configuração | Turnos | Redigidos pelo simulador | Fallbacks | Respostas com múltiplas perguntas |
| --- | ---: | ---: | ---: | ---: |
| before | 39 | 14 (35.9%) | 2 | 0 |
| after | 39 | 6 (15.4%) | 4 | 0 |

A cobertura comprova transições, retomada, vínculo canônico das mídias, ausência de despacho sem consentimento e distinção de fila/entrega. A redação do simulador continua genérica em algumas respostas técnicas e de uso. O mecanismo V2 não comprova melhoria de naturalidade do provedor real. As rejeições de composição são registradas, não ocultadas como sucesso do LLM.

O uso de redação determinística em identidade, memória e recibos reduz a proporção de turnos redigidos pelo simulador. Isso não é uma métrica de encantamento ou maior inteligência. As respostas livres existentes continuam no mesmo grafo e sob as mesmas políticas.

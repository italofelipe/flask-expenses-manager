# Profile V1 - Especificacao Tecnica

Ultima atualizacao: 2026-02-20

## Objetivo
Definir a evolucao tecnica do perfil de usuario para suportar personalizacao financeira e futuras recomendacoes.

Este documento descreve contrato e arquitetura alvo.
Status de execucao e prioridade ficam em `TASKS.md`.

## Escopo funcional
1. Captura de contexto financeiro minimo no perfil.
2. Perfil de investidor auto declarado pelo usuario.
3. Questionario curto para sugestao indicativa de perfil.
4. Compatibilidade REST e GraphQL para leitura/edicao desses dados.

## Decisoes de produto que impactam o backend
1. `monthly_income_net` representa renda liquida mensal disponivel.
2. `financial_objectives` no perfil e texto livre na fase atual.
3. `state_uf` e opcional no onboarding e editavel depois.
4. `investor_profile` e auto declarado.
5. Questionario auxilia a autodeclaracao, sem substituir escolha do usuario.

## Taxonomia de perfil de investidor (V1)
Valores permitidos:
1. `conservador`
2. `explorador`
3. `entusiasta`

Regra de uso:
1. Valor declarado pelo usuario e o source of truth para perfil atual.
2. Resultado do questionario e armazenado separadamente como sugestao.

## Questionario auxiliar (proposta V1)
Formato:
1. 5 a 10 perguntas objetivas.
2. Respostas de multipla escolha.
3. Score total apenas indicativo.

Perguntas candidatas para backlog:
1. Qual sua experiencia com investimentos? (`nenhuma`, `baixa`, `media`, `alta`)
2. Qual oscilacao mensal de carteira voce tolera sem resgatar? (`baixa`, `media`, `alta`)
3. Em quanto tempo pretende usar a maior parte do dinheiro investido? (`curto`, `medio`, `longo`)
4. Qual seu objetivo principal com investimentos? (`preservar`, `crescer`, `acelerar`)
5. Qual percentual da sua renda liquida voce consegue aportar com constancia? (`baixo`, `medio`, `alto`)
6. Como voce reage a quedas de mercado? (`evita risco`, `aguarda`, `aproveita`)
7. Qual sua preferencia entre previsibilidade e retorno potencial? (`previsibilidade`, `equilibrio`, `retorno`)
8. Qual nivel de complexidade de produtos voce aceita? (`simples`, `moderado`, `avancado`)

## Modelo de dados alvo

### Campos de perfil (dominio principal)
1. `state_uf` (`String(2)`, opcional em onboarding, validacao UF quando preenchido).
2. `occupation` (`String`, opcional em onboarding, recomendado para completude).
3. `investor_profile` (`Enum`, opcional em onboarding, validado por taxonomia V1).
4. `financial_objectives` (`Text`, opcional em onboarding).
5. `monthly_income_net` (`Numeric`, nao negativo).

### Campos auxiliares de questionario
1. `investor_profile_suggested` (`Enum`, calculado por score).
2. `profile_quiz_score` (`Integer` ou `Numeric`, escala definida pelo questionario).
3. `taxonomy_version` (`String`, ex.: `v1`).
4. `profile_quiz_answered_at` (`DateTime`, opcional).

## Contrato de API esperado

### REST
1. `PUT /user/profile` deve aceitar os novos campos sem quebrar payload legado.
2. `GET /user/me` deve retornar os campos normalizados.
3. Endpoint dedicado de quiz pode ser avaliado em fase posterior (`/user/profile/quiz`), ou acoplado ao update de perfil.

### GraphQL
1. `updateUserProfile` deve aceitar os novos campos.
2. `me` deve expor os novos campos.
3. Operacao dedicada para quiz pode ser adicionada sem quebrar schema existente.

## Regras de validacao
1. `monthly_income_net >= 0`.
2. `investor_profile` deve pertencer ao enum V1.
3. `state_uf`, quando informado, deve seguir UF valida (`AC`, `AL`, ..., `TO`).
4. `financial_objectives` aceita texto livre com limite de tamanho.
5. Campos de quiz nao podem sobrescrever automaticamente `investor_profile`.

## Compatibilidade e migracao
1. Manter compatibilidade com `monthly_income` durante janela de transicao.
2. Definir estrategia de mapeamento (`monthly_income` -> `monthly_income_net`) sem quebra.
3. Atualizar schemas e presenters REST/GraphQL em conjunto para evitar drift de contrato.

## Riscos tecnicos
1. Drift de contrato entre REST e GraphQL.
2. Quebra de clientes existentes ao introduzir `monthly_income_net`.
3. Inconsistencia semantica entre perfil declarado e perfil sugerido.
4. Ambiguidade de UX se nao houver explicacao clara no frontend.

## Debitos tecnicos relacionados
1. Centralizar validacao de perfil em camada de aplicacao unica.
2. Garantir testes de regressao para payload legado e payload novo.
3. Manter `schema.graphql` sincronizado com schema runtime.

## Rastreabilidade no backlog
1. `B8`: campos minimos de perfil V1 + retrocompatibilidade.
2. `B9`: fluxo auto declarado com validacao de enum.
3. `B10`: questionario indicativo (5-10 perguntas).
4. `B11`: persistencia do resultado sugerido e versao de taxonomia.

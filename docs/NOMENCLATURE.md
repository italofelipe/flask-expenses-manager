# Nomenclature Guide (Domain Language)

Este documento evita ambiguidade entre termos legados e atuais.

## Termos oficiais
- `wallet`: agregado de carteira do usuário.
- `investment`: item/posição da carteira identificado por `investment_id`.
- `investment operation`: operação da posição (`buy`/`sell`) com data, preço, quantidade e taxas.
- `ticker`: símbolo de mercado para ativos negociáveis e consultas de preço.

## Regras de nomenclatura na API
- REST usa o prefixo `/wallet` para operações de carteira e investimentos.
- Identificador de item da carteira permanece `investment_id` por consistência semântica.
- Não expor endpoint REST `/ticker`; ticker pertence ao domínio de carteira/GraphQL.

## Regra de documentação
- Ao escrever novas docs, evitar misturar termos como se fossem equivalentes absolutos.
- Sempre explicitar o contexto:
  - carteira agregada: `wallet`
  - posição específica: `investment`
  - símbolo de mercado: `ticker`

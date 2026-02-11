# TASKS - Central de TODOs e Progresso

Ultima atualizacao: 2026-02-11

## Regras de uso deste arquivo
- Este arquivo centraliza TODOs de produto, engenharia e qualidade.
- Cada tarefa deve manter: `Status`, `Progresso`, `Risco`, `Commit` (quando aplicavel).
- Ao concluir uma tarefa, atualizar `Status=Done`, `Progresso=100%` e preencher `Commit`.

## Legenda de status
- `Todo`: ainda nao iniciada.
- `In Progress`: em andamento.
- `Blocked`: bloqueada por dependencia/decisao.
- `Done`: concluida e validada.

## Backlog central

| ID | Area | Tarefa | Status | Progresso | Risco | Commit | Ultima atualizacao |
|---|---|---|---|---:|---|---|---|
| A1 | API Base | Padronizar contrato de resposta (sucesso/erro) em todos os endpoints | In Progress | 70% | Medio: domínios futuros ainda nao padronizados | da2ff52, f3ef3c0 | 2026-02-09 |
| A2 | API Base | Revisar OpenAPI/Swagger para refletir rotas reais | Todo | 35% | Medio: divergencia gera erro de consumo em cliente | da19f35, f3ef3c0 | 2026-02-09 |
| A3 | API Base | Remover inconsistencias de nomenclatura (ticker/wallet/investment) | Todo | 20% | Medio: confusao entre recurso legado e atual |  | 2026-02-09 |
| A4 | API Base | Definir estrategia unica de validacao (Marshmallow vs Pydantic gradual) | Todo | 0% | Baixo: decisao arquitetural pendente |  | 2026-02-09 |
| B1 | Usuario | Criar endpoint dedicado para leitura de perfil (payload reduzido) | Todo | 0% | Baixo |  | 2026-02-09 |
| B2 | Usuario | Reforcar validacoes de coerencia financeira no perfil | Todo | 0% | Medio: dados inconsistentes impactam metas |  | 2026-02-09 |
| B3 | Usuario | Adicionar auditoria de atualizacao de perfil | Todo | 0% | Medio: rastreabilidade insuficiente |  | 2026-02-09 |
| C1 | Transacoes | Corrigir listagem de transacoes com filtros/paginacao reais no banco | Done | 100% | Baixo | 497f901 | 2026-02-09 |
| C2 | Transacoes | Regras fortes de recorrencia + geracao automatica idempotente | Done | 100% | Baixo | f3ef3c0 | 2026-02-09 |
| C3 | Transacoes | Consolidar regras de parcelamento (soma exata e arredondamento final) | Done | 100% | Baixo | 497f901 | 2026-02-09 |
| C4 | Transacoes | Criar endpoint de dashboard mensal (receitas, despesas, saldo, categorias) | Done | 100% | Baixo | pending-commit | 2026-02-09 |
| C5 | Transacoes | Endpoint de despesas por periodo com paginacao/ordenacao/metricas | Done | 100% | Baixo | f3ef3c0 | 2026-02-09 |
| D1 | Investimentos | Entidade de operacoes (`buy`/`sell`) com data, preco, quantidade, taxas | Done | 100% | Baixo | 94c94db, pending-commit | 2026-02-09 |
| D2 | Investimentos | Calculo de custo medio por ativo e posicao atual | Done | 100% | Medio: requer evolucao para casos avancados (venda acima da posicao/short) | pending-commit | 2026-02-09 |
| D3 | Investimentos | Calculo de quanto investiu no dia por data de operacao | Done | 100% | Medio: cobertura de regra baseline, faltam cenarios avancados (ex.: timezone/mercado) | pending-commit | 2026-02-09 |
| D4 | Investimentos | Calculo de valor atual por ativo e consolidado (BRAPI + fallback) | Done | 100% | Baixo | pending-commit | 2026-02-09 |
| D5 | Investimentos | Calculo de P/L absoluto e percentual por ativo e consolidado | Done | 100% | Baixo | pending-commit | 2026-02-09 |
| D6 | Investimentos | Resiliencia BRAPI (timeout, retry, tratamento de erro, cache curto) | Done | 100% | Medio: cache em memória por processo (sem cache distribuído) | pending-commit | 2026-02-09 |
| D7 | Investimentos | Endpoint de evolucao historica da carteira por periodo | Done | 100% | Medio: preços históricos dependem de disponibilidade do provider externo | pending-commit | 2026-02-09 |
| D8 | Investimentos | Expandir carteira para acoes, FII, CDB, CDI etc. + BRAPI + ganho/perda temporal | Done | 100% | Medio: projeção de renda fixa usa taxa informada pelo usuário (sem curva externa) | pending-commit | 2026-02-09 |
| E1 | Metas | Criar model `Goal` | Todo | 0% | Medio |  | 2026-02-09 |
| E2 | Metas | Criar CRUD de metas (`/goals`) | Todo | 0% | Medio |  | 2026-02-09 |
| E3 | Metas | Servico de planejamento (curto/medio/longo prazo) | Todo | 0% | Alto: regra de negocio central |  | 2026-02-09 |
| E4 | Metas | Calcular plano por renda, gastos e capacidade de aporte | Todo | 0% | Alto |  | 2026-02-09 |
| E5 | Metas | Expor recomendacoes acionaveis com data estimada | Todo | 0% | Medio |  | 2026-02-09 |
| E6 | Metas | Endpoint de simulacao sem persistencia (what-if) | Todo | 0% | Medio |  | 2026-02-09 |
| F1 | Auxiliares | CRUD de `Tag` | Todo | 0% | Baixo |  | 2026-02-09 |
| F2 | Auxiliares | CRUD de `Account` | Todo | 0% | Baixo |  | 2026-02-09 |
| F3 | Auxiliares | CRUD de `CreditCard` | Todo | 0% | Baixo |  | 2026-02-09 |
| F4 | Auxiliares | Integrar `Tag/Account/CreditCard` com transacoes e validacoes | Todo | 0% | Medio |  | 2026-02-09 |
| G1 | Qualidade | Completar suite de testes por dominio | In Progress | 75% | Medio: lacunas em cenarios complexos | 497f901, f3ef3c0 | 2026-02-09 |
| G2 | Qualidade | Testes de integracao BRAPI com mocks/fakes | In Progress | 60% | Medio: falta cenário E2E com falha real do provider | 497f901, pending-commit | 2026-02-09 |
| G3 | Qualidade | Enforce de cobertura minima no CI | In Progress | 80% | Baixo | 497f901, 7f0ac66 | 2026-02-09 |
| G4 | Qualidade | Pipeline CI para lint, type-check, testes e gates de qualidade | In Progress | 85% | Baixo | 842a656, 7f0ac66 | 2026-02-09 |
| G5 | Qualidade | Seed de dados para ambiente local | Todo | 0% | Baixo |  | 2026-02-09 |
| H1 | Arquitetura | Adicionar suporte a GraphQL | In Progress | 65% | Alto: impacto transversal na API | ba1f238, e12bf21 | 2026-02-09 |
| H2 | Seguranca | Implementar rate limit por rota/usuario/IP | In Progress | 60% | Medio: baseline entregue, falta storage distribuído e tuning por ambiente | pending-commit | 2026-02-11 |
| H3 | Seguranca | Hardening de validacao/sanitizacao/authz/headers/auditoria | In Progress | 15% | Alto: mapeamento consolidado, implementação pendente | pending-commit | 2026-02-11 |
| I1 | Deploy Cloud | Fechar arquitetura alvo AWS/Azure para budget de R$40/mês e registrar decisão | Done | 100% | Medio: custos podem variar por região/câmbio | pending-commit | 2026-02-09 |
| I2 | Deploy Cloud | Preparar Docker para produção (Dockerfile prod, gunicorn, healthcheck) | Done | 100% | Medio: diferenças dev/prod podem quebrar startup | pending-commit | 2026-02-09 |
| I3 | Deploy AWS | Provisionar ambiente base na AWS (VPC, SG, instância Lightsail/EC2) | In Progress | 70% | Medio: hardening inicial de rede e portas | pending-commit | 2026-02-10 |
| I4 | Deploy AWS | Provisionar banco no plano A (PostgreSQL em container na própria VM) | Todo | 0% | Medio: risco operacional sem HA gerenciado |  | 2026-02-09 |
| I5 | Deploy AWS | Provisionar banco no plano B (RDS PostgreSQL) e documentar critérios de fallback | Todo | 0% | Alto: custo pode estourar orçamento |  | 2026-02-09 |
| I6 | Deploy AWS | Configurar deploy automático (GitHub Actions -> servidor) com rollback básico | Todo | 0% | Medio: risco de indisponibilidade durante release |  | 2026-02-09 |
| I7 | Deploy AWS | Observabilidade mínima (logs centralizados, métricas, alertas básicos) | Todo | 0% | Medio: sem observabilidade o suporte fica reativo |  | 2026-02-09 |
| I8 | Deploy AWS | Hardening de produção (secrets, TLS, firewall, least-privilege IAM) | In Progress | 40% | Alto: risco de segurança e vazamento | pending-commit | 2026-02-10 |
| I9 | Deploy AWS | Runbook de operação (backup, restore, rotação de credenciais, incidentes) | Todo | 0% | Medio: continuidade operacional insuficiente |  | 2026-02-09 |
| I10 | Deploy Cloud | Primeiro deploy em produção (MVP) imediatamente após fechar Bloco D | Todo | 0% | Alto: dependência de D5-D8 e pipeline estável |  | 2026-02-09 |
| I11 | Nginx/TLS | Configurar Nginx em HTTP com suporte a ACME challenge (`/.well-known/acme-challenge`) | Done | 100% | Baixo | pending-commit | 2026-02-10 |
| I12 | Nginx/TLS | Configurar compose prod para `443`, volumes de certbot e certificados | Done | 100% | Medio: erro de volume/mount pode invalidar proxy | pending-commit | 2026-02-10 |
| I13 | Nginx/TLS | Provisionar emissão de certificado Let's Encrypt para `api.auraxis.com.br` | In Progress | 60% | Medio: depende de DNS + portas 80/443 + rate limit ACME | pending-commit | 2026-02-10 |
| I14 | Nginx/TLS | Ativar config TLS no Nginx (redirect 80->443 + headers de segurança) | Todo | 0% | Medio: depende de I13 |  | 2026-02-10 |
| I15 | Nginx/TLS | Configurar renovação automática de certificado e validações pós-renovação | Todo | 0% | Medio: risco de expiração sem automação |  | 2026-02-10 |
| I16 | Nginx/TLS | Checklist de validação local/AWS (DNS, SG, health, curl, logs, rollback) | In Progress | 65% | Baixo | pending-commit | 2026-02-10 |
| R1 | Rebranding | Mapear todas ocorrências de nomenclatura legada do projeto e registrar plano de substituição para `auraxis` | Done | 100% | Baixo: mapeamento concluído em arquivos versionados | pending-commit | 2026-02-10 |
| R2 | Rebranding | Substituir ocorrências versionadas de nomenclatura legada por `auraxis` (sem quebrar integrações externas) | Done | 100% | Medio: integrações externas podem manter identificador legado temporário | pending-commit | 2026-02-10 |
| S1 | AWS Security | Restringir acesso e hardening de instâncias EC2 (SG, NACL, IMDSv2, SSH policy, patching baseline) | Todo | 0% | Alto: superfície de ataque de infraestrutura |  | 2026-02-10 |
| S2 | App Security | Implementar segurança de endpoints (rate-limit, validação/sanitização de request/response, headers e authz por recurso) | In Progress | 50% | Alto: limites de consumo ativos, pendente sanitização central e matriz de authz | pending-commit | 2026-02-11 |
| S3 | App Security | Executar checklist OWASP no sistema (ASVS/API Top 10), corrigir gaps e formalizar evidências | In Progress | 85% | Alto: risco de vulnerabilidades críticas não mapeadas | pending-commit | 2026-02-11 |
| S4-01 | App Security | Remover vazamento de exceções em respostas (`str(e)`, `traceback`) e adotar erros genéricos com correlação | Todo | 0% | Alto: exposição de detalhes internos |  | 2026-02-11 |
| S4-02 | App Security | Substituir `print` por logging estruturado com níveis e política de redaction | Todo | 0% | Medio: vazamento acidental e baixa auditabilidade |  | 2026-02-11 |
| S4-03 | App Security | Padronizar callbacks JWT e middleware para contrato de erro único (v1/v2) e status codes consistentes | Todo | 0% | Medio: comportamento inconsistente em auth |  | 2026-02-11 |
| S4-04 | App Security | Implementar limite global de tamanho de request body para endpoints REST | Todo | 0% | Alto: risco de DoS por payload grande |  | 2026-02-11 |
| S4-05 | App Security | Endurecer paginação e limites de resposta (ex.: `limit` em `/user/me`, `per_page<=0` em histórico) | Todo | 0% | Alto: risco de consumo excessivo de recursos |  | 2026-02-11 |
| S4-06 | App Security | Implementar sanitização/normalização central para campos textuais de entrada | Todo | 0% | Alto: risco de payload malicioso em logs/consumidores |  | 2026-02-11 |
| S4-07 | App Security | Aplicar política GraphQL deny-by-default para operações privadas e cobertura automática de autorização por resolver | Todo | 0% | Alto: risco de exposição caso resolver novo esqueça auth |  | 2026-02-11 |
| S4-08 | App Security | Tornar introspecção GraphQL configurável por ambiente (desabilitar em PROD por padrão) | Todo | 0% | Medio: ampliação de superfície de reconhecimento |  | 2026-02-11 |
| S4-09 | App Security | Endurecer consumo BRAPI (allowlist de ticker, validação estrita de resposta, fallback defensivo) | Todo | 0% | Medio: entrada externa não confiável |  | 2026-02-11 |
| S4-10 | App Security | Evoluir rate-limit e revogação de token para storage distribuído (Redis) | Todo | 0% | Alto: controle atual in-memory não escala em múltiplas instâncias |  | 2026-02-11 |
| S4-11 | App Security | Remover fallback de secrets fracos em runtime não-dev e falhar startup sem segredos fortes | Todo | 0% | Alto: risco de configuração insegura |  | 2026-02-11 |
| S4-12 | App Security | Definir política CORS estrita por ambiente (origins permitidas, métodos, headers) | Todo | 0% | Medio: exposição indevida via browser clients |  | 2026-02-11 |
| S4-13 | App Security | Implementar trilha de auditoria para ações sensíveis (login, perfil, transações, carteira) | Todo | 0% | Medio: baixa rastreabilidade de incidentes |  | 2026-02-11 |
| S4-14 | App Security | Revisar/remover código legado não registrado (`ticker_controller`) e alinhar superfície real de API | Todo | 0% | Baixo: risco de dívida técnica e confusão operacional |  | 2026-02-11 |
| S4-15 | App Security | Formalizar threat model (STRIDE + abuse cases) e critérios de aceite por risco | Todo | 0% | Medio: decisões de segurança sem baseline formal |  | 2026-02-11 |
| S4-16 | App Security | Adicionar scan de vulnerabilidades de dependências no CI (`pip-audit`/equivalente) | Todo | 0% | Medio: risco de CVEs não detectadas cedo |  | 2026-02-11 |
| X1 | Tech Debt | Remover/atualizar TODO desatualizado sobre enums em transacoes | Todo | 0% | Baixo: clareza de manutencao |  | 2026-02-09 |

## Registro de progresso recente

| Data | Item | Atualizacao | Commit |
|---|---|---|---|
| 2026-02-09 | C2 | Job de recorrencia + servico idempotente para gerar ocorrencias | f3ef3c0 |
| 2026-02-09 | C5 | Endpoint `GET /transactions/expenses` com filtros de periodo, paginacao, ordenacao e metricas | f3ef3c0 |
| 2026-02-09 | C4 | Endpoint `GET /transactions/dashboard` com totais, contagens e top categorias no contrato legado/v2 | pending-commit |
| 2026-02-09 | C4/G1 | Refatoracao com `TransactionAnalyticsService` + suite validada sem regressao | pending-commit |
| 2026-02-09 | G4 | Correcao de lint local (`flake8`/`pyflakes`) com pin de compatibilidade no ambiente dev | pending-commit |
| 2026-02-09 | G4 | Pipeline CI com gate de qualidade/Sonar e validacoes locais | 7f0ac66 |
| 2026-02-09 | H1 (fase 1) | Base GraphQL criada com endpoint `/graphql` + queries/mutations iniciais por controller | pending-commit |
| 2026-02-09 | H1/G1 | Refatoracao interna do schema GraphQL para reduzir duplicacao/complexidade sem alterar regras de negocio | pending-commit |
| 2026-02-09 | D1 | Modelo e endpoints REST iniciais para operacoes de investimento (`/wallet/{investment_id}/operations`) + testes | pending-commit |
| 2026-02-09 | D1/H1 | Operacoes de investimento com domínio compartilhado REST + GraphQL (create/list/update/delete/summary) | pending-commit |
| 2026-02-09 | D2/H1 | Posicao e custo medio por investimento no dominio compartilhado + REST (`/operations/position`) + GraphQL (`investmentPosition`) | pending-commit |
| 2026-02-09 | D3/H1 | Valor investido por data com domínio compartilhado + REST (`/operations/invested-amount`) + GraphQL (`investmentInvestedAmount`) | pending-commit |
| 2026-02-09 | D4/H1 | Valuation atual por ativo e consolidado com domínio compartilhado + REST (`/valuation`) + GraphQL (`investmentValuation`, `portfolioValuation`) | pending-commit |
| 2026-02-09 | D5/H1 | P/L absoluto/percentual por ativo e consolidado no domínio de valuation compartilhado REST + GraphQL | pending-commit |
| 2026-02-09 | D6/G2 | Resiliência BRAPI com timeout/retry/cache curto + testes unitários de cache/retry/timeout | pending-commit |
| 2026-02-09 | D7/H1 | Histórico da carteira por período (REST + GraphQL) com série diária de investido líquido acumulado | pending-commit |
| 2026-02-09 | D7/H1 | Histórico evoluído com valor estimado e P/L por dia (REST + GraphQL) | pending-commit |
| 2026-02-09 | D8/H1 | Suporte a classes de ativos (stock/fii/etf/bdr/crypto/cdb/cdi/lci/lca/tesouro/fund/custom) + projeção de renda fixa | pending-commit |
| 2026-02-09 | I1 | Backlog e análise de deploy AWS/Azure com custos, plano A/B e decisão inicial | pending-commit |
| 2026-02-09 | I2 | Perfis DEV/PROD no Docker com compose separado, Dockerfile de produção, entrypoint com migração e proxy Nginx | pending-commit |
| 2026-02-10 | I3/I11-I13/I16 | DNS e AWS em andamento + base Nginx/TLS implementada no repo (ACME challenge, compose com 443/certbot, runbook TLS) | pending-commit |
| 2026-02-10 | R1/R2 | Rebranding concluído no repositório versionado: nomenclatura migrada para `auraxis` e pendências externas mapeadas | pending-commit |
| 2026-02-10 | S3 | Baseline OWASP iniciado com diagnóstico API Top 10/ASVS e backlog de segurança para execução S3 -> S2 -> S1 | pending-commit |
| 2026-02-10 | S3.1 | Inventário de superfície de ataque REST/GraphQL concluído com matriz OWASP e handoff para S2/S1 (`docs/OWASP_S3_INVENTORY.md`) | pending-commit |
| 2026-02-10 | S3.2 | Checklist OWASP/ASVS iniciado com status por controle, evidências e ações (`docs/OWASP_S3_CHECKLIST.md`) | pending-commit |
| 2026-02-10 | S3.3 | Script de evidências OWASP (`scripts/security_evidence_check.sh`) integrado ao CI com artifact (`security-evidence`) | pending-commit |
| 2026-02-11 | S3.4 | Plano priorizado de remediação OWASP (P0/P1/P2) mapeado para S2/S1 (`docs/OWASP_S3_REMEDIATION_PLAN.md`) | pending-commit |
| 2026-02-11 | S2.1/H2 | Baseline de rate-limit para REST+GraphQL implementado (`app/middleware/rate_limit.py`) com testes dedicados (`tests/test_rate_limit.py`) e atualização do checklist OWASP | pending-commit |
| 2026-02-11 | S2.2/H1-HARDENING | Limites de transporte GraphQL implementados (tamanho/profundidade/complexidade/operações) com política configurável (`app/graphql/security.py`) e testes (`tests/test_graphql_security.py`) | pending-commit |
| 2026-02-11 | S3.5/H3 | Revisão de fragilidades de segurança na aplicação e mapeamento em backlog de remediação (`S4-01..S4-16`) | pending-commit |
| 2026-02-09 | D (observacao) | Restaurados arquivos deletados acidentalmente: ticker/carteira | n/a |

## Proxima prioridade sugerida
- S2 (P0): executar `S4-01`, `S4-04`, `S4-05`, `S4-06` e `S4-10` como pacote crítico de segurança.

## Mapeamento Rebranding (nomenclatura legada -> `auraxis`)

Escopo do mapeamento em 2026-02-10 (com busca por identificadores legados e variações):
- Versionado:
  - documentação operacional atualizada para path padrão `/opt/auraxis`.
- Não versionado / ambiente local:
  - `.env`: chave de projeto SonarCloud com identificador legado (depende de migração no serviço externo).
  - `.env`: nome de key pair AWS legado (renomeável sem impacto funcional obrigatório).
  - `.scannerwork/report-task.txt`: referências internas de scan local (artefato temporário, não versionado).

Pendências de substituição controlada:
- Ajustar nomes externos com potencial impacto operacional antes da troca definitiva:
  - projeto/chave no SonarCloud;
  - nomes de key pair/recursos AWS já provisionados (somente nomenclatura, sem impacto funcional direto).

## Plano GraphQL por Controller

| ID | Controller | Escopo GraphQL | Status | Progresso | Risco | Commit |
|---|---|---|---|---:|---|---|
| H1-AUTH | `auth_controller` | `registerUser`, `login`, `logout` | In Progress | 75% | Medio: manter mesma politica de token do REST | ba1f238 |
| H1-USER | `user_controller` | `me`, `updateUserProfile` | In Progress | 70% | Medio: consistencia das validacoes de perfil | ba1f238 |
| H1-TRANSACTIONS | `transaction_controller` | `transactions`, `transactionSummary`, `transactionDashboard`, `createTransaction`, `deleteTransaction` | In Progress | 60% | Alto: nao divergir das regras de recorrencia/parcelamento | ba1f238 |
| H1-WALLET | `wallet_controller` | `walletEntries`, `walletHistory`, `addWalletEntry`, `updateWalletEntry`, `deleteWalletEntry` | In Progress | 60% | Alto: consistencia de calculo e historico | ba1f238 |
| H1-TICKER | `ticker_controller` | `tickers`, `addTicker`, `deleteTicker` | In Progress | 75% | Baixo | ba1f238 |
| H1-HARDENING | `graphql_controller` | autorização fina por operação, limites de complexidade/profundidade, observabilidade | In Progress | 45% | Alto: custo de query baseline ativo, faltam observabilidade e custo por domínio | pending-commit |

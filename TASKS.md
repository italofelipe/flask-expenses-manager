# TASKS - Central de TODOs e Progresso

Ultima atualizacao: 2026-02-13

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
| A1 | API Base | Padronizar contrato de resposta (sucesso/erro) em todos os endpoints | Done | 100% | Baixo: padronização v1/v2 aplicada em controllers, rate-limit e fluxo JWT legado/callbacks | da2ff52, f3ef3c0, pending-commit | 2026-02-12 |
| A2 | API Base | Revisar OpenAPI/Swagger para refletir rotas reais | Todo | 35% | Medio: divergencia gera erro de consumo em cliente | da19f35, f3ef3c0 | 2026-02-09 |
| A3 | API Base | Remover inconsistencias de nomenclatura (ticker/wallet/investment) | Todo | 20% | Medio: confusao entre recurso legado e atual |  | 2026-02-09 |
| A4 | API Base | Definir estrategia unica de validacao (Marshmallow vs Pydantic gradual) | Todo | 0% | Baixo: decisao arquitetural pendente |  | 2026-02-09 |
| A5 | API Base | Consolidar utilitarios de controller dentro dos pacotes de dominio com facade legada para retrocompatibilidade | Done | 100% | Baixo | pending-commit | 2026-02-12 |
| A6 | API Base | Modularizar login guard em componentes coesos (`context`, `settings`, `backend`, `service`) preservando retrocompatibilidade publica | Done | 100% | Baixo: arquitetura simplificada sem mudanca de regra de bloqueio/cooldown | pending-commit | 2026-02-12 |
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
| G1 | Qualidade | Completar suite de testes por dominio | In Progress | 80% | Medio: lacunas em cenarios complexos | 497f901, f3ef3c0, pending-commit | 2026-02-12 |
| G2 | Qualidade | Testes de integracao BRAPI com mocks/fakes | In Progress | 60% | Medio: falta cenário E2E com falha real do provider | 497f901, pending-commit | 2026-02-09 |
| G3 | Qualidade | Enforce de cobertura minima no CI | In Progress | 80% | Baixo | 497f901, 7f0ac66 | 2026-02-09 |
| G4 | Qualidade | Pipeline CI para lint, type-check, testes e gates de qualidade | In Progress | 92% | Baixo | 842a656, 7f0ac66 | 2026-02-11 |
| G5 | Qualidade | Seed de dados para ambiente local | Todo | 0% | Baixo |  | 2026-02-09 |
| G6 | CI/Security | Reforcar pre-commit com secret scanning confiável (Gitleaks), Bandit e detecção de private keys | In Progress | 80% | Médio: risco de falso positivo em segredos de teste |  | 2026-02-11 |
| G7 | CI/Resilience | Adicionar teste de confiabilidade de contrato OpenAPI com Schemathesis | In Progress | 75% | Médio: flakiness se escopo de fuzzing crescer sem calibração |  | 2026-02-11 |
| G8 | CI/Quality | Adicionar gate de mutation testing (Cosmic Ray) para módulos críticos | Done | 100% | Médio: custo de execução controlado por escopo e filtro de operadores | pending-commit | 2026-02-11 |
| G9 | CI/Security | Integrar Snyk (dependências e container) com gate condicional por `SNYK_ENABLED` | In Progress | 85% | Baixo: actions fixadas por SHA imutável; pendente somente calibração fina de baseline/ruleset |  | 2026-02-11 |
| G10 | CI/Security | Integrar scan de imagem/container com Trivy em todo PR/push | Done | 100% | Baixo: pipeline validado com imagem hardenizada e scan HIGH/CRITICAL limpo no baseline atual | pending-commit | 2026-02-11 |
| G11 | CI/Governance | Formalizar política de branch protection + required checks + push protection no GitHub | Todo | 0% | Alto: sem enforcement central, gates podem ser ignorados |  | 2026-02-11 |
| G12 | CI/Quality | Garantir paridade local do job `Quality` (script Python 3.11 + hook mypy alinhado ao CI) | Done | 100% | Baixo | pending-commit | 2026-02-11 |
| G13 | CI/Quality | Adicionar matrix de tipagem (`mypy`) em Python 3.11 e 3.13 para reduzir regressão entre ambientes | Done | 100% | Baixo: job dedicado `mypy-matrix` cobre 3.11/3.13 em paralelo | pending-commit | 2026-02-12 |
| G14 | CI/Quality | Avaliar lock/constraints de dependências de tooling (lint/type/security) para builds determinísticos | Done | 100% | Baixo: `pip-audit` e stubs de tipagem fixados em versão e CI sem instalação avulsa não determinística | pending-commit | 2026-02-12 |
| G15 | CI/Review | Integrar Cursor Bugbot como camada de revisão automática de PR + calibrar obrigatoriedade no ruleset | In Progress | 35% | Médio: risco de falso positivo se exigido sem período de calibração |  | 2026-02-11 |
| G16 | Quality | Reduzir warnings globais de deprecacao (Marshmallow v4, apispec schema naming, warnings de terceiros) com plano faseado | In Progress | 92% | Baixo: warnings do pipeline local foram saneados; remanescente depende de upgrade estruturado de bibliotecas terceiras | pending-commit | 2026-02-12 |
| H1 | Arquitetura | Adicionar suporte a GraphQL | In Progress | 65% | Alto: impacto transversal na API | ba1f238, e12bf21 | 2026-02-09 |
| H2 | Seguranca | Implementar rate limit por rota/usuario/IP | Done | 100% | Baixo: rate-limit por domínio com backend distribuído, fail-closed e observabilidade básica | pending-commit | 2026-02-11 |
| H3 | Seguranca | Hardening de validacao/sanitizacao/authz/headers/auditoria | Done | 100% | Médio: baseline aplicado; evolução contínua segue para monitoramento centralizado e infraestrutura S1 | pending-commit | 2026-02-11 |
| I1 | Deploy Cloud | Fechar arquitetura alvo AWS/Azure para budget de R$40/mês e registrar decisão | Done | 100% | Medio: custos podem variar por região/câmbio | pending-commit | 2026-02-09 |
| I2 | Deploy Cloud | Preparar Docker para produção (Dockerfile prod, gunicorn, healthcheck) | Done | 100% | Medio: diferenças dev/prod podem quebrar startup | pending-commit | 2026-02-09 |
| I3 | Deploy AWS | Provisionar ambiente base na AWS (VPC, SG, instância Lightsail/EC2) | Done | 100% | Medio: manter hardening evolutivo em I8 e runbook em I9 | pending-commit | 2026-02-13 |
| I4 | Deploy AWS | Provisionar banco no plano A (PostgreSQL em container na própria VM) | Done | 100% | Medio: risco operacional sem HA gerenciado (mitigado parcialmente com backups S3 e restore drill) | pending-commit | 2026-02-13 |
| I5 | Deploy AWS | Provisionar banco no plano B (RDS PostgreSQL) e documentar critérios de fallback | Done | 100% | Baixo: RDS nao foi provisionado por budget; guardrails (Budgets/Anomaly) aplicados e plano B documentado | 877c0cc | 2026-02-14 |
| I6 | Deploy AWS | Configurar deploy automático (GitHub Actions -> servidor) com rollback básico | Done | 100% | Medio: deploy DEV automatico (push master) e deploy PROD manual (workflow_dispatch) via OIDC+SSM; requer env approval para PROD no GitHub | pending-commit | 2026-02-14 |
| I7 | Deploy AWS | Observabilidade mínima (logs centralizados, métricas, alertas básicos) | Done | 100% | Médio: DEV canary via HTTP:80 (sem TLS), PROD via HTTPS:443; logs em CloudWatch Logs confirmados para web/nginx/db/redis | pending-commit | 2026-02-13 |
| I8 | Deploy AWS | Hardening de produção (secrets, TLS, firewall, least-privilege IAM) | In Progress | 65% | Medio: IAM audit indica role não-broad (SSM + CloudWatchAgent + inline S3 backups); pendente runbook operacional (I9) e revisão de políticas (remover excesso se houver) | 5825206, 2b2459c, c76957f | 2026-02-13 |
| I9 | Deploy AWS | Runbook de operação (backup, restore, rotação de credenciais, incidentes) | Done | 100% | Baixo: runbook consolidado em docs + scripts de validacao/operacao | 877c0cc | 2026-02-14 |
| I10 | Deploy Cloud | Primeiro deploy em produção (MVP) imediatamente após fechar Bloco D | Done | 100% | Medio: operação em VM única (sem HA) exige runbook e rotinas de backup/restore (I9/S1-03) | pending-commit | 2026-02-13 |
| I11 | Nginx/TLS | Configurar Nginx em HTTP com suporte a ACME challenge (`/.well-known/acme-challenge`) | Done | 100% | Baixo | pending-commit | 2026-02-10 |
| I12 | Nginx/TLS | Configurar compose prod para `443`, volumes de certbot e certificados | Done | 100% | Medio: erro de volume/mount pode invalidar proxy | pending-commit | 2026-02-10 |
| I13 | Nginx/TLS | Provisionar emissão de certificado Let's Encrypt para `api.auraxis.com.br` | Done | 100% | Medio: manter validações pós-deploy e automação de renovação (I15) | pending-commit | 2026-02-13 |
| I14 | Nginx/TLS | Ativar config TLS no Nginx (redirect 80->443 + headers de segurança) | Done | 100% | Baixo: TLS ativo em PROD com headers de segurança; DEV segue HTTP por enquanto | pending-commit | 2026-02-13 |
| I15 | Nginx/TLS | Configurar renovação automática de certificado e validações pós-renovação | Done | 100% | Baixo: timer systemd instalado em PROD e validação dry-run executada via SSM | 575dcea, 3137cd9 | 2026-02-13 |
| I16 | Nginx/TLS | Checklist de validação local/AWS (DNS, SG, health, curl, logs, rollback) | Done | 100% | Baixo: checklist automatizado em `scripts/aws_validate_i16.py` e validado contra DEV/PROD | 2af0a95 | 2026-02-13 |
| R1 | Rebranding | Mapear todas ocorrências de nomenclatura legada do projeto e registrar plano de substituição para `auraxis` | Done | 100% | Baixo: mapeamento concluído em arquivos versionados | pending-commit | 2026-02-10 |
| R2 | Rebranding | Substituir ocorrências versionadas de nomenclatura legada por `auraxis` (sem quebrar integrações externas) | Done | 100% | Medio: integrações externas podem manter identificador legado temporário | pending-commit | 2026-02-10 |
| S1 | AWS Security | Restringir acesso e hardening de instâncias EC2 (SG, NACL, IMDSv2, SSH policy, patching baseline) | Done | 100% | Baixo: baseline aplicado e validado; pendência remanescente é apenas runbook operacional (I9) e ajustes contínuos | pending-commit | 2026-02-13 |
| S1-03 | AWS Security | Backups do PostgreSQL para S3 (bucket hardenizado + IAM least-privilege + lifecycle + versioning + restore drill + agendamento via SSM MW) | Done | 100% | Médio: ainda falta runbook de restore completo e teste de RTO/RPO com volume real | pending-commit | 2026-02-13 |
| S1-02 | AWS Security | Cleanup pós-migração de EBS: revisar e remover volumes/snapshots antigos (após janela de validação) | Done | 100% | Baixo: volumes e snapshots intermediários removidos após confirmação | pending-commit | 2026-02-12 |
| S2 | App Security | Implementar segurança de endpoints (rate-limit, validação/sanitização de request/response, headers e authz por recurso) | Done | 100% | Médio: baseline completo em aplicação; próximos passos são monitoramento centralizado e hardening de infraestrutura (S1) | pending-commit | 2026-02-11 |
| S3 | App Security | Executar checklist OWASP no sistema (ASVS/API Top 10), corrigir gaps e formalizar evidências | In Progress | 92% | Médio: baseline e remediações de aplicação concluídas; pendências residuais concentram-se em controles de infraestrutura (S1) | pending-commit | 2026-02-11 |
| S4-01 | App Security | Remover vazamento de exceções em respostas (`str(e)`, `traceback`) e adotar erros genéricos com correlação | Done | 100% | Médio: manter revisão contínua em novos endpoints | pending-commit | 2026-02-11 |
| S4-02 | App Security | Substituir `print` por logging estruturado com níveis e política de redaction | Done | 100% | Baixo: runtime HTTP e scripts operacionais migrados para logging estruturado | f2bcda1 | 2026-02-11 |
| S4-03 | App Security | Padronizar callbacks JWT e middleware para contrato de erro único (v1/v2) e status codes consistentes | Done | 100% | Baixo | pending-commit | 2026-02-11 |
| S4-04 | App Security | Implementar limite global de tamanho de request body para endpoints REST | Done | 100% | Baixo: limite parametrizado por ambiente | pending-commit | 2026-02-11 |
| S4-05 | App Security | Endurecer paginação e limites de resposta (ex.: `limit` em `/user/me`, `per_page<=0` em histórico) | Done | 100% | Baixo: limites agora explícitos em REST/GraphQL | pending-commit | 2026-02-11 |
| S4-06 | App Security | Implementar sanitização/normalização central para campos textuais de entrada | Done | 100% | Médio: expandir para todos os schemas legados | pending-commit | 2026-02-11 |
| S4-07 | App Security | Aplicar política GraphQL deny-by-default para operações privadas e cobertura automática de autorização por resolver | Done | 100% | Baixo: transporte GraphQL já bloqueia chamadas privadas sem auth | pending-commit | 2026-02-11 |
| S4-08 | App Security | Tornar introspecção GraphQL configurável por ambiente (desabilitar em PROD por padrão) | Done | 100% | Baixo | pending-commit | 2026-02-11 |
| S4-09 | App Security | Endurecer consumo BRAPI (allowlist de ticker, validação estrita de resposta, fallback defensivo) | Done | 100% | Médio: validação concluída; falta telemetria por códigos de erro de provider (item S4-17) | pending-commit | 2026-02-11 |
| S4-10 | App Security | Evoluir rate-limit e revogação de token para storage distribuído (Redis) | Done | 100% | Baixo: backend distribuído com observabilidade/runbook e helper legado de revogação alinhado ao source-of-truth persistido | pending-commit | 2026-02-11 |
| S4-11 | App Security | Remover fallback de secrets fracos em runtime não-dev e falhar startup sem segredos fortes | Done | 100% | Baixo: bloqueio de startup em runtime inseguro | pending-commit | 2026-02-11 |
| S4-12 | App Security | Definir política CORS estrita por ambiente (origins permitidas, métodos, headers) | Done | 100% | Médio: manter allowlist por ambiente atualizada | pending-commit | 2026-02-11 |
| S4-13 | App Security | Implementar trilha de auditoria para ações sensíveis (login, perfil, transações, carteira) | Done | 100% | Médio: trilha em logs estruturados; faltam retenção/alertas centralizados | pending-commit | 2026-02-11 |
| S4-14 | App Security | Revisar/remover código legado não registrado (`ticker_controller`) e alinhar superfície real de API | Done | 100% | Baixo: controller legado removido e cobertura de não-exposição adicionada | 805c69e | 2026-02-11 |
| S4-15 | App Security | Formalizar threat model (STRIDE + abuse cases) e critérios de aceite por risco | Done | 100% | Baixo: baseline de risco documentada com critérios de aceite e backlog vinculado | pending-commit | 2026-02-11 |
| S4-16 | App Security | Adicionar scan de vulnerabilidades de dependências no CI (`pip-audit`/equivalente) | Done | 100% | Baixo | pending-commit | 2026-02-11 |
| S4-17 | App Security | Adicionar observabilidade de integrações externas (BRAPI): contadores por timeout, payload inválido e erro HTTP | Done | 100% | Médio: métricas em memória entregues; próximo passo é export para backend central (CloudWatch/Prometheus) | f2bcda1 | 2026-02-11 |
| S5-01 | App Security | Eliminar fallback de memória para rate-limit em produção (fail-closed se Redis indisponível) | Done | 100% | Médio: fail-closed implementado; falta monitoramento/alerta de indisponibilidade (S5-02/S5-10) | pending-commit | 2026-02-11 |
| S5-02 | App Security | Implementar trilha de auditoria persistente (DB/CloudWatch) com retenção e busca por `request_id` | Done | 100% | Médio: persistência + retenção + busca por `request_id` concluídas no banco local; integração CloudWatch permanece evolução de observabilidade | pending-commit | 2026-02-11 |
| S5-03 | App Security | Aplicar autorização por recurso no domínio GraphQL (não só no transporte), com testes de ownership | Done | 100% | Baixo: checks explícitos de ownership para `investmentId` no domínio GraphQL + suíte de testes de acesso cruzado | pending-commit | 2026-02-11 |
| S5-04 | App Security | Endurecer CORS/headers por ambiente com validação de configuração no startup | Done | 100% | Baixo: política de CORS validada no startup e headers de segurança centralizados por ambiente | 5aa0d2c | 2026-02-11 |
| S5-05 | App Security | Adotar rotação de secrets + source of truth (AWS SSM/Secrets Manager), removendo `.env` como primário em cloud | Done | 100% | Médio: script e runbook implementados; depende de IAM/SSM em cada ambiente AWS | pending-commit | 2026-02-11 |
| S5-06 | App Security | Fechar lacunas de brute-force/account takeover (lockout progressivo, cooldown e fingerprint de IP/device) | Done | 100% | Médio: política por usuário conhecido + telemetria local concluídas; falta exportador central de alertas (CloudWatch/Prometheus) | pending-commit | 2026-02-11 |
| S5-07 | App Security | Revisar endpoints legados e desativar/feature-flag rotas não suportadas (`ticker_controller`) | Done | 100% | Baixo: superfície legado removida e bloqueada por teste de não exposição | 805c69e | 2026-02-11 |
| S5-08 | App Security | Implementar validação de saída para evitar data leakage (campos sensíveis e debug data) | Done | 100% | Médio: sanitização central reduz leak; manter revisão contínua em novos payloads | 5aa0d2c | 2026-02-11 |
| S5-09 | App Security | Fortalecer proteção de banco de testes/fixtures para evitar conexões abertas e vazamento de estado | Done | 100% | Baixo: fixture isolada por ambiente e teardown forte de engine/sessão/banco temporário | c0f83e2 | 2026-02-11 |
| S5-10 | App Security | Integrar SAST + secret scanning + dependabot com gate no CI (quebra build em severidade alta) | Done | 100% | Médio: gates ativos no CI; branch protection ainda deve exigir checks | c0f83e2 | 2026-02-11 |
| S6-01 | App Security | Corrigir mass-assignment no `PUT /transactions/{id}` com allowlist de campos mutáveis | Done | 100% | Baixo: coberto por validação e testes de regressão | pending-commit | 2026-02-11 |
| S6-02 | App Security | Tornar `user_id` dump-only no schema de transação e bloquear bind de ownership por payload | Done | 100% | Baixo: schema endurecido e teste de payload malicioso adicionado | pending-commit | 2026-02-11 |
| S6-03 | App Security | Validar ownership de `tag_id/account_id/credit_card_id` no REST de transações (create/update) | Done | 100% | Baixo: validação central reaproveitada no REST | pending-commit | 2026-02-11 |
| S6-04 | App Security | Remover vazamento de `str(exc)`/detalhes internos em controllers REST e padronizar erro seguro | Done | 100% | Baixo: mapeador de erro público aplicado em REST/GraphQL para exceções de validação, com fallback seguro para falhas inesperadas | pending-commit | 2026-02-11 |
| S6-05 | App Security | Unificar política de registro REST/GraphQL (mesma validação de senha/email e normalização) | Done | 100% | Baixo: GraphQL passou a usar `UserRegistrationSchema` | pending-commit | 2026-02-11 |
| S6-06 | App Security | Mitigar enumeração de contas em register/login (status e comportamento observável) | Done | 100% | Baixo: defaults seguros em runtime de produção e proteção de timing em login REST/GraphQL | 4ff5265 | 2026-02-12 |
| S6-07 | App Security | Migrar login guard para backend distribuído (Redis) com política de falha explícita | Done | 100% | Baixo: policy explícita exigida em runtime seguro e compose com Redis pronto para rate-limit/login guard | e23b2af | 2026-02-12 |
| S6-08 | App Security | Endurecer defaults de runtime (`DEBUG=False` por padrão seguro e validação de startup) | Done | 100% | Baixo: runtime seguro bloqueia bypass de enforcement de secrets e mantém validação de startup | 5fc1be7 | 2026-02-12 |
| S6-09 | App Security | Retirar sweep de retenção de auditoria do ciclo de request (job agendado/assíncrono) | Done | 100% | Baixo: retenção externalizada via CLI/job e proteção coberta por teste de não execução no request | 208e1d1 | 2026-02-12 |
| S6-10 | App Security | Atualizar dependências com CVE (`Flask`, `marshmallow`) e zerar `pip-audit` runtime | Done | 100% | Baixo: gate validado com `pip-audit` sem vulnerabilidades conhecidas | afc15c7 | 2026-02-11 |
| S6-11 | App Security | Harden Docker de produção (non-root, multi-stage, runtime deps only) | Done | 100% | Baixo: multi-stage + non-root + contexto sem segredos reduziram superfície e removeram CVEs críticos/altos observados | pending-commit | 2026-02-11 |
| S6-12 | App Security | Definir política de exposição de documentação em produção (`/docs`) por ambiente/autenticação | Done | 100% | Baixo: política por ambiente + fail-fast para configuração inválida em runtime seguro | 208e1d1 | 2026-02-12 |
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
| 2026-02-11 | S2.3/S4 | Hardening aplicado: limite global de payload, CORS por ambiente, introspecção GraphQL configurável, sanitização central, paginação endurecida, segredos fortes obrigatórios e scan `pip-audit` no CI + testes de segurança | pending-commit |
| 2026-02-11 | S2.4/S4-07 | GraphQL com política deny-by-default no transporte: operações privadas exigem auth, allowlist pública por ambiente (`registerUser/login`) + testes de contrato | pending-commit |
| 2026-02-11 | S2.5/S4-10 | Rate-limit com backend distribuído opcional (Redis) + fallback automático para memória + testes de backend e documentação de env | pending-commit |
| 2026-02-11 | S2.6/S4-09 | Hardening BRAPI: sanitização/allowlist de ticker e validação estrita de payload de cotação/histórico com fallback seguro + testes | pending-commit |
| 2026-02-11 | S4-13 | Trilha de auditoria adicionada para rotas sensíveis (`/auth`, `/user`, `/transactions`, `/wallet`, `/graphql`) com payload estruturado de request e testes | pending-commit |
| 2026-02-11 | S5-01 | Rate limit em modo fail-closed para backend Redis indisponível (retorno 503), com configuração por ambiente e testes de backend/guard | pending-commit |
| 2026-02-11 | S5-02 (fase 1) | Persistência opcional de auditoria em tabela `audit_events` com flag de ambiente (`AUDIT_PERSISTENCE_ENABLED`) + teste de integração | pending-commit |
| 2026-02-11 | S5-02 (fase 1.1) | Trilha de auditoria endurecida para Sonar: remoção de payload controlado por usuário dos logs e manutenção apenas de metadados seguros + ajuste de teste | pending-commit |
| 2026-02-11 | S5-03 (fase 1) | Autorização por recurso em GraphQL `createTransaction`: valida ownership de `tagId/accountId/creditCardId` com testes negativos de referência cruzada entre usuários | pending-commit |
| 2026-02-11 | S5-06 (fase 1) | Guard de login progressivo (REST + GraphQL): cooldown exponencial por fingerprint `principal+IP+user-agent`, bloqueio `429/GraphQLError` e testes dedicados | pending-commit |
| 2026-02-11 | S4-02 | Migração de scripts operacionais (`init_db`, `generate_recurring_transactions`) para logging estruturado sem `print` | f2bcda1 |
| 2026-02-11 | S4-17 | Observabilidade BRAPI adicionada com contadores (`timeout`, `http_error`, `invalid_payload`) + testes dedicados | f2bcda1 |
| 2026-02-11 | S5-04 | Endurecimento de CORS/headers por ambiente: validação de startup para origins inválidas em produção e middleware de security headers com políticas por env + testes | 5aa0d2c |
| 2026-02-11 | S5-08 | Sanitização central de respostas REST/GraphQL para reduzir data leakage (`INTERNAL_ERROR`, campos sensíveis) + testes de regressão | 5aa0d2c |
| 2026-02-11 | S5-09 | Hardening da suíte de testes: isolamento de env vars por teste + teardown forte de SQLite/engine para evitar conexões abertas e vazamento de estado | c0f83e2 |
| 2026-02-11 | S5-10 | CI de segurança reforçado: Bandit (SAST), Gitleaks (secret scan), Dependency Review gate (high+) e configuração Dependabot | c0f83e2 |
| 2026-02-11 | S4-14/S5-07 | Remoção do `ticker_controller` legado não registrado, atualização de documentação de superfície e teste para garantir que rotas antigas não sejam expostas | 805c69e |
| 2026-02-11 | S4-15 | Threat model STRIDE + abuse cases + critérios de aceite por risco documentados (`docs/THREAT_MODEL_STRIDE.md`) | pending-commit |
| 2026-02-11 | S5-05 | Source of truth de segredos em cloud com script de sync (`scripts/sync_cloud_secrets.py`) + runbook operacional (`docs/CLOUD_SECRETS_RUNBOOK.md`) | pending-commit |
| 2026-02-11 | S4-10 | Rate-limit distribuído finalizado com observabilidade (`rate_limit.*`), logs de backend Redis/fail-closed, runbook operacional (`docs/RATE_LIMIT_REDIS_RUNBOOK.md`) e alinhamento do helper legado de revogação JWT ao `current_jti` persistido | pending-commit |
| 2026-02-11 | S5-02 | Auditoria persistente evoluída com retenção configurável (`AUDIT_RETENTION_*`), índices de consulta, serviço de busca por `request_id`, utilitário operacional (`scripts/manage_audit_events.py`) e runbook (`docs/AUDIT_TRAIL_RUNBOOK.md`) | pending-commit |
| 2026-02-11 | S5-03 | Autorização por recurso reforçada no domínio GraphQL para fluxos por `investmentId` (queries/mutations) com validação explícita de ownership + testes de acesso cruzado | pending-commit |
| 2026-02-11 | S5-06 | Login guard evoluído com política específica para principal conhecido (`LOGIN_GUARD_KNOWN_*`) + métricas de telemetria (`login_guard.*`) e testes de regressão REST/GraphQL | pending-commit |
| 2026-02-11 | S6 | Reavaliação de segurança round 2 concluída com evidências locais atualizadas (`bandit`, `security_evidence_check`, `pip-audit`) e novo backlog de remediação (`S6-01..S6-12`) | n/a |
| 2026-02-11 | S6-01/S6-02/S6-03/S6-04 | Harden transações REST: bloqueio de mass-assignment, `user_id` dump-only, validação de ownership de referências e remoção de detalhes internos de exceção em respostas 500 | pending-commit |
| 2026-02-11 | S6-05 | Registro GraphQL alinhado ao schema de validação REST (`UserRegistrationSchema`) com normalização e política de senha forte | pending-commit |
| 2026-02-11 | G6/G7/G8/G9/G10 | CI/pre-commit reforçados com Gitleaks+Bandit+private-key detection, job Schemathesis, gate Cosmic Ray, Trivy e Snyk condicional | pending-commit |
| 2026-02-11 | G8 | Mutation gate migrado para Cosmic Ray com escopo crítico em CORS (`app/middleware/cors.py`), filtro de operadores ruidosos e threshold de sobrevivência 0% | pending-commit |
| 2026-02-11 | S6-10 | Dependências com CVE atualizadas (`Flask 3.1.1`, `marshmallow 3.26.2`, `Werkzeug 3.1.5`) e validação `pip-audit` limpa | afc15c7 |
| 2026-02-11 | G12 | Correções de tipagem para CI (`mypy`) + alinhamento do hook local para usar ambiente real (`language: system`) + script de paridade local `scripts/run_ci_quality_local.sh` | pending-commit |
| 2026-02-11 | G15 | Cursor Bugbot registrado em documentação de CI/CD como camada complementar de revisão de PR; estratégia de execução local e limitações formalizadas | pending-commit |
| 2026-02-11 | G8/G9 | Hardening de CI: mutation test sem path hardcoded de `.venv` (compatível com runner GitHub) e actions Snyk fixadas por SHA imutável para reduzir risco de supply-chain | pending-commit |
| 2026-02-11 | G10/S6-11 | Hardening de container para Trivy: Dockerfile.prod multi-stage, runtime não-root, atualização de pacotes no estágio final e exclusão de `.env/.pem/.key` no `.dockerignore`; scan local Trivy (HIGH/CRITICAL) limpo | pending-commit |
| 2026-02-11 | H1/Cleanup | Refatoração estrutural de transações e GraphQL: `transaction_controller` quebrado em recursos modulares, OpenAPI extraído, `schema.py` segmentado em `types/query/mutations`; cobertura global mantida em 88% com suíte e hooks verdes | cbcf368 |
| 2026-02-11 | S6-04/H1-Cleanup | Sanitização de erro aplicada aos controllers REST (`user/wallet/transaction reports`) com camada de aplicação (`DTO + interface + mapper`) para validação pública e fallback seguro sem leak; cobertura validada em 88% | pending-commit |
| 2026-02-12 | A5/H1-Cleanup | `graphql_controller_utils` movido para `app/controllers/graphql/utils.py` com facade legada mantida para imports antigos e alinhamento do padrão por domínio | pending-commit |
| 2026-02-12 | A1 | Contrato v1/v2 unificado em helper compartilhado (`app/controllers/response_contract.py`) com classe de erro extensível (`ResponseContractError`) e adoção inicial em auth/user/wallet/transaction | pending-commit |
| 2026-02-12 | A6/S6-07 Prep | Login guard refatorado para arquitetura modular (`login_attempt_guard_context/settings/backend/service`) com dependências explícitas, mantendo API pública e cobertura >= 85% | pending-commit |
| 2026-02-12 | G1/G16 | Suíte estabilizada sem `ResourceWarning` de SQLite e sem `InsecureKeyLengthWarning` em JWT de testes (fixtures e apps de teste endurecidos); backlog de deprecações Marshmallow/apispec formalizado | pending-commit |
| 2026-02-12 | G16 (fase 1) | `auth_schema` migrado para `metadata=` (Marshmallow 4-ready) e `wallet_schema` atualizado para `load_default`; suíte e cobertura >= 85% mantidas | pending-commit |
| 2026-02-12 | G16 (fase 2) | Schemas auxiliares (`account`, `tag`, `credit_card`, `error`, `user_ticker`) migrados para `metadata=` em preparação ao Marshmallow v4; cobertura mantida em 88% | pending-commit |
| 2026-02-12 | G16 (fase 3) | `transaction_schema` e `user_schemas` migrados para `metadata=` e remoção de `Meta.ordered` legado; `mypy` e suíte completa verdes com cobertura global em 88.17% | pending-commit |
| 2026-02-12 | G16 (fase 4) | Endpoints de wallet atualizados de `missing=` para `load_default` no parsing de query (`page/per_page`) para compatibilidade Marshmallow v4; cobertura global mantida em 88.17% | pending-commit |
| 2026-02-12 | G16 (fase 5) | `APISpec` passou a usar `schema_name_resolver` determinístico com sufixo por modificadores de schema (`only/exclude/...`), removendo colisões de componentes OpenAPI e reduzindo warnings da suíte de 160 para 11 | pending-commit |
| 2026-02-12 | G16 (fase 6) | `pytest.ini` atualizado para filtrar apenas deprecações conhecidas de bibliotecas terceiras (`flask-apispec`/`schemathesis`) e manter `DeprecationWarning` do namespace `app.*` em modo `error`; execução completa da suíte ficou limpa (0 warnings exibidos) com cobertura em 88.24% | pending-commit |
| 2026-02-12 | A1 (fechamento) | Helper de contrato extraído para utilitário neutro (`app/utils/api_contract.py`) e aplicado em `response_contract`, `jwt_callbacks`, `rate_limit` e `token_required`; fluxo JWT legado agora responde contrato v2 quando solicitado (sem quebrar v1) | pending-commit |
| 2026-02-12 | G13 | CI ganhou job dedicado `mypy-matrix` em Python 3.11 e 3.13, reduzindo risco de regressão de tipagem entre versões sem alterar os gates existentes de lint/test/security | pending-commit |
| 2026-02-12 | G14 | Tooling CI deterministic: `pip-audit` adicionado com versão fixa em `requirements-dev.txt`, remoção de `pip install` avulso no workflow e stubs (`types-*`) fixados em `requirements.txt` | pending-commit |
| 2026-02-12 | S6-06 | Mitigação de enumeração em autenticação: política padrão em produção agora oculta conflito de registro e desabilita sinal de principal conhecido no login guard; REST/GraphQL passaram a usar verificação de senha com proteção de timing para usuários inexistentes | 4ff5265 |
| 2026-02-12 | S6-07 | Login guard Redis endurecido com política de falha explícita em runtime seguro (`LOGIN_GUARD_FAIL_CLOSED` obrigatório) e compose atualizado com serviço Redis + URLs padrão para login guard/rate limit (dev/prod/local) | e23b2af |
| 2026-02-12 | S6-08 | Startup hardening reforçado: `SECURITY_ENFORCE_STRONG_SECRETS=false` agora é rejeitado em runtime seguro (`FLASK_DEBUG=false` e `FLASK_TESTING=false`), com testes de regressão para cenários seguro/debug | 5fc1be7 |
| 2026-02-12 | S6-09 | Sweep de retenção confirmado fora do ciclo de request: retenção executada por comando operacional (`flask audit-events purge-expired`) com teste de regressão que garante não execução durante requests (`tests/test_audit_trail.py`) | 208e1d1 |
| 2026-02-13 | I15 | TLS: script de renovação (`renew_tls_cert.sh`) + systemd timer instalado em PROD via SSM e validação `--dry-run` executada | 575dcea, 3137cd9 |
| 2026-02-13 | I8 | Firewall host: UFW habilitado em DEV/PROD via SSM (deny incoming + allow 80/443 + loopback), com verificação de status | 5825206, 2b2459c |
| 2026-02-13 | I8 | IAM audit: instâncias DEV/PROD usando role `auraxis-ec2-ssm-role` com políticas gerenciadas mínimas (SSM + CloudWatchAgent) e inline policy para backups S3 | c76957f |
| 2026-02-13 | I16 | Checklist automatizado (DNS/HTTP/SSM/Route53/Logs/S3) implementado e validado em DEV/PROD (`scripts/aws_validate_i16.py`) | 2af0a95 |
| 2026-02-14 | I5 | Guardrails de custo aplicados (AWS Budgets + Cost Anomaly Detection) com limite conservador em USD e docs de custo/Plano B | 877c0cc |
| 2026-02-14 | I9 | Runbook operacional consolidado (deploy/rollback, TLS, backups/restore, observabilidade, firewall, custo) | 877c0cc |
| 2026-02-14 | I6 | Deploy automático via GitHub Actions (OIDC assume role + SSM) para DEV/PROD, com PROD manual | pending-commit |
| 2026-02-12 | S6-12 | Política `/docs` endurecida com validação de startup: `DOCS_EXPOSURE_POLICY` inválido agora causa erro em runtime seguro; em debug mantém fallback seguro para produtividade local, com testes dedicados | 208e1d1 |
| 2026-02-12 | S1 (fase 1) | Script operacional `scripts/aws_s1_hardening.py` criado com `audit/apply` (dry-run por padrão) para checagem de IMDSv2, SG exposure, EBS encryption, IAM profile, SSM e termination protection; aplicado hardening de termination protection em `auraxis_prod` e `auraxis_dev` via CLI | pending-commit |
| 2026-02-12 | S1 (fase 2) | SSM online confirmado via auditoria e script de migração de root volume para EBS criptografado adicionado (`scripts/aws_encrypt_root_volume.py`) com dry-run e `--execute` (downtime). | pending-commit |
| 2026-02-12 | S1 (fase 3) | Migração DEV executada: root volume substituído por EBS criptografado; `aws_s1_hardening.py audit` agora valida `encrypted=true` (PROD pendente). | pending-commit |
| 2026-02-12 | S1 (fase 4) | Migração PROD executada: root volume substituído por EBS criptografado; `aws_s1_hardening.py audit` valida `encrypted=true`. Observação: volume antigo e snapshots mantidos para rollback/cleanup posterior. | pending-commit |
| 2026-02-12 | S1-02 | Cleanup pós-migração executado: volumes não criptografados antigos e snapshots intermediários removidos (DEV+PROD). | pending-commit |
| 2026-02-12 | S1 (fase 5) | Correção de disponibilidade pós-downtime: PROD recebeu Elastic IP e `api.auraxis.com.br` foi atualizado no Route 53 para evitar mudança de IP após stop/start; validação via `dig` e `curl` (HTTPS 200). | pending-commit |
| 2026-02-12 | S1 (fase 6) | SSH ingress removido dos Security Groups usados por DEV/PROD; acesso administrativo passa a depender de SSM Session Manager (requer `session-manager-plugin` local). Auditor S1 agora sinaliza `SSH ingress present` quando existir regra de porta 22. | pending-commit |
| 2026-02-12 | S1 (fase 7) | Patching baseline configurado via SSM Maintenance Window: `auraxis-dev-patching` (cron 05:00 UTC) e `auraxis-prod-patching` (cron 06:00 UTC) com task `AWS-RunPatchBaseline` e role `auraxis-ssm-maintenance-window-role`. Instâncias taggeadas com `App=auraxis` e `Environment=dev/prod`. | pending-commit |
| 2026-02-12 | S1 (fase 8) | Security Groups segregados por ambiente: criados `auraxis-prod-web` e `auraxis-dev-web` (somente 80/443), anexados às instâncias e SGs antigos removidos. | pending-commit |
| 2026-02-12 | S1 (fase 9) | Egress hardening nos SGs de DEV/PROD: removido `-1 0.0.0.0/0` e permitido somente `tcp/443`, `tcp/80`, DNS (`tcp/udp 53` para `172.31.0.2/32`) e NTP (`udp/123` para `169.254.169.123/32`). Auditor S1 passou a reportar egress scope/broad egress. | pending-commit |
| 2026-02-12 | S1 (fase 10) | DNS DEV corrigido: `dev.api.auraxis.com.br` atualizado para o IP público atual da instância DEV, validado com `dig` e `curl` (HTTPS 200). | pending-commit |
| 2026-02-13 | S1 (fase 11) | DEV com IP estável: Elastic IP associado à instância DEV e `dev.api.auraxis.com.br` atualizado no Route 53; validação via `dig` e `curl` (HTTPS 200). | pending-commit |
| 2026-02-13 | S1 (fase 12) | Observabilidade mínima (sem SNS): alarmes CloudWatch criados para DEV/PROD (`CPUHigh` e `StatusCheckFailed`). Próximo passo é adicionar SNS/Email/ChatOps e dashboards. | pending-commit |
| 2026-02-13 | S1 (fase 13) | NACL hardening no subnet compartilhado (`subnet-006b15b6fb193f5e7`): NACL dedicado `auraxis-web-nacl` criado e associado, permitindo apenas 80/443 e portas efêmeras (tcp/udp 1024-65535) + egress DNS/NTP; validação via `curl` (PROD/DEV 200) e SSM RunCommand (Success). | pending-commit |
| 2026-02-13 | S1 (fase 14) | Firewall no host (UFW) habilitado via SSM em DEV/PROD: default deny incoming, allow outgoing, allow `80/tcp` e `443/tcp` e loopback. Validado via `curl` (PROD/DEV 200) e `ufw status` (active). | pending-commit |
| 2026-02-13 | S1 (fase 15) | Patching calibrado: execução on-demand do `AWS-RunPatchBaseline` em DEV validada (Success). Política alvo: DEV `RebootIfNeeded`, PROD `NoReboot` (configurada via maintenance windows). | pending-commit |
| 2026-02-13 | S1 (fase 16) | Observabilidade mínima: CloudWatch Dashboard `Auraxis-EC2` criado com CPU e StatusCheckFailed para DEV/PROD. | pending-commit |
| 2026-02-13 | S1 (fase 17) | Notificações habilitadas: tópico SNS `auraxis-alerts` criado com assinatura email e alarmes CloudWatch atualizados para enviar `ALARM/OK/INSUFFICIENT_DATA` para o SNS. Teste: `set-alarm-state` disparado manualmente em um alarme de DEV. | pending-commit |
| 2026-02-13 | S1-03 | Backups Postgres em S3: bucket com policy HTTPS+SSE, versioning, lifecycle, IAM no role da EC2; backup manual DEV/PROD validado + restore drill DEV validado; agendamento diário via SSM Maintenance Windows. | pending-commit |
| 2026-02-13 | I7 | Observabilidade mínima: CloudWatch Agent aplicado via SSM para métricas de memória/disco (`Auraxis/EC2`), alarmes `MemUsedHigh/DiskUsedHigh` (DEV+PROD) com SNS/email e dashboard `Auraxis-EC2` atualizado. | pending-commit |
| 2026-02-13 | I7 | Logs centralizados (preparação): overlay `docker-compose.aws.logging.yml` (awslogs) e script idempotente `scripts/aws_cloudwatch_logs_i7.py` para IAM + log groups + retention. Pendência: aplicar overlay nas EC2 e validar streams recebendo eventos. | pending-commit |
| 2026-02-13 | I7 | Healthcheck: endpoint público `GET /healthz` (liveness) e healthcheck do `docker-compose.prod.yml` migrado de `/docs/swagger/` para `/healthz` para reduzir acoplamento a docs. | pending-commit |
| 2026-02-13 | I7 | Canary barato: Route53 health checks (DEV+PROD) em `https://<domain>/healthz` + alarmes CloudWatch `auraxis-health-dev/prod` para SNS `auraxis-alerts`. | pending-commit |
| 2026-02-13 | I7 | Mitigação temporária: `auraxis-health-dev/prod` ficaram em estado `ALARM` (endpoint ainda não deployado em master). Actions foram desabilitadas via `cloudwatch disable-alarm-actions` até concluir deploy de `/healthz`. | pending-commit |
| 2026-02-13 | CI/Security | Correção do check `security_evidence_check.sh`: padrões atualizados para refletir paths reais após modularização (`graphql/utils.py`, `auth/resources.py`). | 465cba6 |
| 2026-02-13 | Security | GraphQL: sanitização de `extensions` em erros de execução para evitar leak de detalhes de infraestrutura; Transações: deduplicação de `_guard_revoked_token` em `transaction.utils`. | pending-commit |
| 2026-02-13 | DX/CI | Paridade local: script `scripts/run_ci_like_actions_local.sh` (pipeline CI-like) + hooks `pre-push` no pre-commit para `pip-audit` e `security_evidence_check.sh` (evita surpresas só no Actions). | pending-commit |
| 2026-02-13 | I7 | Rollout em EC2 via SSM: `awslogs` aplicado em DEV/PROD (streams `dev/prod-{nginx,web,db,redis}`), health checks Route53: PROD `HTTPS:443`, DEV migrado para `HTTP:80` (TLS ainda não emitido no DEV), alarmes reabilitados após estabilização. | pending-commit |
| 2026-02-13 | I6 | Deploy (fase 1, manual): script `scripts/aws_deploy_i6.py` para deploy via SSM por git ref em DEV/PROD com validação `/healthz` e render de Nginx por ambiente. | pending-commit |
| 2026-02-13 | S1 | Alertas operacionais: regra EventBridge `auraxis-ssm-command-failures` -> SNS `auraxis-alerts` para falhas de SSM RunCommand (patching/backups/ops). | pending-commit |
| 2026-02-13 | S1 | Patching validado end-to-end: tasks de `AWS-RunPatchBaseline` re-registradas com `RebootIfNeeded` (DEV) e `NoReboot` (PROD) e validação executada via maintenance windows one-off agendadas (DEV+PROD: SUCCESS). | pending-commit |
| 2026-02-09 | D (observacao) | Restaurados arquivos deletados acidentalmente: ticker/carteira | n/a |

## Proxima prioridade sugerida
- S1/S3 (P1): fechar controles de infraestrutura OWASP em AWS (`S1`) e integrar exportação central de métricas/alertas de segurança (CloudWatch/Prometheus).
- G17 (P1): eliminar `ResourceWarning` remanescente da suíte (`tests/test_transaction_contract.py`) para manter execução 100% limpa e reproduzível no CI/local.

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
| H1-TICKER | `graphql.schema` | `tickers`, `addTicker`, `deleteTicker` | In Progress | 75% | Baixo | ba1f238 |
| H1-HARDENING | `graphql_controller` | autorização fina por operação, limites de complexidade/profundidade, observabilidade | In Progress | 45% | Alto: custo de query baseline ativo, faltam observabilidade e custo por domínio | pending-commit |

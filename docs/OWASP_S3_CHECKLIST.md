# OWASP S3 Checklist (Working Sheet)

Updated at: 2026-02-20  
Status scale: `PASS`, `PARTIAL`, `FAIL`, `N/A`.

## API Top 10 Checklist

| Control | Status | Evidence | Action Owner | Next Action |
|---|---|---|---|---|
| API1 - Object-level authorization enforced in all user-owned resources | PASS | Ownership checks em REST/GraphQL + regressões em `tests/test_graphql_resource_authorization.py` e validações de referência de transação | Backend | Monitorar regressão em novas rotas |
| API2 - Authentication and token lifecycle hardened | PASS | JWT callbacks, revogação por `current_jti`, login guard progressivo e testes de contrato | Backend/SRE | Revisão periódica de política de expiração |
| API3 - Property-level authorization and input field constraints | PASS | Schemas Marshmallow/Webargs + mitigação de mass-assignment (`S6-01/S6-02`) e validações por allowlist | Backend | Manter matriz de campos em revisão de PR |
| API4 - Resource consumption controls (rate/quotas/timeouts) | PASS | Rate-limit por domínio (`app/middleware/rate_limit.py`) + limites GraphQL de bytes/profundidade/complexidade/operações (`app/graphql/security.py`) | Backend | Ajuste fino de quotas por ambiente conforme telemetria |
| API5 - Function-level authorization boundaries documented/tested | PASS | Auth guard central + política de autorização GraphQL (`app/graphql/authorization.py`) + testes negativos de acesso | Backend | Expandir cenários de abuso em smoke externo |
| API6 - Sensitive business flow abuse protections | PASS | Login guard progressivo, rate-limit em auth/graphql e observabilidade de tentativas | Backend | Integrar alertas centralizados por anomalia |
| API7 - SSRF and outbound request controls | PASS | Integração BRAPI com ticker allowlist, timeout/retry/fallback e validação defensiva de payload | Backend/SRE | Revalidar política de saída em mudanças de provider |
| API8 - Security misconfiguration controls | PASS | Runtime fail-fast para segredos/config insegura, CORS/headers por ambiente e docs exposure policy | Backend/SRE | Auditoria periódica de drift de configuração |
| API9 - API inventory and lifecycle management | PASS | Inventário OWASP (`OWASP_S3_INVENTORY.md`) + paridade de rotas OpenAPI (`tests/test_openapi_route_parity.py`) | Backend | Revisão em toda mudança de superfície de API |
| API10 - Safe consumption of third-party APIs | PASS | Hardening BRAPI + testes de integração com falha real de provider em REST/GraphQL (`tests/test_brapi_integration_contract.py`) | Backend | Manter matriz de fallback e observabilidade |

## ASVS High-Level Checklist

| ASVS Area | Status | Evidence | Next Action |
|---|---|---|---|
| V1 Architecture and threat model | PASS | Threat model formal em `docs/THREAT_MODEL_STRIDE.md` | Revisão por ciclo de feature |
| V2 Authentication | PASS | Fluxo auth REST/GraphQL com validação forte e políticas anti-enumeração | Revisão de parâmetros de lockout |
| V3 Session management | PASS | JTI por sessão + revogação de token + logout consistente | Monitoramento contínuo |
| V4 Access control | PASS | Ownership checks e testes de acesso cruzado | Cobrir novos recursos |
| V5 Validation and sanitization | PASS | Estratégia unificada de validação (ADR) + sanitização central de entrada/saída | Revisão em mudanças de schema |
| V7 Error handling and logging | PASS | Contrato de erro seguro + mascaramento de erro interno + logging estruturado | Integrar alertas externos por severidade |
| V8 Data protection | PASS | Segredos fortes obrigatórios em runtime seguro + runbook de cloud secrets | Revisão de rotação operacional |
| V9 Communications | PASS | TLS/Nginx hardening + renovação automática de certificado | Auditoria periódica de certificados |
| V14 Configuration | PASS | Configuração por ambiente com validação de startup e política explícita de fail-fast | Validar drift com rotina de governança |

## Exit Criteria (S3)
- Checklist completo e atualizado para API Top 10 + ASVS.
- Evidências rastreáveis para controles críticos em código/testes/docs.
- Verificação automática de evidências disponível em `scripts/security_evidence_check.sh`.

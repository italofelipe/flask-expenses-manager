# API-OPS-04-05

## O que foi feito

- fortalecido o helper de deploy via SSM em `scripts/aws_deploy_i6.py`
  - diagnostico estruturado de `get-command-invocation`
  - escrita opcional de JSON no runner via `--diagnostics-json-path`
  - append automatico de resumo no `GITHUB_STEP_SUMMARY`
  - mensagens de falha com `status_details`, `response_code` e tails de `stdout`/`stderr`
- atualizado `.github/workflows/deploy.yml`
  - artifacts `deploy-dev-ssm-diagnostics` e `deploy-prod-ssm-diagnostics`
  - resumo final do job agora destaca `command_id`, `status`, `status_details` e `response_code`
- refatorado o enforcement do Sonar para `scripts/sonar_enforce_ci.py`
  - report estruturado com erros da policy customizada
  - persistencia opcional em JSON via `SONAR_POLICY_REPORT_PATH`
  - wrapper shell `scripts/sonar_enforce_ci.sh` preservado por compatibilidade
- atualizado `.github/workflows/ci.yml`
  - `quality gate` e `custom policy` passam a ter outcomes separados
  - artifact `sonar-policy-report`
  - resumo final do job explicita quando o vermelho veio da policy customizada Auraxis
  - gate final continua bloqueando o CI quando deve bloquear
- adicionados testes puros:
  - `tests/test_aws_deploy_i6.py`
  - `tests/test_sonar_enforce_ci.py`
- atualizado `docs/RUNBOOK.md` com os novos artifacts e o fluxo de diagnostico

## O que foi validado

- `pytest --noconftest tests/test_aws_deploy_i6.py tests/test_sonar_enforce_ci.py -q`
- `ruff check` nos arquivos alterados
- `mypy app`
- `mypy` focado em `scripts/aws_deploy_i6.py` e `scripts/sonar_enforce_ci.py`
- `git diff --check`
- `sh -n scripts/sonar_enforce_ci.sh`

## Riscos pendentes

- a melhor validacao de `OPS-04` continua sendo um run real de falha de deploy no GitHub Actions
- a melhor validacao de `OPS-05` continua sendo um run real de policy Sonar reprovada no CI
- o branch foi aberto a partir de `origin/master`, mas o remoto avancou durante o bloco; rebase final pode ser necessario antes do merge

## Próximo passo

- abrir PR unico cobrindo `OPS-04 + OPS-05`
- comentar nas issues `#639` e `#640` com as evidencias do PR
- apos merge, validar um run real dos workflows para confirmar o ganho de observabilidade fim a fim

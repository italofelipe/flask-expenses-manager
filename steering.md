# Steering Guide (AI + Engineering Workflow)

## 1. Source of Truth
- Backlog, status e rastreabilidade: `TASKS.md`.
- Contexto funcional e operacional: `README.md`.
- Este arquivo define o modo de execucao da IA no projeto.

## 2. Sequencia de ciclos
- Ordem oficial: `estabilizacao > features > debitos > refinamento > features`.
- Em retomadas apos re-clone, assumir `estabilizacao` ate validar baseline local e CI.

## 3. Fluxo obrigatorio por tarefa
1. `git checkout master`
2. `git pull --ff-only origin master`
3. Criar branch nova seguindo conventional branching.
4. Implementar com escopo pequeno e isolado.
5. Executar validacoes locais relevantes.
6. Atualizar documentacao/rastreabilidade (`TASKS.md`, docs afetados).
7. Commit pequeno e granular (Conventional Commit).
8. `git push -u origin <branch>` ao final da tarefa.

## 4. Branching e commits
- Branch: `tipo/escopo-descricao-curta`.
- Tipos: `feat`, `fix`, `refactor`, `chore`, `docs`, `test`, `perf`, `security`.
- Evitar prefixos ad-hoc.
- Se o ambiente/ferramenta impor prefixo tecnico, manter semanticamente o padrao convencional apos o prefixo.
- Commit obrigatoriamente em Conventional Commits.
- Um commit = uma responsabilidade (facil rollback).

## 5. Padrao tecnico esperado
- Tratar cada alteracao com nivel de engenharia senior.
- Priorizar Clean Code, SOLID e design orientado a dominio.
- Evitar acoplamento desnecessario, duplicacao e "fix" sem teste.
- Preservar retrocompatibilidade quando exigido por contrato existente.

## 6. Quality gates locais (antes de commit)
- `black .`
- `isort app tests config run.py run_without_db.py`
- `flake8 app tests config run.py run_without_db.py`
- `mypy app`
- `pytest -m "not schemathesis" --cov=app --cov-fail-under=85`
- `pre-commit run --all-files`

## 7. Seguranca e operacao
- Nunca commitar segredo/chave/token.
- Manter aderencia aos gates de seguranca: Bandit, Gitleaks, pip-audit, Trivy, Snyk, Sonar.
- Em mudancas de deploy/AWS, sempre atualizar runbook e checklist operacional.

## 8. Rastreabilidade e documentacao
- Toda entrega deve refletir status/progresso/risco/commit no `TASKS.md`.
- Registrar decisoes arquiteturais relevantes em docs dedicadas (ex.: ADR).
- Marcar debitos tecnicos explicitos quando houver trade-off deliberado.

## 9. Definicao de pronto (DoD)
- Requisito implementado com testes adequados.
- Sem regressao de contrato (REST/GraphQL quando aplicavel).
- Linters/type-check/testes/gates locais OK.
- Documentacao atualizada.
- Branch publicada com commit(s) granulares e mensagem clara.

## 10. Itens que exigem interacao humana
- Escolhas de produto/negocio (priorizacao de roadmap, UX sensivel, custo/fornecedor).
- Credenciais/acessos externos nao disponiveis localmente.
- Decisoes de arquitetura com impacto transversal sem diretriz pre-aprovada.

## 11. Ritual de feedback entre blocos
- Ao concluir cada bloco de execucao (conjunto de tarefas/feature set), executar uma rodada formal de feedback.
- A IA deve sempre propor essa rodada antes de iniciar o proximo bloco.
- O feedback deve cobrir no minimo: estrategia, execucao, riscos, oportunidades, qualidade tecnica, governanca e proximos ajustes.
- Registrar os aprendizados e decisoes de melhoria na documentacao (steering/TASKS/ADR quando aplicavel) para evolucao continua do processo.

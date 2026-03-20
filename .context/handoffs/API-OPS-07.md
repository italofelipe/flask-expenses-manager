# API-OPS-07 - Restricao de docs runtime em producao

## O que foi feito

- a politica padrao de `/docs` passou a ser `disabled` quando o runtime e de producao
- `DOCS_EXPOSURE_POLICY=public` passou a ser rejeitado em producao segura no startup
- `docker-compose.prod.yml` agora explicita `DOCS_EXPOSURE_POLICY=disabled` por default
- `.env.prod.example` foi alinhado para o mesmo comportamento
- `docs/CI_CD.md` passou a documentar a politica oficial de docs runtime

## O que foi validado

- `ruff check app/middleware/docs_access.py tests/test_docs_access_policy.py config/__init__.py`
- `pytest tests/test_docs_access_policy.py -q`
- `mypy app/middleware/docs_access.py tests/test_docs_access_policy.py`

## Riscos pendentes

- ambientes de producao que dependam excepcionalmente de docs runtime autenticada precisam configurar isso de forma explicita
- a superficie publica oficial da API continua sendo o portal MkDocs da platform; este bloco nao altera DNS nem o runtime do portal

## Proximo passo

- abrir PR do endurecimento da politica
- validar o CI completo
- atualizar a issue `#648` com o rationale e a evidencia

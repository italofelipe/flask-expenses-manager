# API19.1 - Supply Chain de Imagens

## O que foi feito
- criado `scripts/ci_image_artifact.sh` para build/export/load das imagens canônicas do CI
- criado `docker-compose.ci.yml` para subir smoke/full a partir da imagem já construída, sem bind mount nem rebuild
- `ci.yml` passou a ter o job `ci-runtime-images`, com artifacts efêmeros reutilizados por `api-smoke`, `api-integration` e `trivy`
- compose principal recebeu `WEB_IMAGE` explícito para melhorar auditabilidade e preparar paridade local/CI
- docs operacionais foram atualizadas em `.github/workflows/README.md`, `docs/CI_CD.md`, `scripts/README.md` e `.context/quality_gates.md`

## O que foi validado
- `docker build` nos perfis dev e prod via `scripts/ci_image_artifact.sh`
- export + remoção + reload da imagem dev
- `docker compose -f docker-compose.ci.yml up -d db redis web`
- `flask db upgrade` dentro da stack de CI
- healthcheck em `http://localhost:3333/healthz`
- `pre-commit` e `git diff --check`

## Riscos pendentes
- artifacts de imagem aumentam volume de upload/download; a retenção curta reduz custo, mas vale monitorar tempo total do workflow
- a paridade operacional completa local/CI ainda depende do slice `API19.4`

## Próximo passo
- fechar `API19.2` com bootstrap canônico da stack e taxonomia de falhas para reduzir ainda mais flakiness e rerun cego

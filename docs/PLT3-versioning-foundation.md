# PLT3 - Versioning Foundation (API)

## Objetivo

Eliminar versionamento manual e padronizar releases da API com base em Conventional Commits.

## Entrega deste bloco

- `.github/workflows/release-please.yml`
- `.release-please-config.json`
- `.release-please-manifest.json`

## Como funciona

1. Push em `master/main` dispara `Release Please`.
2. A action abre/atualiza PR de release com changelog e versão semântica.
3. Ao mergear o PR de release:
   - tag semântica é criada;
   - release GitHub é publicada automaticamente.

## Requisitos operacionais

- Secret obrigatório no repositório: `RELEASE_PLEASE_TOKEN`
- O token de release deve ser um PAT ou credencial equivalente capaz de criar/atualizar o PR de release sem suprimir o disparo do CI
- `GITHUB_TOKEN` não deve ser usado como token principal do Release Please neste repositório, porque pode criar PRs de release que ficam sem checks por proteção anti-recursão do GitHub Actions

## Observações

- Estratégia da API está em `release-type: simple`:
  - source of truth da versão é a tag/release no Git;
  - não há bump automático de arquivo Python neste bloco.
- Para sincronizar versão em runtime (ex.: endpoint `/version`), criar task dedicada para injetar tag de release em build/deploy.

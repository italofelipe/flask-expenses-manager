# config

## Objetivo
Configuracoes de inicializacao da aplicacao (Flask/SQLAlchemy/extensoes), com separacao de responsabilidades de bootstrap.

## Padroes obrigatorios
- Configuracoes devem ser orientadas por env vars.
- Defaults inseguros so sao aceitos em ambiente local de desenvolvimento.
- Runtime de producao deve falhar rapido em configuracao critica invalida.

## Manutencao
- Mudancas em config exigem revisao de impacto em DEV/PROD.
- Sempre alinhar com `docker-compose*.yml`, workflows e runbooks.

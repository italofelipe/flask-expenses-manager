# deploy

## Objetivo
Arquivos de suporte a deploy e runtime de infraestrutura (Nginx, systemd, componentes de orquestracao local/EC2).

## Estrutura
- `nginx/`: templates de configuracao HTTP/TLS e variacoes por ambiente.
- `systemd/`: unidades e timers de operacao (ex.: renovacao TLS).

## Padroes obrigatorios
- Templates devem ser deterministas e renderizaveis por script.
- Mudancas em proxy/TLS exigem validacao em DEV antes de PROD.
- Sempre prever fallback/rollback operacional.

## Validacao minima
- Health endpoint respondendo apos deploy.
- Reverse-proxy estavel sem restart loop.
- TLS valido quando ambiente exige HTTPS.

# API-OPS-10 - ALB Public Edge Preparation

## O que foi feito
- adicionado `deploy/nginx/default.alb.conf` para terminação TLS no ALB com origem HTTP na instância
- `scripts/ensure_tls_runtime.sh` agora suporta `EDGE_TLS_MODE=alb`
- `scripts/aws_deploy_i6.py` foi atualizado para bootstrapar o template `default.alb.conf` e o modo `alb`
- `.env.prod.example` e docs operacionais foram atualizados com o contrato do modo `alb`

## O que foi validado
- leitura e coerência do fluxo de deploy atual com `docker-compose.prod.yml`
- consistência do cabeçalho `X-Forwarded-Proto` / `X-Forwarded-Port` no template `alb`
- sintaxe visual dos artefatos alterados

## Riscos pendentes
- o cutover real para ALB ainda depende de provisionamento AWS: ACM, ALB, target group, listener e Route 53
- o runtime atual de produção ainda usa `instance_tls` até que o ALB seja criado e validado
- o ambiente `dev` segue instável e não deve ser usado como base de confiança para o cutover

## Próximo passo
- provisionar ACM + ALB + target group em produção
- validar o ALB usando o DNS nativo da AWS
- só então apontar `api.auraxis.com.br` para o ALB

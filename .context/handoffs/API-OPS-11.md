# API-OPS-11

## O que foi feito

- introduzido `EDGE_TLS_MODE=alb_dual` no runtime para cutover seguro de `HTTPS origin` para `HTTP origin`
- adicionado template novo em `deploy/nginx/default.alb_dual.conf`
- atualizado `scripts/ensure_tls_runtime.sh` para:
  - renderizar `80` e `443` ao mesmo tempo em modo transitório
  - exigir certificado local existente antes de ativar `alb_dual`
- atualizado `scripts/aws_deploy_i6.py` para bootstrapar o novo template/modo em hosts legados
- documentado o fluxo em `docs/RUNBOOK.md` e `docs/DEPLOYMENT_ENVIRONMENTS.md`

## O que foi validado

- `sh -n scripts/ensure_tls_runtime.sh`
- `python3 -m py_compile scripts/aws_deploy_i6.py`
- revisão do diff do recorte alterado

## Riscos pendentes

- o cutover real em `prod` ainda precisa ser executado com essa versão já deployada no host
- o modo `alb_dual` depende de certificado local ainda presente durante a janela de transição

## Próximo passo

- abrir PR e mergear essa melhoria
- deployar em `prod`
- aquecer target group `HTTP:80` com `EDGE_TLS_MODE=alb_dual`
- só então trocar o listener do ALB para origem HTTP
- após estabilização, trocar o host para `EDGE_TLS_MODE=alb`

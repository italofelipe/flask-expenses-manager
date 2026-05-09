# CLAUDE.md — `app/application/services/*`

Camada de logica de negocio do auraxis-api. Services sao stateless e orquestram
models, schemas e repositorios.

## Regras

- Services sao funcoes puras ou metodos de classe estaticos/classmethods
- Nunca acoplam HTTP (sem `request`, `jsonify`) — isso fica nos controllers
- Nunca acoplam ao banco diretamente com SQL raw — usam models SQLAlchemy
- Toda operacao de escrita deve ser transacional (`db.session.commit()` ao final)
- Erros de negocio levantam excecoes do tipo `AppError` (nunca `HTTPException`)
- Services nao conhecem o protocolo (REST ou GraphQL) que os chamou

## Padrao canonico

```python
# app/application/services/<domain>_service.py
from app.models.<domain> import <Domain>
from app.extensions import db
from app.errors import AppError

class <Domain>Service:
    @classmethod
    def create(cls, user_id: int, data: dict) -> <Domain>:
        # validacoes de negocio
        existing = <Domain>.query.filter_by(user_id=user_id).first()
        if existing:
            raise AppError("already_exists", 409)
        # criacao do model
        entity = <Domain>(user_id=user_id, **data)
        db.session.add(entity)
        db.session.commit()
        return entity
```

## Services existentes

| Service | Responsabilidade |
|---|---|
| `auth_security_policy_service.py` | Politicas de seguranca de autenticacao |
| `authenticated_user_bootstrap_service.py` | Bootstrap do contexto de usuario autenticado |
| `authenticated_user_context_service.py` | Contexto de usuario por request |
| `billing_email_service.py` | Emails transacionais de cobranca |
| `email_confirmation_service.py` | Confirmacao de email por token |
| `entitlement_application_service.py` | Logica de entitlements por plano |
| `goal_application_service.py` | Metas financeiras e contribuicoes |
| `installment_vs_cash_application_service.py` | Comparativo parcelado vs avista |
| `installment_vs_cash_bridge_service.py` | Bridge para dados de simulacao |
| `investment_application_service.py` | Operacoes de investimento |
| `login_identity_service.py` | Verificacao de identidade no login |
| `password_reset_service.py` | Fluxo de reset de senha |
| `password_verification_service.py` | Verificacao de senha atual |
| `public_error_mapper_service.py` | Mapeamento de erros internos para publicos |
| `session_service.py` | Gestao de sessoes e refresh tokens |
| `simulation_application_service.py` | Simulacoes financeiras |
| `transaction_application_service.py` | CRUD de transacoes |
| `transaction_ledger_service.py` | Contabilidade do ledger |
| `transaction_query_service.py` | Queries complexas de transacoes |
| `transaction_reminder_service.py` | Lembretes de transacao recorrente |
| `user_profile_service.py` | Atualizacao de perfil de usuario |
| `wallet_application_service.py` | Carteira e ativos de investimento |
| `advisory_service.py` | Recomendacoes e insights financeiros |

## Antes de criar um novo service

1. Verifique se ja existe um service para o dominio na tabela acima
2. Prefira estender o service existente com novo metodo ao inves de criar duplicata
3. Se o service existente ficaria grande demais (>300 linhas), divida com sufixo semantico:
   - `_query_service` para operacoes de leitura pesada
   - `_application_service` para orchestracao de casos de uso
   - `_ledger_service` para contabilidade/calculo

## Testes

Unit tests em `tests/unit/services/` — mockam o banco com fixtures pytest:

```bash
pytest tests/unit/services/test_<domain>_service.py -v
```

Cobertura minima: 85% (obrigatoria para merge).

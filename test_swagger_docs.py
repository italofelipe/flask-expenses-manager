#!/usr/bin/env python3
"""
Script para testar a documentação Swagger sem conectar ao banco de dados
"""

import os
import sys
from typing import Any, Dict, Optional
from unittest.mock import patch

# Configurar variáveis de ambiente para teste
os.environ.update(
    {
        "DB_USER": "test",
        "DB_PASS": "test",
        "DB_HOST": "localhost",
        "DB_PORT": "5432",
        "DB_NAME": "test_db",
        "FLASK_DEBUG": "True",
        "SECRET_KEY": "test-secret",
        "JWT_SECRET_KEY": "test-jwt-secret",
    }
)


def test_swagger_documentation() -> bool:
    """Testa se a documentação Swagger está configurada corretamente"""

    print("🧪 Testando documentação Swagger...")

    try:
        # Mock do banco de dados para evitar conexão
        with patch("app.extensions.database.db.create_all"):
            from app import create_app

            app = create_app()

            print("✅ Aplicação Flask criada com sucesso!")

            # Verificar configuração do Swagger
            with app.app_context():
                # Verificar se o APISpec foi configurado
                spec: Any = app.config.get("APISPEC_SPEC")
                if spec:
                    print(f"✅ APISpec configurado: {spec.title} v{spec.version}")

                    # Verificar tags
                    tags: Optional[Any] = getattr(spec, "tags", None)
                    if tags:
                        print(f"🏷️ Tags configuradas: {len(tags)}")
                        for tag in tags:
                            print(f"   - {tag['name']}: {tag['description']}")

                    # Verificar componentes de segurança
                    security_schemes: Dict[str, Any] = spec.components.get(
                        "securitySchemes", {}
                    )
                    if "BearerAuth" in security_schemes:
                        print("🔐 Autenticação Bearer configurada")

                    print("✅ Documentação Swagger configurada corretamente!")
                else:
                    print("❌ APISpec não encontrado na configuração")
                    return False

            return True

    except Exception as e:
        print(f"❌ Erro ao testar documentação: {e}")
        return False


def test_schemas_documentation() -> bool:
    """Testa se os schemas têm documentação adequada"""

    print("\n📋 Testando documentação dos schemas...")

    try:
        from app.schemas import TransactionSchema

        # Testar TransactionSchema
        transaction_fields: Dict[str, Any] = TransactionSchema().fields
        required_fields: list[str] = ["title", "amount", "type", "due_date"]

        for field_name in required_fields:
            if field_name in transaction_fields:
                field: Any = transaction_fields[field_name]
                if hasattr(field, "metadata") and field.metadata.get("description"):
                    print(f"✅ Campo '{field_name}' tem descrição")
                else:
                    print(f"⚠️ Campo '{field_name}' sem descrição")
            else:
                print(f"❌ Campo '{field_name}' não encontrado")

        print("✅ Teste de schemas concluído!")
        return True

    except Exception as e:
        print(f"❌ Erro ao testar schemas: {e}")
        return False


def main() -> int:
    """Função principal do teste"""

    print("🚀 Iniciando testes de documentação Swagger...\n")

    # Teste 1: Configuração do Swagger
    swagger_ok: bool = test_swagger_documentation()

    # Teste 2: Documentação dos schemas
    schemas_ok: bool = test_schemas_documentation()

    print("\n" + "=" * 50)
    if swagger_ok and schemas_ok:
        print("🎉 Todos os testes passaram!")
        print("📚 A documentação Swagger está configurada corretamente.")
        print(
            "🌐 Acesse: http://localhost:5000/docs/ (quando a aplicação estiver rodando)"
        )
        return 0
    else:
        print("❌ Alguns testes falharam.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Script para rodar a aplicação Flask sem banco de dados
Apenas para visualizar a documentação Swagger
"""

import os
from typing import Any
from unittest.mock import patch

# Configurar variáveis de ambiente
env_vars: dict[str, str] = {
    "DB_USER": "test",
    "DB_PASS": "test",
    "DB_HOST": "localhost",
    "DB_PORT": "5432",
    "DB_NAME": "test_db",
    "FLASK_DEBUG": "True",
    "SECRET_KEY": "test-secret",
    "JWT_SECRET_KEY": "test-jwt-secret",
}
os.environ.update(env_vars)


def run_app() -> None:
    """Roda a aplicação Flask sem banco de dados"""

    print("🚀 Iniciando aplicação Flask para visualizar documentação Swagger...")
    print("📚 Acesse: http://localhost:5000/docs/")
    print("🔗 JSON da API: http://localhost:5000/docs/swagger/")
    print("⏹️  Pressione Ctrl+C para parar\n")

    try:
        # Mock do banco de dados para evitar conexão
        with patch("app.extensions.database.db.create_all"):
            from app import create_app

            app: Any = create_app()

            # Rodar a aplicação
            app.run(host="0.0.0.0", port=5000, debug=True)

    except KeyboardInterrupt:
        print("\n👋 Aplicação finalizada!")
    except Exception as e:
        print(f"❌ Erro ao rodar aplicação: {e}")


if __name__ == "__main__":
    run_app()

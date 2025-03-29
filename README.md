# 🐍 Not Enough Cash, Stranger!

Uma API RESTful escrita em **Python** com **Flask**, utilizando **JWT para autenticação**, **PostgreSQL como banco de dados** e documentação automatizada via **Swagger UI (OpenAPI 3)**.

---

## 🚀 Tecnologias

- [Flask](https://flask.palletsprojects.com/)
- [Flask-JWT-Extended](https://flask-jwt-extended.readthedocs.io/)
- [Flask-Migrate](https://flask-migrate.readthedocs.io/)
- [Marshmallow](https://marshmallow.readthedocs.io/)
- [Flask-Apispec](https://flask-apispec.readthedocs.io/)
- [PostgreSQL](https://www.postgresql.org/)
- [Docker + Docker Compose](https://docs.docker.com/compose/)

---

## 📂 Estrutura do projeto

```
flask-template/
├── app/
│   ├── __init__.py         # Criação da aplicação e configuração do Swagger
│   ├── controllers/        # Endpoints (ex: auth_controller.py)
│   ├── extensions/         # DB, JWT, error handlers
│   ├── models/             # Modelos do banco
│   └── schemas/            # Schemas Marshmallow
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

---

## 📦 Como rodar o projeto com Docker

### 1. Crie o arquivo `.env` com as variáveis:

```env
POSTGRES_DB=flaskdb
POSTGRES_USER=flaskuser
POSTGRES_PASSWORD=flaskpass
DB_HOST=db
DB_PORT=5432
```

### 2. Suba os containers

```bash
docker-compose up --build
```

---

## 🌐 Endpoints principais

| Rota              | Método | Descrição               |
| ----------------- | ------ | ----------------------- |
| `/login/register` | POST   | Criação de novo usuário |
| `/login/auth`     | POST   | Login com JWT           |
| `/docs/`          | GET    | Interface Swagger (UI)  |
| `/docs/swagger/`  | GET    | JSON da documentação    |

---

## 🔐 Autenticação

- Após fazer login, um token JWT é retornado.
- Para acessar endpoints protegidos, envie o token no header:
  ```
  Authorization: Bearer <seu_token>
  ```

---

## ⚙️ Detalhes técnicos

- A aplicação Flask roda na **porta `3333`** (exposta via Docker).
- O PostgreSQL roda na **porta `5432`**.
- A interface Swagger está acessível em: [`http://localhost:3333/docs`](http://localhost:3333/docs)

---

## 🛠️ Migrations

Para aplicar ou gerar migrations manualmente:

```bash
docker-compose exec web flask db migrate -m "mensagem"
docker-compose exec web flask db upgrade
```

---

## 🧼 Pre-commit Hooks

Este projeto utiliza o arquivo `.pre-commit-config.yaml` para garantir consistência de código antes de cada commit. As seguintes ferramentas são utilizadas:

| Ferramenta | Função                                                                     |
| ---------- | -------------------------------------------------------------------------- |
| `black`    | Formatador de código automático conforme PEP8                              |
| `flake8`   | Linter para detectar erros de sintaxe, más práticas e código não utilizado |
| `isort`    | Organizador automático de imports                                          |
| `mypy`     | Verificador de tipos estáticos para código Python tipado                   |

### Como usar

Instale o pre-commit e configure os hooks:

```bash
pip install pre-commit
pre-commit install
```

Agora, sempre que um commit for feito, os hooks serão executados automaticamente.

### Executar manualmente

Você pode rodar os hooks a qualquer momento com:

```bash
pre-commit run --all-files
```

### Lidando com avisos

- `black`: Corrige automaticamente arquivos mal formatados.
- `flake8`: Pode apontar erros como variáveis não usadas, imports não utilizados, problemas de indentação ou linhas muito longas. Corrija ou justifique os casos específicos.
- `isort`: Corrige automaticamente a ordem e agrupamento de imports.
- `mypy`: Aponte erros de tipo com base em anotações estáticas. É útil corrigir ou adicionar anotações para evitar falhas.

Esses hooks ajudam a manter a base de código limpa, confiável e dentro de boas práticas Python modernas.

---

## 📌 Observações

- A documentação Swagger é gerada automaticamente com base nos schemas e decorators `@use_kwargs` e `@doc`.
- O projeto segue boas práticas de organização modular com Blueprints e extensões desacopladas.

---

## ✅ Requisitos para desenvolvimento

- Docker e Docker Compose instalados
- Python 3.13+ (apenas para rodar fora do container, opcional)

---

## 🧪 Testes

> (Ainda não implementado — considere usar `pytest` + `pytest-flask`)

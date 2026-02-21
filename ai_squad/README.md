# Auraxis AI Squad - Agentes Autônomos

Esta pasta contém o ecossistema de agentes agênticos (Agentic AI) para automatizar o ciclo de desenvolvimento do Auraxis.

## Estrutura do Esquadrão
- **PM (Gerente):** Analisa o `TASKS.md` e define o que fazer.
- **Backend Dev:** Implementa lógica em Flask/SQLAlchemy.
- **QA Engineer:** Roda o `pytest` e valida a implementação.

## Como usar (Mac OS)

1.  **Instalação (Crie um venv isolado):**
    ```bash
    cd ai_squad
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    ```

2.  **Configuração da API:**
    Crie um arquivo `.env` dentro de `ai_squad/` e adicione sua chave:
    ```bash
    OPENAI_API_KEY=sk-xxxx...
    ```
    *Nota: Você também pode usar modelos locais com **Ollama** se preferir.*

3.  **Execução:**
    ```bash
    python3 main.py
    ```

## Como estender
- Adicione novos agentes (Frontend, Mobile, DevOps) no `main.py`.
- Crie novas ferramentas em `tools/project_tools.py` (ex: ferramenta de git commit, ferramenta de deploy aws).
- Mude o `Process.sequential` para `Process.hierarchical` para que o PM tome decisões mais complexas.

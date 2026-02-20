"""
Auraxis Multi-Agent System — Entry Point.

Orchestrates a CrewAI squad of 5 specialized agents to automate the SDLC.
Each agent has access to security-hardened tools (see tools/project_tools.py)
and follows the knowledge base defined in .context/.

Agent Flow (sequential):
    PM (bootstrap + plan) → Backend → Frontend → QA → DevOps (human approval)

Integration with .context/:
    The PM agent performs the bootstrap sequence from .context/README.md
    before planning. Backend and QA agents can read architecture and
    quality gate docs via read_context_file().

References:
    - .context/README.md — bootstrap reading order
    - .context/03_agentic_workflow.md — agent operational loop
    - ai_squad/AGENT_ARCHITECTURE.md — squad architecture manifesto
    - ai_squad/tools/project_tools.py — all available tools
"""

from crewai import Agent, Crew, Process, Task
from dotenv import load_dotenv
from tools.project_tools import ProjectTools

load_dotenv()


class AuraxisSquad:
    """
    Auraxis development squad with 5 agents.

    The squad reads the .context/ knowledge base during bootstrap,
    then executes a sequential pipeline from planning to deployment.
    """

    def __init__(self) -> None:
        self.tools = ProjectTools()

    def run(self):  # type: ignore[no-untyped-def]
        # --- AGENTS ---

        manager = Agent(
            role="Gerente de Projeto Auraxis",
            goal=(
                "Coordenar o ciclo completo de desenvolvimento "
                "(Back, Front, QA, Deploy) usando a base de "
                "conhecimento em .context/ como referencia."
            ),
            backstory=(
                "Voce e o lider do squad Auraxis. Antes de qualquer "
                "planejamento, execute o bootstrap lendo os arquivos "
                "da base de conhecimento .context/ na ordem definida "
                "em .context/README.md. Use read_context_file() para "
                "cada arquivo e read_governance_file() para product.md "
                "e steering.md. Garanta que cada agente tenha o que "
                "precisa para trabalhar com rastreabilidade e qualidade."
            ),
            tools=[
                self.tools.read_tasks,
                self.tools.read_context_file,
                self.tools.read_governance_file,
            ],
            verbose=True,
            allow_delegation=True,
        )

        backend_dev = Agent(
            role="Senior Backend Engineer",
            goal="Implementar APIs Flask e migrations SQLAlchemy.",
            backstory=(
                "Focado em performance e seguranca de dados financeiros. "
                "Consulte .context/04_architecture_snapshot.md via "
                "read_context_file() para entender a estrutura do projeto "
                "antes de implementar. Siga os padroes de nomenclatura "
                "e arquitetura definidos na base de conhecimento."
            ),
            tools=[
                self.tools.read_tasks,
                self.tools.read_schema,
                self.tools.read_context_file,
                self.tools.write_file_content,
            ],
            verbose=True,
        )

        frontend_dev = Agent(
            role="Senior Frontend Engineer",
            goal="Desenvolver interfaces responsivas e intuitivas.",
            backstory=(
                "Especialista em criar UIs que consomem GraphQL/REST. "
                "Voce foca na experiencia do usuario e integra com "
                "os contratos definidos pelo backend."
            ),
            tools=[self.tools.write_file_content],
            verbose=True,
        )

        qa_engineer = Agent(
            role="QA Engineer",
            goal="Validar integridade do sistema e ausencia de bugs.",
            backstory=(
                "Rigoroso e detalhista. Consulte "
                ".context/05_quality_and_gates.md via read_context_file() "
                "para conhecer os gates de qualidade obrigatorios. "
                "Rode os testes e valide contra os criterios de pronto "
                "antes de aprovar o incremento."
            ),
            tools=[
                self.tools.run_backend_tests,
                self.tools.read_context_file,
            ],
            verbose=True,
        )

        devops_agent = Agent(
            role="Cloud DevOps Engineer",
            goal="Gerenciar infraestrutura AWS e processos de deploy.",
            backstory=(
                "Especialista em AWS EC2, S3 e automacao. "
                "Seguranca e sua prioridade numero 1. "
                "Toda acao de deploy requer aprovacao humana."
            ),
            tools=[self.tools.check_aws_status],
            verbose=True,
        )

        # --- TASKS ---

        task_plan = Task(
            description=(
                "BOOTSTRAP: Primeiro, leia os seguintes arquivos na ordem:\n"
                '1. read_context_file("README.md")\n'
                '2. read_context_file("01_sources_of_truth.md")\n'
                '3. read_context_file("04_architecture_snapshot.md")\n'
                '4. read_governance_file("steering.md")\n'
                '5. read_governance_file("product.md")\n'
                "6. read_tasks()\n\n"
                "Depois, defina o proximo incremento funcional baseado "
                "nas prioridades do TASKS.md e na direcao de product.md. "
                "Inclua no plano: branch name, commits planejados, "
                "quality gates a validar, e riscos identificados."
            ),
            expected_output=(
                "Plano de execucao detalhado para Backend e Frontend, "
                "incluindo branch name convencional, commits planejados, "
                "quality gates, e riscos mapeados."
            ),
            agent=manager,
        )

        task_backend = Task(
            description=(
                "Implemente a logica de backend e atualize o schema "
                "de dados conforme o plano do PM. Consulte "
                ".context/04_architecture_snapshot.md para a estrutura "
                "e o schema.graphql para contratos existentes."
            ),
            expected_output="Codigo Python e Migrations criados.",
            agent=backend_dev,
            context=[task_plan],
        )

        task_frontend = Task(
            description=(
                "Crie os componentes de interface necessarios "
                "integrando com o backend recem-criado."
            ),
            expected_output="Arquivos de frontend (JS/TS/Flutter) gerados.",
            agent=frontend_dev,
            context=[task_backend],
        )

        task_test = Task(
            description=(
                "Execute a suite de testes em todo o incremento. "
                "Consulte .context/05_quality_and_gates.md para os "
                "criterios de qualidade. Reporte PASS/FAIL com detalhes."
            ),
            expected_output="Relatorio de QA com status PASS/FAIL.",
            agent=qa_engineer,
            context=[task_frontend],
        )

        task_deploy = Task(
            description=(
                "Verifique a saude da AWS e prepare o deploy " "do novo incremento."
            ),
            expected_output=("Relatorio de pre-deploy e execucao do deploy na AWS."),
            agent=devops_agent,
            context=[task_test],
            human_input=True,  # SECURITY: requires human "OK" for deploy
        )

        # --- ORCHESTRATION ---

        crew = Crew(
            agents=[
                manager,
                backend_dev,
                frontend_dev,
                qa_engineer,
                devops_agent,
            ],
            tasks=[
                task_plan,
                task_backend,
                task_frontend,
                task_test,
                task_deploy,
            ],
            process=Process.sequential,
            verbose=True,
        )

        return crew.kickoff()


if __name__ == "__main__":
    print("### Auraxis Multi-Agent System Activated ###")
    squad = AuraxisSquad()
    squad.run()

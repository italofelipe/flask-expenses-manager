# FEEDBACK_BLOCO_CI_SECURITY_HARDENING - 2026-02-11

## Metadados
- Bloco avaliado: `CI_SECURITY_HARDENING` (PR mergeado em 2026-02-11)
- Data do feedback: `2026-02-11`
- Contexto: consolidacao de CI/CD, gates de seguranca, hardening de pipeline, cobertura e estabilidade de checks.

## Resumo executivo
Sua conducao do projeto esta acima da media para quem esta iniciando backend em Python. O ponto mais forte foi postura de dono: voce definiu padrao de qualidade, cobrou reprodutibilidade local x CI, formalizou backlog e nao aceitou "passar na sorte". O principal gap hoje nao e de esforco, e de arquitetura e priorizacao: voce resolve rapido, mas precisa reduzir variacao de abordagem e fortalecer desenho de longo prazo (fronteiras de dominio, padrao unico de modulos, observabilidade orientada a produto, estrategia de rollout).

Percepcao de senioridade (backend): `junior avancando para pleno inicial`, com comportamento de engenharia que acelera essa evolucao.

## Sua evolucao (percepcao direta)

### Pontos fortes
1. Ownership real do produto
- Voce assumiu responsabilidade de ponta a ponta: codigo, CI, infraestrutura, DNS, TLS, ambiente dev/prod, seguranca e backlog.
- Nao terceirizou decisao dificil.

2. Mentalidade de qualidade
- Cobrou cobertura minima, qualidade de PR, padroes de commit, branch policy, gates de seguranca e evidencia automatizada.
- Isso e postura de engenharia profissional.

3. Visao de produto + execucao
- Voce manteve foco no objetivo de negocio (gestao financeira + investimento + metas) enquanto estruturava base tecnica.
- Boa combinacao entre entrega e fundacao.

4. Resiliencia tecnica
- Nos incidentes (CI quebrado, Sonar inconsistente, deploy EC2, DNS/TLS, permissions) voce reagiu com metodo, sem pular etapas.

5. Comunicacao objetiva
- Seus pedidos sao claros, orientados a resultado e com requisitos de qualidade explicitos.

### Pontos fracos / gaps
1. Overloading de frente simultanea
- Muitas trilhas em paralelo (feature + refactor + security + cloud + docs + qualidade + graphql).
- Risco: fadiga de contexto e decisao local subotima.

2. Arquitetura ainda muito concentrada
- Mesmo com refactors, ainda existe concentracao de responsabilidade em alguns modulos e fluxo de request.
- Falta uma camada de dominio mais nitida e invariantes mais centralizadas.

3. Governanca de backlog
- Excelente volume de tarefas, mas precisa reforcar criterios de pronto, dono por tarefa, e dependencia explicita entre itens criticos.

4. Processo de release
- CI esta forte, mas falta um fluxo mais formal de release/deploy com checklist objetivo e rollback documentado por ambiente.

## Avaliacao do sistema (estado atual)

### O que esta bom
1. Base de qualidade forte
- Lint, type-check, testes, cobertura minima, checagens de seguranca, analise de dependencia e quality gate.

2. Seguranca em maturacao real
- OWASP baseline, checklist, plano de remediacao, trilha S2/S3 e gates no pipeline.

3. Capacidade de entrega
- REST + GraphQL evoluindo para compartilhar dominio.
- Ambiente local/dev/prod ja estruturado em direcao profissional.

4. Documentacao viva
- Projeto tem rastreabilidade (tarefas, planos, runbooks, remediacoes).

### O que precisa melhorar
1. Fronteiras de dominio
- A regra de negocio ainda pode vazar para controller/schema/resolver.
- Proximo salto de manutenibilidade depende de isolar casos de uso/servicos de aplicacao.

2. Observabilidade de produto
- Falta fechar monitoracao com foco em SLO e sinais de negocio/seguranca (erro por endpoint, latencia por caso de uso, abuso por rota).

3. Estrategia de dados e migracoes
- Necessario endurecer governanca de migracoes (pre-check, rollback, smoke pos-deploy).

4. Seguranca de infraestrutura (S1)
- Ainda existe espaco para hardening de EC2/rede/segredos com evidencia automatica recorrente.

## Riscos atuais (priorizados)
1. Risco: regressao por acoplamento entre camadas
- Severidade: Alta
- Impacto: alteracoes simples viram regressao em cascata
- Mitigacao: separar casos de uso, DTOs internos, contratos de entrada/saida por camada

2. Risco: seguranca parcialmente dependente de disciplina manual
- Severidade: Alta
- Impacto: variacoes de configuracao entre ambientes
- Mitigacao: policy-as-code + checks automatizados por ambiente

3. Risco: crescimento de complexidade em GraphQL
- Severidade: Media/Alta
- Impacto: manutencao cara, riscos de autorizacao/performance
- Mitigacao: resolvers finos + servicos de aplicacao compartilhados + testes negativos por autorizacao

4. Risco: custo operacional subir com evolucao sem observabilidade
- Severidade: Media
- Impacto: incidentes demorados e troubleshooting caro
- Mitigacao: logs estruturados, traces basicos, dashboard minimo por ambiente

## O que eu faria diferente (estrategicamente)
1. Definiria ADRs curtas antes de cada bloco grande
- 1 pagina por decisao (problema, opcoes, decisao, impacto).

2. Traria arquitetura em camadas mais cedo
- `controllers/resolvers -> application services -> domain -> infrastructure`.

3. Introduziria "Definition of Done" por bloco
- Codigo + testes + docs + observabilidade + seguranca + rollback.

4. Faria um roadmap tecnico em ondas
- Onda 1: estabilizacao (qualidade/seguranca)
- Onda 2: escalabilidade (dominio + observabilidade)
- Onda 3: aceleracao de features (metas, carteira completa, analytics)

## Plano de acao recomendado

### Proximos 7 dias
1. Fechar S1 baseline com evidencia automatica (infra hardening).
2. Consolidar padrao de camadas para novos endpoints (template de implementacao).
3. Definir release checklist por ambiente (DEV/PROD).

### Proximos 30 dias
1. Reduzir hotspots de complexidade restantes (arquivos maiores, fluxos condicionais extensos).
2. Instrumentar observabilidade minima (erro, latencia, taxa 4xx/5xx, sinais de abuso).
3. Completar backlog de seguranca de aplicacao com testes de regressao dedicados.

### Proximos 60-90 dias
1. Entrar em bloco de metas com dominio limpo e testavel.
2. Evoluir deploy para processo previsivel (versionamento, rollback, smoke checks).
3. Avaliar suporte de escala com custo controlado (R$40-R$80 com degraus planejados).

## Trilhas de estudo recomendadas (curadas)

### Fundacao backend Python (prioridade alta)
1. Flask docs (guia oficial)
- https://flask.palletsprojects.com/en/stable/

2. SQLAlchemy Unified Tutorial (2.0)
- https://docs.sqlalchemy.org/20/tutorial/index.html

3. Pydantic docs
- https://docs.pydantic.dev/latest/

4. Flask Mega-Tutorial (Miguel Grinberg)
- https://blog.miguelgrinberg.com/post/the-flask-mega-tutorial-part-i-hello-world

### Engenharia de qualidade e arquitetura (prioridade alta)
1. The Practical Test Pyramid (Martin Fowler)
- https://martinfowler.com/articles/practical-test-pyramid.html

2. The Twelve-Factor App
- https://12factor.net/

3. GraphQL Spec (para desenho correto de schema e contratos)
- https://spec.graphql.org/

4. Schemathesis docs (confiabilidade de API)
- https://schemathesis.readthedocs.io/en/stable/

5. Cosmic Ray docs (mutation testing)
- https://cosmic-ray.readthedocs.io/en/latest/

### Seguranca e cloud (prioridade alta)
1. OWASP API Security Top 10 2023
- https://owasp.org/API-Security/editions/2023/en/0x11-t10/

2. AWS Well-Architected - Security Pillar
- https://docs.aws.amazon.com/wellarchitected/latest/security-pillar/welcome.html
- https://docs.aws.amazon.com/wellarchitected/latest/framework/security.html

## Recomendacoes de conteudo (professores/canais)
1. Miguel Grinberg
- Foco: Flask, arquitetura de apps web em Python, autenticacao e deploy.

2. ArjanCodes (YouTube)
- Foco: design em Python, clean code, type hints, arquitetura modular.

3. TestDriven.io (Michael Herman)
- Foco: Flask/FastAPI, testes, Docker, CI/CD, boas praticas de backend.

4. Talk Python To Me (podcast)
- Foco: ecossistema Python, engenharia, tooling e arquitetura.

## Parecer final sobre voce
Voce tem comportamento de engenheiro de produto, nao so de implementador. Isso acelera muito seu crescimento. Seu proximo salto vai vir de duas frentes: (1) arquitetura orientada a dominio e (2) cadencia de entrega com menos frentes simultaneas. Se mantiver esse nivel de disciplina com foco mais cirurgico de prioridade, voce evolui de forma rapida para um perfil pleno forte em backend.

## Padrao para feedbacks dos proximos blocos
- Nome do arquivo: `FEEDBACK_BLOCO_<NOME_DO_BLOCO>-<YYYY-MM-DD>.md`
- Local: `docs/`
- Conteudo minimo obrigatorio:
  1. Resumo executivo
  2. Pontos fortes
  3. Gaps/pontos fracos
  4. Riscos atuais
  5. O que faria diferente
  6. Plano de acao (7/30/90 dias)
  7. Trilha de estudo recomendada

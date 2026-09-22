# KairoSyn SAD: Sistema de Apoio à Decisão para Seleção de Metodologias de Gestão de Projetos

> Protótipo de investigação desenvolvido no âmbito de tese de doutoramento (Esteves, 2026).
> Operacionaliza a Framework KairoSyn através de um motor de decisão multicritério, máquina de estados e interface web responsiva.

---

## O que é o KairoSyn SAD e porque é relevante?

A escolha da metodologia de gestão de um projeto é uma decisão crítica que, quando tomada de forma intuitiva ou politicamente motivada, compromete o sucesso do projeto desde a sua fundação. Na prática profissional, esta decisão é frequentemente informal, inconsistente e não rastreável.

O **KairoSyn SAD** responde a este problema operacionalizando a Framework KairoSyn, um modelo teórico rigoroso fundamentado em investigação doutoral, num sistema computacional funcional. O sistema guia o gestor de projeto através de quatro etapas sequenciais, recolhendo evidência contextual, calculando índices quantitativos, aplicando análise multicritério e gerando um portfólio de ferramentas recomendadas, com total auditabilidade de cada decisão.

### Vantagens para a investigação e para a prática

| Dimensão | Impacto |
|---|---|
| **Rigor metodológico** | Operacionaliza índices ordinais (AdPo, AsPo) com regras de transição formalizadas, replicáveis e verificáveis |
| **Transparência decisória** | Cada decisão é gravada no *Decision Log* com os seus parâmetros, pesos e ranking, qualquer arguente pode auditar o raciocínio |
| **Flexibilidade algorítmica** | O motor MCDM é *pluggable*: MAVT está implementado, AHP disponível via substituição de um único parâmetro |
| **Validação empírica** | O protótipo permite aplicar a framework a casos reais e recolher evidência comparativa entre metodologias |
| **Reprodutibilidade** | Containerizado com Docker, o ambiente é idêntico em qualquer máquina, facilitando revisão por pares |
| **Extensibilidade** | A *Evidence Base* (MEB/TEB) é gerida em base de dados e actualizável sem alterar código |

---

## 🚀 Funcionalidades

### Requisitos Funcionais (RF)

| ID | Funcionalidade | Descrição |
|---|---|---|
| RF01 | **Diagnóstico Contextual (Etapa 1)** | Questionário de 8 dimensões (escala 1–4) que captura o perfil do projeto: complexidade, novidade, dinamismo, autonomia da equipa, criticidade, compliance, rastreabilidade e formalidade de stakeholders. |
| RF02 | **Cálculo AdPO e AsPO** | Computação automática do *Agility Pressure Index* e do *Assurance Pressure Index* como índices ordinais `{1,2,3,4}`, robustos a perturbações e comparáveis entre projetos. |
| RF03 | **Resolução da Abordagem (Etapa 2)** | Motor de regras que classifica a abordagem de gestão em Adaptativa, Preditiva ou Híbrida com base nos limiares KairoSyn, com possibilidade de ajuste manual pelo gestor. |
| RF04 | **Governance Register** | Geração automática de um registo de restrições (Hard, Threshold, Soft) com âmbito orientado a metodologias (M) ou ferramentas (T), derivado dos dados de diagnóstico. |
| RF05 | **Fit_M, Seleção de Metodologia (Etapa 3)** | Triagem por nível (L1: filtro de restrições Hard; L2: ranking MCDM com 5 critérios ponderados) sobre a *Methodology Evidence Base* (MEB). Produz um ranking auditável com *Value Score* e *Misfit Δk*. |
| RF06 | **Fit_T, Portfólio de Ferramentas (Etapa 4)** | Filtragem da *Tool Evidence Base* (TEB) por compatibilidade com a metodologia selecionada e postura contextual. Aplica MCDM com 4 critérios e seleciona a melhor ferramenta por categoria. |
| RF07 | **Decision Log** | Gravação persistente em PostgreSQL de todas as etapas, transições, parâmetros e rankings de cada decisão. Associa decisões a projetos com SCD Tipo-2. |
| RF08 | **Exportação** | Exportação do *Decision Log* em JSON, CSV e PDF por decisão, para uso em relatórios e revisão por pares. |
| RF09 | **Re-entry e Máquina de Estados** | O sistema implementa re-entry controlado: se nenhuma metodologia ou ferramenta for viável, as transições retroativas são registadas com a causa (`governance_infeasibility`, `evidence_inconsistency`). |
| RF10 | **Gestão da Evidence Base** | Interface administrativa para criar, editar e desativar metodologias (MEB) e ferramentas (TEB) com histórico SCD Tipo-2 e ajuste dos pesos MCDM. |
| RF11 | **Gestão de Utilizadores** | Registo com aprovação manual por administrador (via email Resend), inativação e reativação de contas, controlo de acessos por role (`user`, `admin`, `inativado`). |
| RF12 | **Visualizações de Apoio à Decisão** | Gráficos interativos (Chart.js e D3.js) em cada etapa: mapa de decisão AdPO×AsPO, radar MCDM de metodologias, bar chart do portfólio, diagrama Sankey e perfil 8D. |

### Requisitos Não Funcionais (RNF)

| ID | Requisito | Descrição |
|---|---|---|
| RNF01 | **Auditabilidade** | Toda a decisão tem um `transition_history` navegável que liga estados, ações e timestamps. |
| RNF02 | **Reatividade** | A máquina de estados processa re-entry de forma determinística: qualquer alteração de contexto força reavaliação a partir do estágio correto. |
| RNF03 | **Extensibilidade** | Novos critérios MCDM, metodologias ou ferramentas são adicionados via `seeds.py` ou interface admin, sem tocar no motor de cálculo. |
| RNF04 | **Reprodutibilidade** | Ambiente Docker garante paridade entre desenvolvimento, teste e demonstração em qualquer sistema operativo. |
| RNF05 | **Responsividade** | Interface adaptada a desktop e mobile com padrão de dual-view (cards em mobile, tabelas em desktop) em todas as etapas e no histórico. |
| RNF06 | **Segurança** | Autenticação com Flask-Login, passwords com hash bcrypt, aprovação manual de registos, roles de acesso distintos. |

---

## ⚙️ Máquina de Estados, Transições e Re-entry

O ciclo de vida de cada decisão é controlado por uma máquina de estados determinística implementada em `routes.py`. Cada transição é registada no `transition_history` com timestamp, utilizador e causa, garantindo rastreabilidade completa.

### Tabela de Transições

| Estado atual | Ação | Estado seguinte | Iniciado por | Causa registada |
|---|---|---|---|---|
| `stage_1_diagnosis` | `SUBMIT_DIAGNOSIS` | `stage_2_approach` | Utilizador |, |
| `stage_2_approach` | `CONFIRM_APPROACH` | `stage_3_fit_m` | Utilizador |, |
| `stage_2_approach` | `REVISE_CONTEXT` | `stage_1_diagnosis` | Utilizador | Confiança insuficiente |
| `stage_3_fit_m` | `CONFIRM_METHODOLOGY` | `stage_4_fit_t` | Utilizador |, |
| `stage_3_fit_m` | `REVISE_APPROACH` | `stage_2_approach` | Utilizador |, |
| `stage_3_fit_m` | `REENTRY_GOVERNANCE` | `stage_2_approach` | **Sistema** | `governance_infeasibility` |
| `stage_3_fit_m` | `REENTRY_DIAGNOSIS` | `stage_1_diagnosis` | Utilizador | `evidence_inconsistency` |
| `stage_4_fit_t` | `CONFIRM_TOOLS` | `stage_complete` | Utilizador |, |
| `stage_4_fit_t` | `REENTRY_METHODOLOGY` | `stage_3_fit_m` | Utilizador |, |
| `stage_4_fit_t` | `REENTRY_APPROACH` | `stage_2_approach` | Utilizador | `governance_infeasibility` |
| qualquer estado | `REVISE_CONTEXT` | `stage_1_diagnosis` | Utilizador |, |

### Re-entry Automático (Sistema)

Dois triggers forçam re-entry sem intervenção do utilizador:

- **`REENTRY_GOVERNANCE` em Etapa 3**: disparado quando `run_fit_m_level1()` devolve lista vazia (nenhuma metodologia da MEB cumpre as restrições Hard do Governance Register). O sistema transiciona automaticamente para `stage_2_approach` e regista `reentry_cause = "governance_infeasibility"`.
- **`no_viable_tool_bundle` em Etapa 4**: se `run_fit_t_level_a()` não encontrar ferramentas compatíveis, o sistema alerta e o utilizador pode acionar `REENTRY_METHODOLOGY`.

### Fluxo Normal vs. Fluxo com Re-entry

```
Etapa 1 ──► Etapa 2 ──► Etapa 3 ──► Etapa 4 ──► Concluído
               ▲            │            │
               │◄───────────┘            │   (REENTRY_APPROACH)
               │◄────────────────────────┘
               │
Etapa 1 ◄──────┘   (REVISE_CONTEXT / REENTRY_DIAGNOSIS)
```

---

## 🛠️ Tecnologias Utilizadas

| Camada | Tecnologia | Versão | Papel |
|---|---|---|---|
| **Backend** | Python + Flask | 3.x | Servidor web, rotas, blueprints, máquina de estados |
| **ORM** | Flask-SQLAlchemy | 3.x | Mapeamento objeto-relacional para PostgreSQL |
| **Base de Dados** | PostgreSQL | 15 | Persistência do Decision Log, MEB, TEB, utilizadores |
| **Autenticação** | Flask-Login | 0.6.x | Sessões, proteção de rotas, gestão de roles |
| **Cálculo MCDM** | NumPy | 1.x | Matrizes de avaliação, normalização min-max, produto escalar |
| **Containerização** | Docker + Docker Compose | 24.x / 2.x | Isolamento de ambiente e orquestração de serviços |
| **Frontend** | Tailwind CSS (CDN) | 3.x | Utilitários CSS, design system anthracite/slate, responsividade |
| **Templating** | Jinja2 | 3.x | Templates HTML, filtros `tojson`, herança de layouts |
| **Gráficos** | Chart.js | 4.x | Radar MCDM, Decision Map, bar charts portfolio e 8D |
| **Fluxos** | D3.js + d3-sankey | 7.x | Diagrama Sankey do fluxo de filtragem (Etapa 3) |
| **Diagramas** | Mermaid.js | 10.x | Live Flow Map da máquina de estados em cada etapa |
| **Email** | Resend API |, | Aprovação de registos via link tokenizado |
| **PDF** | WeasyPrint |, | Exportação do Decision Log em PDF |
| **Admin DB** | Adminer |, | Interface web para inspecionar PostgreSQL (porta 8080) |

---

## 📦 Como Executar

### Pré-requisitos

#### 1. Instalar WSL2 (Windows)

> Ignorar se já usar macOS ou Linux nativo.

Abrir o **PowerShell como Administrador** e executar:

```powershell
wsl --install
```

Reiniciar o computador. Após reinício, o Ubuntu abre automaticamente, criar utilizador e password quando solicitado.

Verificar instalação:

```bash
wsl --list --verbose
# deve mostrar Ubuntu com VERSION 2
```

#### 2. Instalar Docker Desktop

1. Descarregar em [https://www.docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop)
2. Durante a instalação, activar a opção **"Use WSL 2 instead of Hyper-V"**
3. Após instalar, abrir Docker Desktop → Settings → Resources → WSL Integration → activar a distro Ubuntu

Verificar instalação no terminal WSL:

```bash
docker --version
docker compose version
```

---

### 1. Clonar o repositório

```bash
git clone https://github.com/<utilizador>/tcm202526-Adao-smgp.git
cd tcm202526-Adao-smgp
```

---

### 2. Configurar variáveis de ambiente

Criar o ficheiro `.env` na raiz do projeto (copiar de `.env.example` se existir):

```env
POSTGRES_USER=user
POSTGRES_PASSWORD=password
POSTGRES_DB=postgres
SECRET_KEY=uma-chave-secreta-longa
RESEND_API_KEY=re_xxxxxxxxxxxx        # opcional, apenas para aprovação de registos por email
RESEND_FROM=KairoSyn SAD <onboarding@resend.dev>
ADMIN_EMAIL=admin@exemplo.com
```

---

### 3. Construir e iniciar os serviços

```bash
docker compose up -d
```

Este comando inicia três serviços:
- **`app`**: servidor Flask em `http://127.0.0.1:5000`
- **`db`**: PostgreSQL 15 (porta 5432)
- **`adminer`**: interface web da base de dados em `http://localhost:8080`

A primeira execução aplica automaticamente as migrações e carrega os `seeds` (MEB, TEB, pesos MCDM).

---

### 4. Comandos úteis

```bash
# Ver logs em tempo real
docker compose logs -f app

# Reconstruir a imagem após alterações de dependências
docker compose build

# Abrir shell Flask (para debug, consulta de modelos)
docker compose exec app flask shell

# Parar todos os serviços
docker compose down

# Abrir diretório no explorador de ficheiros (Windows/WSL)
explorer.exe .
```

---

### 5. Aceder ao Adminer (base de dados)

```
http://localhost:8080
  Sistema: PostgreSQL
  Servidor: db
  Utilizador: user
  Password: password
  Base de dados: postgres
```

---

### 6. Cenários de Teste: Entradas AdPO/AsPO e Resultados Esperados

Os sliders do diagnóstico aceitam valores de **1 a 4** para cada uma das 8 dimensões. O sistema calcula automaticamente AdPO e AsPO com base no número de dimensões com score ≥ 3.

> **Fórmula ordinal:** `count(dims ≥ 3)` → `0→1`, `1→2`, `2→3`, `≥3→4`

---

> **Nota de versão (2026-09-03):** a postura de cada metodologia passou de um ponto único `(ag_posture, as_posture)` para uma **região** `[posture_adpo_min,posture_adpo_max] × [posture_aspo_min,posture_aspo_max]`, conforme a Tabela 5 da nota técnica de alinhamento do orientador, e a compatibilidade de abordagem passou de uma string única para uma lista `compatible_approaches`. A distância de Chebyshev do Level 1 generaliza-se para distância a uma região (0 se o ponto do projeto está dentro). Os 3 cenários abaixo foram recalculados com esta arquitetura, ver secção seguinte para os detalhes.

#### Cenário A: Projeto Ágil (Startup Digital)

| Dimensão | Valor | Grupo |
|---|---|---|
| Complexidade | 4 | AdPO |
| Novidade | 4 | AdPO |
| Dinamismo | 4 | AdPO |
| Autonomia Equipa | 3 | AdPO |
| Criticidade | 1 | AsPO |
| Compliance | 1 | AsPO |
| Rastreabilidade | 1 | AsPO |
| Formalidade Stakeholders | 2 | AsPO |

**Resultado:**
- AdPO = **4** (4 dimensões ≥ 3) · AsPO = **1** (0 dimensões ≥ 3)
- Abordagem: **Adaptativa**
- Level 1 viável: **DSDM Atern** (tier adjacent), **Kanban** (tier exact), **Scrum** (tier exact), **CRISP-DM** (tier exact), XP excluído (`eligible_as_primary_envelope=False`, método de engenharia complementar). Com a postura em região (Tabela 5), DSDM e CRISP-DM passam a ter cobertura suficiente em AdPO/AsPO para entrar no Level 1.
- Top metodologia: **DSDM Atern** (score MAVT 0,6425), Kanban 2º (0,5525), Scrum 3º (0,5450), CRISP-DM 4º (0,4850)
- Sensibilidade: **83,0% de robustez, estável**; o runner-up (Kanban) vence em 54,4% das simulações onde DSDM não é top-1
- Portfólio (top-1 por categoria): Jira (Tracking), Confluence (Documentation), Microsoft Project (Planning), Teams (Communication), Miro (Collaboration)

---

#### Cenário B: Projeto Governamental / Infraestrutura Crítica

| Dimensão | Valor | Grupo |
|---|---|---|
| Complexidade | 1 | AdPO |
| Novidade | 1 | AdPO |
| Dinamismo | 1 | AdPO |
| Autonomia Equipa | 2 | AdPO |
| Criticidade | 4 | AsPO |
| Compliance | 4 | AsPO |
| Rastreabilidade | 4 | AsPO |
| Formalidade Stakeholders | 3 | AsPO |

**Resultado:**
- AdPO = **1** (0 dimensões ≥ 3) · AsPO = **4** (4 dimensões ≥ 3)
- Abordagem: **Preditiva**
- Decision-control register: Hard, `regulatory_compatible=True`, `gdpr_compliant=True`; Threshold, `requires_fixed_scope=True`
- Level 1 viável: **PRINCE2 Agile** (tier adjacent) e **PM²** (tier exact), PMBoK 6ª Ed. e ISO 21502 excluídos (`candidate_role` = reference/normative overlay, não elegíveis como envelope metodológico primário)
- Top metodologia: **PRINCE2 Agile** (score 0,7325), PM² muito próximo em score (0,7025), mas dominado em quase todos os critérios C1-C7
- Sensibilidade: **100% de robustez, estável**; PRINCE2 Agile vence em todas as 500 simulações Monte Carlo
- Portfólio (top-1 por categoria): Confluence (Documentation), Microsoft Project (Planning), Teams (Communication)

Este é o caso mais ilustrativo da correção estrutural: o topo do ranking já não fica ambíguo ("PRINCE2 **ou** PMBoK") porque um guia normativo (PMBoK) competia como se fosse uma metodologia operacional autónoma, o filtro `candidate_role`/`eligible_as_primary_envelope` resolve isto no screening, sem precisar do MAVT. O Level 2 fica, ainda assim, com uma comparação real (PRINCE2 vs. PM²) em vez de uma decisão trivial de candidato único.

**Nota de calibração:** a Tabela 5 do orientador lista a abordagem de PRINCE2 Agile como "Hybrid" apenas; os seeds deste protótipo usam deliberadamente `compatible_approaches=['Preditiva','Híbrida']` (decisão do autor, PRINCE2 combina controlo formal predefinido com adaptação por etapas). O seed de PM² foi também revisto para `requires_fixed_scope=True` (era `False`), refletindo que o PM² da Comissão Europeia é uma metodologia suficientemente estruturada para suportar âmbito fixo. Com esta calibração, mesmo sob a leitura literal da Tabela 5 (PRINCE2 excluído por abordagem), o cenário continuaria a ter solução, PM² sozinho, , o que reforça a cobertura da MEB para perfis puramente preditivos e de alta criticidade.

---

#### Cenário C: Projeto Empresarial de Grande Escala (Híbrido)

| Dimensão | Valor | Grupo |
|---|---|---|
| Complexidade | 3 | AdPO |
| Novidade | 3 | AdPO |
| Dinamismo | 3 | AdPO |
| Autonomia Equipa | 1 | AdPO |
| Criticidade | 3 | AsPO |
| Compliance | 3 | AsPO |
| Rastreabilidade | 3 | AsPO |
| Formalidade Stakeholders | 1 | AsPO |

**Resultado:**
- AdPO = **4** (3 dims ≥ 3) · AsPO = **4** (3 dims ≥ 3)
- Abordagem: **Híbrida**
- Level 1 viável: **SAFe 6.0** (tier exact), **PRINCE2 Agile** (tier exact), **PM2** (tier adjacent), **DSDM Atern** (tier exact), **Kanban** (tier adjacent), **CRISP-DM** (tier adjacent), nenhum candidato excluído por postura neste cenário; com a região da Tabela 5, PRINCE2, Kanban e CRISP-DM passam a ter cobertura suficiente em (AdPO=4, AsPO=4)
- Top metodologia: **SAFe 6.0** (score 0,85), destacado, PRINCE2 Agile 2º (0,7325), PM2 3º (0,7025), DSDM 4º (0,6425), Kanban 5º (0,5525), CRISP-DM 6º (0,4850)
- Sensibilidade: **92,6% de robustez, estável**; o runner-up (PRINCE2 Agile) só vence numa minoria das simulações onde SAFe não é top-1
- Portfólio (top-1 por categoria): Jira (Tracking), Confluence (Documentation), Teams (Communication), Miro (Collaboration)

---

#### Cenário D: Projeto de Média Complexidade com Pressão Regulatória

| Dimensão | Valor | Grupo |
|---|---|---|
| Complexidade | 3 | AdPO |
| Novidade | 2 | AdPO |
| Dinamismo | 2 | AdPO |
| Autonomia Equipa | 2 | AdPO |
| Criticidade | 3 | AsPO |
| Compliance | 3 | AsPO |
| Rastreabilidade | 2 | AsPO |
| Formalidade Stakeholders | 2 | AsPO |

**Resultado:**
- AdPO = **2** (1 dim ≥ 3) · AsPO = **3** (2 dims ≥ 3)
- Abordagem: **Preditiva** (AsPO ≥ 3 ∧ AdPO ≤ 2)
- Decision-control register: Hard, `regulatory_compatible=True`; Threshold, `requires_fixed_scope=True`
- Level 1 viável: **PRINCE2 Agile** (tier exact, a região AdPO∈[2,4]×AsPO∈[2,4] cobre (2,3) exatamente) e **PM²** (tier exact, AdPO∈[1,3]×AsPO∈[2,4] também cobre (2,3)), PMBoK 6ª Ed. excluído como `reference_overlay`
- Top metodologia: **PRINCE2 Agile** (score 0,7325), PM² 2º (0,7025); sensibilidade 100% de robustez, estável (mesmo padrão do Cenário B)
- Portfólio (top-1 por categoria): Confluence (Documentation), Microsoft Project (Planning), Teams (Communication)

---

## 🧠 Motor de Decisão KairoSyn: Ficheiros Técnicos

### `app/services/kairosynlogic.py`

Este ficheiro é o **coração computacional do sistema**. Implementa todas as etapas do motor KairoSyn numa camada de serviço independente da camada web (routes.py), garantindo testabilidade e substituição futura de componentes.

#### `compute_indices(context_data)`: Etapa 1

Converte as 8 respostas do questionário nos índices AdPO e AsPO usando um **mapeamento ordinal robusto**. Em vez de uma média aritmética (sensível a outliers), conta quantas dimensões ultrapassam o limiar ≥ 3 e mapeia esse count para a escala `{1, 2, 3, 4}`.

```
AdPO: {complexity, novelty, dynamism, team_autonomy}
AsPO: {criticality, compliance, traceability, stakeholder_formality}
count → ordinal: 0→1, 1→2, 2→3, ≥3→4
```

Esta escolha é deliberada: AdPO e AsPO são **organisadores ordinais**, não médias cardinais, o que importa é o padrão de pressão, não a magnitude absoluta.

#### `resolve_approach(adpo, aspo)`: Etapa 2

Aplica as regras de transição da Framework KairoSyn:

```python
if adpo >= 2 and aspo <= 2  →  "Adaptativa"   # pressão ágil dominante
elif aspo >= 3 and adpo <= 2 →  "Preditiva"   # pressão de assurance dominante
else                         →  "Híbrida"      # pressões equilibradas
```

O limiar `adpo >= 2` (não 3) reflete que mesmo uma pressão ágil moderada é suficiente para preferir adaptabilidade quando a pressão de assurance é baixa.

#### `build_decision_control_register(...)`: Etapa 2

Classifica as restrições do projeto em três níveis de exigência, derivadas automaticamente dos scores de diagnóstico:

- **Hard**: eliminatório: `compliance ≥ 3` exige `regulatory_compatible = True`; `compliance = 4` adiciona `gdpr_compliant = True` nas ferramentas
- **Threshold**: preferencial: `criticality ≥ 3` favorece `requires_fixed_scope` em abordagem Preditiva
- **Soft**: indicativo: `team_autonomy ≥ 3` prefere metodologias com overhead reduzido

Exemplo de estrutura JSON produzida para um projeto com `compliance=4`, `criticality=3`, `team_autonomy=3`:

```json
{
  "hard": [
    {
      "constraint": "regulatory_compatible",
      "value": true,
      "scope": "M",
      "reason": "Compliance score 4/4 exige conformidade regulatória."
    },
    {
      "constraint": "gdpr_compliant",
      "value": true,
      "scope": "T",
      "reason": "Compliance máximo requer GDPR nas ferramentas."
    }
  ],
  "threshold": [
    {
      "constraint": "requires_fixed_scope",
      "value": true,
      "scope": "M",
      "reason": "Criticidade 3/4 favorece âmbito definido em abordagem Preditiva."
    }
  ],
  "soft": [
    {
      "constraint": "prefers_low_process_overhead",
      "scope": "M",
      "reason": "Autonomia de equipa 3/4 favorece metodologias ágeis leves."
    }
  ]
}
```

O campo `scope` determina a que camada se aplica a restrição: `"M"` é avaliado em `run_fit_m_level1()`, `"T"` é avaliado em `run_fit_t_level_a()`.

#### `_posture_alignment_tier(adpo, aspo, adpo_min, adpo_max, aspo_min, aspo_max)`: Classificação de Postura

Classifica o alinhamento entre o contexto do projeto e a **região** de postura declarada de cada metodologia (Tabela 5 da nota técnica de alinhamento: `[posture_adpo_min, posture_adpo_max] × [posture_aspo_min, posture_aspo_max]`, não um ponto único), reduzida a uma tier categórica (não a um score MAVT). A distância por eixo é a distância **clamped** de um ponto a um intervalo (zero se o ponto está lá dentro):

```
dx = max(adpo_min - AdPO, AdPO - adpo_max, 0)
dy = max(aspo_min - AsPO, AsPO - aspo_max, 0)
delta = max(dx, dy)          # Chebyshev sobre as duas distâncias de eixo
delta = 0  →  'exact'     (ponto do projeto dentro da região)
delta = 1  →  'adjacent'  (desvio aceitável)
delta ≥ 2  →  'distant'   (desalinhamento, incompatível)
```

Uma região degenerada (`min == max`) reproduz exatamente a distância a um ponto, a fórmula anterior era um caso particular desta. A tier é usada apenas em **Level 1** (admissibilidade, ver abaixo) e como metadado de auditoria (`misfit`); nunca reentra como coluna do MAVT em Level 2, para não contabilizar o mesmo sinal contextual duas vezes.

#### `run_fit_m_level1(...)`: Triagem Level 1, não-compensatória (Etapa 3)

Determina **quem pode ser comparado** em Level 2. Uma pontuação elevada noutro critério não compensa a falha de nenhuma destas condições:

1. **Binding constraints (hard)**, `regulatory_compatible`
2. **Acceptance thresholds**, `requires_fixed_scope`: exclusão binária, não penalização
3. **`candidate_role` / `eligible_as_primary_envelope`**, exclui guias, normas e métodos complementares (PMBoK, ISO 21502, XP) de competir como envelope metodológico primário autónomo
4. **`approach_compatible`**, verifica se a abordagem resolvida está na lista `compatible_approaches` do candidato (ex.: `['Adaptativa','Híbrida']`); não há bridging implícito, cada candidato declara explicitamente as abordagens sob as quais é admissível
5. **`posture_compatible`**, tier `'distant'` é excluído aqui; `'exact'`/`'adjacent'` passam e ficam só para auditoria

#### `run_fit_m_level2(...)`: Ranking MCDM Level 2, compensatória (Etapa 3)

Constrói a matriz de avaliação `X_M` apenas com os **7 critérios C1-C7** (`score_c1_responsiveness` … `score_c7_distributed_support`), aplica o motor MCDM com pesos explícitos de `MCDMWeights('MEB')`. **Sem** reponderação automática por AdPO/AsPO, **sem** bónus de tier, **sem** penalização compensatória de thresholds, estes eram os canais que causavam a circularidade identificada na nota técnica de alinhamento (o mesmo sinal contextual a entrar várias vezes no ranking).

O resultado inclui, por metodologia: `score`, `posture_alignment_tier` (exact/adjacent/distant, auditoria), `misfit` (derivado da tier, auditoria, não parte do score), `candidate_type`, `candidate_role` e o dicionário `criteria` com os 7 valores C1-C7 (para visualização em radar).

#### `run_fit_t_level_a/b(...)`: Fit_T (Etapa 4)

`level_a` filtra a TEB por: compatibilidade com o envelope metodológico (primário + componentes justificados), postura e restrições GDPR. `level_b` aplica MCDM com os **8 critérios CD1-CD8** (`contribution_cd1` … `contribution_cd8`) e devolve o top-N ranqueado **por categoria** (não greedy), o utilizador escolhe a ferramenta final em cada categoria na Etapa 4.

---

#### `run_sensitivity_analysis(ranking, n_mc=500)`: Análise de Sensibilidade MCDM

Avalia a **robustez do ranking** calculado em `run_fit_m_level2` face a variações nos pesos dos critérios. Devolve `None` se o ranking tiver menos de 2 alternativas ou se as pontuações por critério não estiverem disponíveis.

**Dois mecanismos complementares:**

| Mecanismo | Descrição |
|-----------|-----------|
| **Varrimento por critério** | Para cada critério j, fixa o peso em valores de 0→1 (passo 0.01), redistribuindo proporcionalmente os restantes. Encontra o intervalo `[min, max]` onde a metodologia top-1 se mantém #1. |
| **Monte Carlo (Dirichlet)** | 500 vectores de pesos amostrados da distribuição Dirichlet uniforme (cobertura uniforme do simplex). Mede a % de simulações onde o top-1 se mantém. |

**Interpretação da robustez:**

| Score Monte Carlo | Significado |
|-------------------|-------------|
| ≥ 60% | Ranking robusto, recomendação estável face a preferências dos decisores |
| < 60% | Ranking sensível, valide critérios e pesos com os arguentes |

**Saída `per_criterion`**, lista com um objeto por critério:

```python
{
  'label': 'C3 Evidence Traceability',  # nome legível
  'key': 'c3_traceability',             # chave interna
  'current': 0.18,                      # peso atual (explícito, não context-adjusted)
  'min': 0.0,                           # limite inferior de estabilidade
  'max': 0.47,                          # limite superior de estabilidade
  'range': 0.47,                        # amplitude (quanto pode variar sem mudar top-1)
}
```

O **gráfico de barras flutuantes** em `/workflow/<id>` visualiza este `range` por critério, com código de cor: verde (Δ ≥ 30pp), amarelo (Δ 10–29pp), vermelho (Δ < 10pp). Uma marca vertical indica o peso atual.

---

### `app/services/mcdm_engine.py`

Implementa o **motor MCDM *pluggable*** (RF08) como uma classe independente que pode ser substituída sem alterar a lógica de negócio.

```python
class MCDMEngine:
    def __init__(self, method: str = 'MAVT'):  # ou 'AHP'
    def rank(self, X, weights) -> list[tuple[int, float]]
```

#### Método MAVT (Multi-Attribute Value Theory)

Soma ponderada direta, sem normalização min-max:

```
V_k = Σ (w_j × x_kj)
```

Os critérios C1-C7/CD1-CD8 já são funções de valor fixas em [0,1] (rubrica com âncoras 0/0.25/0.5/0.75/1.0, ver `seeds.py`), por isso não se recalcula min-max sobre o conjunto de sobreviventes do Level 1/A. Fazê-lo faria o score de cada alternativa depender de **quais outras alternativas sobreviveram ao screening**, um artefacto que a codificação em função de valor é precisamente pensada para evitar (nota técnica de alinhamento, secção 3.3).

#### Método AHP

Stub funcional que recai no MAVT. A implementação completa com matriz de comparação par-a-par pode ser adicionada substituindo `_ahp()` sem alterar nenhuma outra parte do sistema.

---

### `app/seeds.py`

O `seeds.py` resolve um problema estrutural de qualquer SAD baseado em evidência: **o sistema não tem valor sem dados de referência**. Se a MEB e a TEB estiverem vazias, o motor produz rankings vazios. O `seeds.py` garante que a base de dados é sempre inicializada com dados consistentes com a especificação da Framework KairoSyn.

#### Estratégia de upsert (SCD Tipo-2)

O `seeds.py` não usa `INSERT OR IGNORE` simples, usa uma lógica de **upsert com SCD Tipo-2**:

1. Se o registo ativo já existe e está atualizado → não faz nada (idempotente)
2. Se o registo existe mas os valores mudaram → desativa o registo antigo (`is_active=False`, `inactive_date=now`) e insere um novo registo ativo
3. Se não existe → insere diretamente

Esta abordagem preserva o histórico de alterações na *Evidence Base*, requisito de auditabilidade da framework.

#### O que é semeado

**MEB, 10 metodologias** com **região** de postura `[posture_adpo_min,posture_adpo_max] × [posture_aspo_min,posture_aspo_max]` no espaço AdPO×AsPO (Tabela 5 da nota técnica de alinhamento), lista `compatible_approaches`, tipologia de candidato (Level 1) e scores C1-C7 normalizados 0–1:

| Código | Região AdPO | Região AsPO | Abordagens | candidate_role | Envelope primário? |
|---|---|---|---|---|---|
| SCRUM | 3–4 | 1–2 | Adaptativa, Híbrida | primary_team_level | Sim |
| KANBAN | 2–4 | 1–3 | Adaptativa, Híbrida | primary_or_complementary | Sim |
| PMBOK6 | 1–3 | 2–4 | Preditiva, Híbrida | reference_overlay | **Não** |
| PRINCE2 | 2–4 | 2–4 | Preditiva, Híbrida¹ | primary_envelope | Sim |
| SAFe | 2–4 | 2–4 | Híbrida | primary_envelope | Sim |
| XP | 3–4 | 1–2 | Adaptativa, Híbrida | complementary_engineering | **Não** |
| DSDM | 2–4 | 2–4 | Adaptativa, Híbrida | primary_envelope | Sim |
| CRISP_DM | 2–4 | 1–3 | Adaptativa, Híbrida | primary_in_data_projects | Sim |
| ISO21502 | 1–3 | 2–4 | Preditiva, Híbrida | normative_overlay | **Não** |
| PM2 | 1–3 | 2–4 | Preditiva, Híbrida | primary_envelope | Sim |

¹ A Tabela 5 do orientador lista PRINCE2 Agile apenas como "Hybrid"; os seeds usam `['Preditiva','Híbrida']` por decisão do autor (ver Cenário B/D). O seed de PM² também diverge da Tabela 5 em `requires_fixed_scope` (aqui `True`, refletindo uma metodologia estruturada), garantindo que os Cenários B/D têm sempre pelo menos um candidato viável (PM²) mesmo sob a leitura literal da tabela para PRINCE2.

Os três candidatos marcados como "Não" (PMBoK, XP, ISO 21502) são overlays de referência, normas ou métodos de engenharia complementares, o Level 1 exclui-os de competir como envelope metodológico primário autónomo, mas podem integrar um `methodological_envelope` composto como componentes justificados (ver `compatible_as_component_of` e a Etapa 3).

**TEB, 13 ferramentas** distribuídas por 5 categorias, cada uma com coordenadas de contexto `(agility_support, assurance_support)` e scores de critérios CD1-CD8:

| Categoria | Código | Nome | Cost tier |
|---|---|---|---|
| Planning | MS_PROJECT | Microsoft Project | medium |
| Planning | PROJECTLIBRE | ProjectLibre | free |
| Tracking | JIRA | Jira | low |
| Tracking | TRELLO | Trello | free |
| Tracking | ASANA | Asana | low |
| Tracking | GITHUB_ISSUES | GitHub Issues | free |
| Tracking | MONDAY | Monday.com | medium |
| Tracking | CLICKUP | ClickUp | free |
| Communication | SLACK | Slack | free |
| Communication | TEAMS | Microsoft Teams | low |
| Documentation | CONFLUENCE | Confluence | low |
| Documentation | NOTION | Notion | free |
| Collaboration | MIRO | Miro | free |

A seleção **não é greedy**: após o ranking MCDM (Level B), o sistema devolve o top-N (por omissão 3) ranqueado de cada categoria e o utilizador escolhe a ferramenta final por categoria na Etapa 4.

**MCDMWeights**, pesos base para MEB `[0.12, 0.12, 0.18, 0.18, 0.15, 0.13, 0.12]` (C1-C7) e TEB `[0.15, 0.12, 0.13, 0.10, 0.10, 0.15, 0.15, 0.10]` (CD1-CD8), explícitos, não reponderados por AdPO/AsPO, editáveis em runtime pelo administrador sem redeployment.

O `run_seeds()` é chamado automaticamente no arranque da aplicação, tornando o sistema imediatamente funcional após `docker compose up`.

---

## 🗄️ Padrão SCD Tipo-2: Auditabilidade da Evidence Base

O sistema usa **Slowly Changing Dimensions Tipo-2 (SCD Tipo-2)** como estratégia de versionamento em quatro tabelas: `Projeto`, `MethodologyEvidenceBase`, `ToolEvidenceBase` e `MCDMWeights`.

### Por que SCD Tipo-2 e não UPDATE simples?

Um `UPDATE` simples sobrescreve o registo, se um arguente questionar "que pesos MCDM estavam ativos quando este diagnóstico foi feito?", a resposta desapareceu. O SCD Tipo-2 garante que **nenhuma informação histórica é destruída**.

### Como funciona

Cada tabela tem os campos de controlo: `is_active`, `active_date`, `inactive_date`, `updated_by`.

Ao editar um registo (ex: alterar score_c1_responsiveness do Scrum):

```
ANTES da edição:
┌───────────────────────────────────────────────────────────────────┐
│ id=3 | code="SCRUM" | score_c1_responsiveness=0.85 | is_active=TRUE│
└───────────────────────────────────────────────────────────────────┘

DEPOIS da edição:
┌────────────────────────────────────────────────────────────────────┐
│ id=3 | code="SCRUM" | score_c1_responsiveness=0.85 | is_active=FALSE│
│                                          | inactive_date=2026-05-17 │
└────────────────────────────────────────────────────────────────────┘
┌────────────────────────────────────────────────────────────────────┐
│ id=9 | code="SCRUM" | score_c1_responsiveness=0.90 | is_active=TRUE │
│                                          | active_date=2026-05-17   │
└────────────────────────────────────────────────────────────────────┘
```

A chave lógica é `(code, is_active=TRUE)`, só existe sempre **um registo ativo por código**. O histórico completo é acessível filtrando `is_active=FALSE` com o código correspondente.

### Tabelas com SCD Tipo-2

| Tabela | Chave lógica | O que versiona |
|---|---|---|
| `methodology_evidence_base` | `(code, is_active)` | Scores MCDM, postura, tier, restrições |
| `tool_evidence_base` | `(code, is_active)` | Scores, compatibilidades, custo |
| `mcdm_weights` | `(context, is_active)` | Pesos MEB e TEB |
| `projetos` | `(projeto_uuid, is_active)` | Nome, gestor, datas, orçamento |

O interface de administração expõe um botão **"Restaurar"** por versão histórica, reativa a versão anterior e desativa a atual, sem apagar nenhum registo.

---

## 📁 Estrutura do Projeto

```
tcm202526-Adao-smgp/
├── app/
│   ├── services/
│   │   ├── kairosynlogic.py   ← motor de decisão KairoSyn
│   │   └── mcdm_engine.py     ← motor MCDM pluggable (MAVT/AHP)
│   ├── templates/             ← templates Jinja2 por etapa
│   ├── models.py              ← modelos SQLAlchemy (SCD Tipo-2)
│   ├── routes.py              ← rotas Flask e máquina de estados
│   ├── seeds.py               ← dados de referência MEB/TEB
│   └── migrations.py          ← migrações manuais de schema
├── docker-compose.yml
├── Dockerfile
├── SPEC.MD                    ← especificação técnica completa
└── README.md
```

---

## 📄 Referências

- Esteves, A. (2026). *Framework KairoSyn para Seleção de Metodologias de Gestão de Projetos*. Tese de Doutoramento.
- Saaty, T. L. (1980). *The Analytic Hierarchy Process*. McGraw-Hill.
- Von Winterfeldt, D., & Edwards, W. (1986). *Decision Analysis and Behavioral Research*. Cambridge University Press.

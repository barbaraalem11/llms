## promp 1
"Arquivo instancia.txt presente e lido com sucesso (m=2, n=8, l=15, C=5, p=24), então segui direto para o projeto conceitual.
A proposta é o BLG-FF: uma única metaheurística condutora — a Busca Local Guiada, vinda da satisfação de restrições em IA e, até onde sei, inédita no IPMTC — orquestrando heurísticas ad hoc de alto acoplamento: KTNS como oráculo exato de carregamento, passes Fiduccia–Mattheyses (importados do particionamento de circuitos VLSI, que é isomorfo à atribuição tarefa–máquina quando ferramentas são tratadas como nets) e busca em profundidade variável estilo Lin–Kernighan no sequenciamento. Um único parâmetro efetivo (α) e desempates determinísticos garantem variância nula por construção.
O documento abre com o diagnóstico da instância, que fundamenta cada escolha: regime dominado por trocas (uma adjacência entre tarefas de magazine cheio custa ≥72 > τ_max=59), dicotomia rígidas × leves com métrica exata d(i,j) entre as rígidas, efeito flush, leves como pontes (demonstrado via KTNS: [7,3,8] gasta 3 trocas contra 4 de [7,8,3]), limitante inferior provado Cmax ≥ 194 via conexidade do grafo de interseção, e um incumbente construtivo de 299 obtido à mão pelos próprios princípios. Incluí também a observação de que, com n=8, o espaço tem apenas 181.440 configurações — enumerável para servir de verdade-terreno na validação experimental." 


# Projeto Conceitual — BLG-FF: Busca Local Guiada por Fluxo de Ferramentas para o IPMTC

*Fase conceitual, sem geração de código, conforme solicitado.*

**Instância lida (`instancia.txt`):** m = 2, n = 8, l = 15, C = 5, p = 24. Verificação de consistência: 15 linhas de incidência × 8 colunas; Σ|Tⱼ| = 32; todas as 15 ferramentas são requeridas por ao menos uma tarefa; |Tⱼ| ≤ C para todo j. Leitura válida.

| j | τⱼ | Tⱼ | \|Tⱼ\| |
|---|-----|------------------|---|
| 1 | 3   | {2, 8, 9, 11, 13} | 5 |
| 2 | 33  | {8, 10}           | 2 |
| 3 | 59  | {3, 7}            | 2 |
| 4 | 38  | {12, 13, 15}      | 3 |
| 5 | 15  | {1, 9, 10, 12, 14}| 5 |
| 6 | 53  | {3, 6, 9, 11, 14} | 5 |
| 7 | 7   | {3, 4, 5, 10, 14} | 5 |
| 8 | 36  | {4, 5, 7, 9, 15}  | 5 |

Convenção adotada: o enunciado tarifa trocas realizadas *entre duas tarefas consecutivas*; a carga inicial do magazine, portanto, não é tarifada. Todos os cálculos abaixo seguem essa convenção e são explicitados para serem auditáveis.

---

## 1. Diagnóstico estrutural da instância

O projeto do método não parte de uma metaheurística escolhida a priori: parte das propriedades verificáveis da instância, e cada componente será justificado como resposta a uma propriedade específica identificada nesta seção.

### 1.1 Regime econômico dominado por trocas

Στ = 244 e τ̄ = 30,5, de modo que p = 24 já equivale a 79% do tempo médio de processamento. A situação é mais severa do que essa razão sugere: como se demonstra em 1.2, qualquer adjacência entre duas tarefas que saturam o magazine custa no mínimo 3p = 72 > τ_max = 59. Uma única transição mal escolhida na sequência custa mais do que processar a tarefa mais longa da instância. O makespan é governado pela logística de ferramentas, não pelos tempos de processamento — hierarquia invertida em relação ao P||Cmax clássico, em que balancear Στ é o essencial. O método deve, portanto, tratar o balanceamento de carga como restrição secundária e a estrutura de ferramentas como objetivo primário.

### 1.2 Dicotomia rígidas × leves e a métrica de adjacência

Cinco tarefas saturam o magazine (|Tⱼ| = C = 5): R = {1, 5, 6, 7, 8}. Três são leves: L = {2, 3, 4}, com folgas C − |Tⱼ| de 3, 3 e 2 posições, respectivamente. A consequência é exata, não heurística: durante uma tarefa rígida, o conteúdo do magazine é univocamente Tⱼ — zero graus de liberdade para a política de carregamento. Logo, se j ∈ R sucede imediatamente i ∈ R, o número de inserções tarifadas é exatamente d(i,j) = |Tⱼ \ Tᵢ| = C − |Tᵢ ∩ Tⱼ|, quantidade simétrica (pois |Tᵢ| = |Tⱼ|) e que satisfaz a desigualdade triangular (|A\C| ≤ |A\B| + |B\C| vale para conjuntos quaisquer). O subproblema de ordenar as rígidas contíguas é um caminho hamiltoniano de custo mínimo sob métrica genuína:

| d | 5 | 6 | 7 | 8 |
|---|---|---|---|---|
| **1** | 4 | 3 | 5 | 4 |
| **5** | – | 3 | 3 | 4 |
| **6** | – | – | 3 | 4 |
| **7** | – | – | – | 3 |

Nenhum par de rígidas compartilha mais que 2 ferramentas (min d = 3; max d = 5, com T₁ ∩ T₇ = ∅). Destaca-se ainda a ferramenta 9, a mais disputada: requerida por 4 das 5 rígidas ({1, 5, 6, 8}), qualquer atribuição que separe essas tarefas entre máquinas duplica t₉.

### 1.3 Efeito de descarga (*flush*) das rígidas

Uma rígida j força mag = Tⱼ; qualquer ferramenta útil no futuro e não pertencente a Tⱼ é expulsa e paga reinserção. Exemplo verificado na instância: na máquina com {1, 2, 4, 5}, a ordem [2, 1, 4, 5] realiza 6 trocas sob KTNS (carga inicial {2, 8, 9, 10, 11}; J1: +13 −10; J4: +12, +15 −2, −8; J5: +1, +10, +14), enquanto [2, 1, 5, 4] realiza 7: processar a rígida J5 entre J1 e J4 expulsa a ferramenta 13 (comum a T₁ e T₄) e cobra sua reinserção. As rígidas particionam a linha do tempo de cada máquina em "épocas" de magazine, e o custo de atravessar uma época depende do que ela força a descartar — propriedade que nenhuma função de avaliação baseada apenas em pares consecutivos captura.

### 1.4 Leves como pontes: demonstração

A sequência [7, 3, 8] realiza 3 trocas: carga inicial T₇ = {3, 4, 5, 10, 14}; J3 requer {3, 7}: insere 7 e o KTNS expulsa 10 (não requerida adiante), preservando {4, 5} para J8; J8 insere {9, 15} expulsando {3, 14}. Já [7, 8, 3] realiza 4 (J8: +7, +9, +15; J3: +3). A leve J3 vale mais *entre* J7 e J8 do que após: T₃ = {3, 7} atravessa o par (J7 fornece a ferramenta 3; J8 consumirá a 7), e a folga C − |T₃| = 3 mantém vivas as ferramentas do sucessor. Pontes são recurso escasso (apenas 3 leves) a ser alocado onde a métrica d é mais cara — regra construtiva extraída diretamente da instância.

### 1.5 Acoplamento entre máquinas: a atribuição é um corte de hipergrafo

Seja G o grafo de interseção (tarefas como vértices; aresta quando compartilham ferramenta). Suas arestas: (1,2)₈, (1,4)₁₃, (1,5)₉, (1,6)₉‚₁₁, (1,8)₉, (2,5)₁₀, (2,7)₁₀, (3,6)₃, (3,7)₃, (3,8)₇, (4,5)₁₂, (4,8)₁₅, (5,6)₉‚₁₄, (5,7)₁₀‚₁₄, (5,8)₉, (6,7)₃‚₁₄, (6,8)₉. G é conexo (J5 é adjacente a 1, 2, 4, 6, 7, 8; J3 conecta-se via 6, 7 e 8). Segue uma cadeia dedutiva verificável: toda bipartição não trivial das tarefas corta ao menos uma aresta de G, logo duplica ao menos uma ferramenta entre as máquinas; portanto Σₖ|Uₖ| ≥ 15 + 1 = 16, onde Uₖ é a união das ferramentas requeridas na máquina k; como cada ferramenta distinta além das C da carga inicial exige ao menos uma inserção, Σₖ trocas ≥ Σₖ(|Uₖ| − C) ≥ 6; e assim **Cmax ≥ (Στ + 6p)/2 = (244 + 144)/2 = 194**, limitante que domina os clássicos ⌈Στ/m⌉ = 122 e τ_max = 59. O gargalo da instância está quantificado: é a duplicação e rotatividade de ferramentas, e a variável de decisão que a controla é a atribuição σ.

### 1.6 Tensão balanceamento × compacidade e incumbente construtivo

As duas forças são antagônicas nesta instância. A partição perfeitamente balanceada em τ, {1, 3, 6, 7} / {2, 4, 5, 8} (122/122), tem uniões de tamanhos 12 e 11, logo a primeira máquina sozinha custa ≥ 122 + 7·24 = 290. No extremo oposto, a partição compacta em ferramentas {3, 6, 7} / {1, 2, 4, 5, 8} (uniões 9 e 13) concentra ≥ 125 + 8·24 = 317 na máquina grande. Aplicando os princípios 1.2–1.4 manualmente, obtém-se o incumbente: M₁ = [6, 7, 3, 8] com 6 trocas (carga inicial T₆; J7: +4, +5, +10; J3: +7 −10; J8: +9, +15 −3, −14), tempo 155 + 144 = 299; M₂ = [2, 1, 4, 5] com 6 trocas (traço em 1.3), tempo 89 + 144 = 233. **Cmax = 299.** Não se alega otimalidade; o par (LB = 194, UB = 299) delimita a instância e evidencia que os princípios extraídos são operacionais — a mesma máquina de raciocínio que o método automatizará.

### 1.7 Nota de validação exata

Com duas máquinas idênticas e n = 8, o espaço (atribuição, sequências) tem Σₖ C(8,k)·k!·(8−k)!/2 = 9·8!/2 = 181.440 configurações, cada uma avaliável por KTNS em O(n·l). A enumeração completa é computacionalmente trivial e será usada como verdade-terreno na fase experimental — boa prática frequentemente negligenciada: validar a metaheurística onde o ótimo é conhecido antes de escalar. O projeto abaixo, entretanto, é dimensionado para a classe-alvo do RCPMS (n ≈ 200, m ≈ 10), onde a enumeração é impossível.

---

## 2. Arquitetura: princípios e representação

Do diagnóstico decorrem três princípios de projeto. **P1 (redução exata do espaço):** o nível de decisão do carregamento não é buscado, é resolvido por oráculo ótimo. **P2 (vocabulário estrutural único):** todas as camadas do método raciocinam sobre as mesmas grandezas diagnosticadas — uniões Uₖ, métrica d, pontes e épocas de flush — de modo que diversificação e intensificação operem sobre as mesmas variáveis, condição necessária para sinergia real e não justaposição. **P3 (determinismo):** robustez obtida por construção, não por média de sorteios.

**Representação.** Solução = (σ: J → M; πₖ por máquina), direta, sem chaves aleatórias ou decodificadores — preservar as estruturas de 1.2–1.4 visíveis para os operadores é o que se entende aqui por alto acoplamento. **Oráculo de carregamento:** KTNS (Tang & Denardo, 1988), ótimo para sequência fixa, O(q·l) por máquina, com carga inicial livre conforme a convenção do enunciado. A justificativa da eliminação do terceiro nível é de dominância: para qualquer (σ, π), todo plano de carregamento distinto do produzido pelo KTNS é fracamente dominado, logo buscá-lo só adicionaria soluções dominadas ao espaço.

**Avaliação hierárquica.** Mantém-se por máquina o *surrogate* Φₖ = τ(Sₖ) + p·max(0, |Uₖ| − C), atualizável em O(|Tⱼ|) por movimento via contadores de uso ferramenta–máquina. Pelo argumento de 1.5, Φₖ é limitante inferior exato do custo da máquina k, independente da ordem: serve para priorizar e podar candidatos de movimento antes da confirmação exata por KTNS, que permanece o único juiz de aceitação. O filtro ordena o esforço computacional; nunca substitui a avaliação exata.

---

## 3. Camada de intensificação: heurísticas ad hoc de alto acoplamento

Os três componentes a seguir são heurísticas específicas, não metaheurísticas — categoria de uso livre segundo as diretrizes — e a importação de cada um se justifica por isomorfismo estrutural com o subproblema atacado, não por analogia frouxa.

**Construção determinística.** (i) *Atribuição:* bipartição do hipergrafo tarefa–ferramenta — células = tarefas com peso τⱼ; *nets* = ferramentas — pelo algoritmo de Fiduccia–Mattheyses (1982), oriundo do projeto físico de circuitos VLSI. A importação é isomorfismo exato: minimizar *nets* cortadas é minimizar ferramentas duplicadas, o custo dominante quantificado em 1.5, sob restrição de balanço expressa em Φ (e não em τ, pelo argumento de 1.1). (ii) *Sequenciamento:* encadeamento guloso das rígidas pela métrica d (vizinho mais barato, desempate lexicográfico fixo) e inserção de cada leve na posição de máxima cobertura-ponte, maximizando |Tℓ ∩ (T_pred ∪ T_succ)| e usando a folga para preservar ferramentas do sucessor — regra formalizada a partir de 1.4.

**Intensificação intra-máquina.** Busca em profundidade variável no espírito de Lin–Kernighan (1973): cadeias de movimentos de realocação de ponte, or-opt e troca, encadeados enquanto houver perspectiva de ganho acumulado positivo, com avaliação exata por KTNS incremental de sufixo (recalcular apenas a partir da posição alterada, O((q − pos)·l)) e poda das cadeias pelos limitantes inferiores de transição fornecidos por d entre rígidas. A profundidade da cadeia não é parâmetro: esgota-se por critério de ganho.

**Intensificação inter-máquinas.** Passes FM completos sobre σ: mover a tarefa de maior ganho em Φ, travá-la até o fim do passe, prosseguir mesmo com ganhos intermediários negativos e reter o melhor prefixo do passe. Esse mecanismo — a marca do FM em VLSI — atravessa deterministicamente vales rasos da paisagem de atribuição, constituindo microdiversificação intrínseca sem qualquer sorteio. Ao aceitar um prefixo, as sequências das máquinas afetadas são re-otimizadas pela busca intra-máquina e o custo é confirmado por KTNS.

---

## 4. Metaheurística condutora única: Busca Local Guiada (BLG)

Adota-se deliberadamente **uma única** metaheurística, dentro do limite de duas: cada metaheurística adicional agrega parâmetros, variância e opacidade analítica, em tensão direta com três diretrizes do enunciado. A escolhida é a Busca Local Guiada (*Guided Local Search*, Voudouris & Tsang, 1999), originária da satisfação de restrições em Inteligência Artificial e — até onde alcança o levantamento realizado — sem aplicação registrada ao IPMTC/SSP, atendendo ao requisito de novidade sem recorrer a gimmicks: seu mecanismo central, penalizar *características estruturais* da solução corrente, é exatamente o que o diagnóstico da Seção 1 pede, pois as características que carregam o custo já foram isoladas e são mensuráveis.

**Características (features) e custos.** F1ₜ: "a ferramenta t é requerida em ambas as máquinas", com custo indicador c = p — o custo marginal mínimo de uma duplicação, conforme 1.5; a ferramenta 9, requerida por quatro rígidas, é a candidata natural à primeira penalização quando duplicada. F2₍ᵢ,ⱼ₎: "a adjacência i→j ocorre em alguma sequência", com custo *realizado* c = p·(inserções tarifadas na transição sob o carregamento KTNS corrente) — medido, não estimado, o que captura inclusive os efeitos de flush e ponte que uma estimativa por pares ignoraria.

**Dinâmica.** Minimiza-se o objetivo aumentado g = f + λ·Σᵢ penᵢ·Iᵢ com a bateria completa de intensificação (Seção 3) até ótimo local conjunto; penalizam-se então as características de utilidade máxima uᵢ = cᵢ/(1 + penᵢ); reinicia-se a intensificação sobre a paisagem deformada. Critério de aspiração padrão: movimento que melhora o f real é aceito independentemente de g, impedindo que penalidades acumuladas ocultem o ótimo global.

**Sinergia, explicitada.** A diversificação da BLG deforma a paisagem exatamente sobre as variáveis que os intensificadores sabem otimizar (P2): penalizar F1ₜ empurra os passes FM a desfazer a duplicação de t; penalizar F2₍ᵢ,ⱼ₎ empurra as cadeias LK a romper a adjacência cara e reposicionar pontes. Não há estagnação, porque a penalização progressiva expulsa a busca de bacias já exauridas; não há passeio aleatório, porque todo movimento continua dirigido por ganho no objetivo aumentado; e o FM contribui uma segunda escala de diversificação, local e determinística, dentro de cada passe. Registre-se ainda que a arquitetura **não** é hiper-heurística: a BLG não seleciona nem gera heurísticas — reparametriza o objetivo de uma busca local fixa, definição canônica de metaheurística única guiando heurísticas subordinadas.

**Por que não as escolhas óbvias.** ILS e GRASP diversificam por perturbação ou reinício sorteados — variância entre execuções e aprendizado nulo entre reinícios, além de já explorados na literatura recente do problema; SA e Parallel Tempering dependem de cronogramas de temperatura sensíveis (≥ 2 parâmetros críticos e alta variância); AG/BRKGA impõem decodificadores que quebram o acoplamento, ocultando dos operadores precisamente as estruturas d, pontes e Uₖ; busca tabu exigiria tenures calibrados e mantém memória de curto prazo redundante com as penalidades da BLG, que são memória de longo prazo com semântica estrutural.

---

## 5. Complexidade assintótica

Contadores de uso ferramenta–máquina: atualização O(|Tⱼ|) por movimento; Φₖ em O(1) amortizado. Passe FM com estrutura de *buckets* de ganho: O(Σⱼ|Tⱼ| + n·G_max) por passe, linear no tamanho da instância como no original de VLSI. KTNS: O(q·l) por sequência; avaliação incremental por sufixo reduz o custo médio por movimento. Cadeia de profundidade variável: O(prof.·q·l) com poda por d. Iteração BLG: custo da convergência local mais O(|F|) para atualização de penalidades, com |F| ≤ l + n² (na prática, apenas características ativas são mantidas, em tabela de dispersão). Memória: O(n·l). Para n = 8 tudo é instantâneo; o dimensionamento — buckets, incrementalidade, surrogate — existe para que o custo por iteração não exploda na classe-alvo (n ≈ 200, m ≈ 10, magazines maiores).

---

## 6. Parâmetros e robustez

Parâmetro efetivo único: α, em λ = α·f(ótimo local)/|características ativas| (recomendação inicial α ≈ 0,2, faixa usual [0,1; 0,3]; se calibrado, iRace sobre α apenas, com orçamento mínimo). Todos os desempates são lexicográficos fixos, tornando o método determinístico: a variância entre execuções independentes é nula *por construção* — a forma mais forte de robustez, que dispensa argumentos estatísticos. Para o protocolo experimental usual, que exige dispersão para testes de hipótese, aleatoriza-se somente o desempate (semente afetando apenas empates), reportando-se a distribuição completa: a robustez passa a ser medida, não presumida.

---

## 7. Protocolo experimental

Em síntese: (1) verdade-terreno por enumeração exata nesta instância (1.7), medindo gap absoluto e taxa de acerto do ótimo em execuções com desempates aleatorizados; (2) ablação de componentes (BLG desligada, passes FM desligados, regra de pontes desligada) para atribuição causal de desempenho a cada mecanismo; (3) curvas *time-to-target* e perfis de desempenho; (4) escalonamento nas instâncias maiores da classe RCPMS para aferir as estruturas de dados incrementais; (5) relato sistemático contra os limitantes aqui derivados, LB = 194 e UB construtivo = 299.

---

### Referências dos componentes importados

Tang, C. S.; Denardo, E. V. (1988). *Models arising from a flexible manufacturing machine, Part I: minimization of the number of tool switches.* Operations Research. — Fiduccia, C. M.; Mattheyses, R. M. (1982). *A linear-time heuristic for improving network partitions.* DAC. — Lin, S.; Kernighan, B. W. (1973). *An effective heuristic algorithm for the traveling-salesman problem.* Operations Research. — Voudouris, C.; Tsang, E. (1999). *Guided local search and its application to the traveling salesman problem.* EJOR. — Crama, Y. et al. (1994). *Minimizing the number of tool switches on a flexible machine.* IJFMS.

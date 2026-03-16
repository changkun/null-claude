# Game Theory & Social Dynamics

Strategic interaction, segregation, and cultural evolution — where mathematics meets sociology.

---

## Spatial Prisoner's Dilemma

### Background

The Prisoner's Dilemma, formalized by Merrill Flood and Melvin Dresher in 1950 and framed by Albert Tucker, is the canonical model of cooperation under temptation to defect. Martin Nowak and Robert May (1992) placed it on a spatial lattice, showing that cooperators can survive by forming protective clusters even without memory, reputation, or kinship. This spatial structure transforms the dynamics from inevitable defection into a rich phase transition between cooperative and defective regimes.

### Formulation

Each cell plays a one-shot Prisoner's Dilemma with all 8 Moore neighbors on a toroidal grid. Payoffs follow the standard matrix:

```
Payoff Matrix (row = focal player, column = opponent):

                 Cooperator    Defector
  Cooperator        R             S
  Defector          T             P

  T = Temptation to defect   (e.g., 1.5)
  R = Reward for mutual coop (e.g., 1.0)
  P = Punishment for mutual defection (e.g., 0.0)
  S = Sucker's payoff        (e.g., 0.0)

  Constraint for a dilemma: T > R > P >= S

  Score(i) = sum of payoffs from all 8 neighbor interactions
```

After scoring, each cell adopts the strategy (cooperate or defect) of whichever cell in its Moore neighborhood (including itself) achieved the highest total score. This deterministic imitation rule produces sharp boundaries between cooperator clusters and defector regions.

### Presets

| Preset | T | R | P | S | Init Coop |
|--------|---|---|---|---|-----------|
| Classic | 1.50 | 1.0 | 0.0 | 0.0 | 50% |
| Weak Dilemma | 1.20 | 1.0 | 0.0 | 0.0 | 50% |
| Strong Dilemma | 2.00 | 1.0 | 0.0 | 0.0 | 50% |
| Snowdrift / Hawk-Dove | 1.50 | 1.0 | 0.1 | 0.5 | 50% |
| Stag Hunt | 1.20 | 1.5 | 0.0 | 0.0 | 40% |
| Critical Threshold | 1.65 | 1.0 | 0.0 | 0.0 | 50% |
| Mostly Defectors | 1.40 | 1.0 | 0.0 | 0.0 | 15% |
| Mostly Cooperators | 1.40 | 1.0 | 0.0 | 0.0 | 85% |

### What to look for

- **Cluster formation**: Cooperators survive by huddling into compact groups where interior cells earn high mutual-cooperation payoffs, insulating them from exploitation at the boundary.
- **Phase transition at T ~ 1.65**: Below this threshold cooperators dominate; above it defectors sweep the grid. At the critical value, fractal-like boundaries appear.
- **Snowdrift coexistence**: When P and S are nonzero (Hawk-Dove variant), cooperators and defectors can stably coexist in dynamic equilibrium.
- **Invasion dynamics**: Try the "Mostly Defectors" preset to watch whether a small cooperator seed can bootstrap itself into a surviving cluster.
- **Temptation tuning**: Press `t`/`T` during simulation to raise or lower T and watch cooperation collapse or recover in real time.

### References

- Nowak, M. A. & May, R. M. "Evolutionary games and spatial chaos." *Nature*, 359, 826--829 (1992). https://doi.org/10.1038/359826a0
- Axelrod, R. *The Evolution of Cooperation*. Basic Books (1984). https://www.basicbooks.com/titles/robert-axelrod/the-evolution-of-cooperation/9780465005642/

---

## Schelling Segregation

### Background

Thomas Schelling's segregation model (1971) demonstrated one of social science's most striking results: even mild individual preferences for same-type neighbors can produce dramatic large-scale segregation. Agents need not be bigots -- a threshold as modest as wanting one-third of their neighbors to be similar suffices to generate nearly complete spatial separation. The model became foundational to agent-based modeling and complexity economics, showing how micro-motives produce macro-behavior.

### Formulation

Agents of N groups occupy cells on a toroidal grid with some fraction left empty. Each agent evaluates its 8 Moore neighbors:

```
For agent at (r, c) with group identity g:

  similar = count of neighbors with group == g
  total   = count of non-empty neighbors

  satisfied = (similar / total) >= tolerance    (if total > 0)
            = true                               (if total == 0)

  tolerance in [0, 1]  (e.g., 0.375 = original Schelling)
  density   in [0, 1]  (fraction of cells occupied)
  n_groups  in {2, 3, 4, ...}
```

Each step, all unsatisfied agents are identified and randomly relocated to random empty cells. The process repeats until equilibrium (all agents satisfied) or indefinitely if churn persists.

### Presets

| Preset | Tolerance | Density | Groups |
|--------|-----------|---------|--------|
| Mild Preference | 30% | 90% | 2 |
| Classic Schelling | 37.5% | 90% | 2 |
| Moderate Bias | 50% | 85% | 2 |
| Strong Preference | 62.5% | 90% | 2 |
| Three Groups | 37.5% | 85% | 3 |
| Four Cultures | 35% | 80% | 4 |
| Sparse City | 40% | 50% | 2 |
| Packed Metropolis | 37.5% | 97% | 2 |

### What to look for

- **Tipping point**: Even the "Mild Preference" preset (30% tolerance) generates visible clustering. The transition from integrated to segregated is nonlinear.
- **Density effects**: Compare "Sparse City" (50% occupied) with "Packed Metropolis" (97%). Low density allows fast relocation and quick equilibrium; high density creates slow, frustrated churn with many unhappy agents who cannot find acceptable vacancies.
- **Multi-group dynamics**: With 3 or 4 groups, boundary geometry becomes more complex. Minority groups tend to form smaller, rounder clusters.
- **Satisfaction tracking**: The status bar shows the happy/unhappy ratio converging toward 100% satisfaction, typically within 20--50 steps.
- **Tolerance tuning**: Press `t`/`T` to adjust tolerance in real time and watch segregation intensify or dissolve.

### References

- Schelling, T. C. "Dynamic models of segregation." *Journal of Mathematical Sociology*, 1(2), 143--186 (1971). https://doi.org/10.1080/0022250X.1971.9989794
- Clark, W. A. V. & Fossett, M. "Understanding the social context of the Schelling segregation model." *PNAS*, 105(11), 4109--4114 (2008). https://doi.org/10.1073/pnas.0708155105

---

## Rock-Paper-Scissors

### Background

Spatial Rock-Paper-Scissors models cyclic dominance -- a competitive structure found throughout ecology, from side-blotched lizards to coral reef overgrowth to bacterial colicin warfare (*E. coli* strains). Birgit Kerr, Margaret Riley, and colleagues demonstrated in 2002 that spatial structure is essential for coexistence: in a well-mixed population one species quickly eliminates another, but on a lattice all three persist through chasing spirals. The model exemplifies how biodiversity can be maintained by local interactions alone.

### Formulation

Each cell on a toroidal grid holds one of N species (3 for classic RPS, 5 for RPSLS -- Rock-Paper-Scissors-Lizard-Spock). Interactions follow cyclic dominance:

```
Cyclic dominance rule for N species (labeled 0, 1, ..., N-1):

  Species i beats species (i - 1) mod N

  For N = 3:  Rock(0) beats Scissors(2)
              Paper(1) beats Rock(0)
              Scissors(2) beats Paper(1)

  For N = 5:  Each species beats the 2 species
              "behind" it in the cycle.

Update algorithm (per generation):
  interactions = rows * cols * swap_rate

  For each interaction:
    1. Pick random cell (r, c)
    2. Pick random von Neumann neighbor (4-connected, toroidal)
    3. attacker = neighbor's species
       defender = cell's species
    4. If defender == (attacker - 1) mod N:
         cell adopts attacker's species  (invasion)

  swap_rate in [0.05, 1.0]  (fraction of grid sampled per step)
```

### What to look for

- **Spiral waves**: The signature phenomenon. Three-armed spirals emerge and rotate as each species chases the one it dominates, forming a stable dynamical pattern.
- **Coexistence through space**: All species survive indefinitely on the lattice, whereas mean-field (well-mixed) dynamics would lead to one species dominating.
- **Swap rate effects**: Higher swap rates (press `s`) create faster dynamics and larger spiral wavelengths. Lower rates produce fine-grained, noisy patterns.
- **5-species dynamics**: RPSLS (Lizard-Spock extension) produces more complex spiral structures with additional interleaved domains.
- **Initial layout**: "Blocks" layout (vertical stripes) shows invasion fronts clearly; "seeds" layout shows nucleation and growth; "random" reaches spiral equilibrium fastest.

### References

- Kerr, B., Riley, M. A., Feldman, M. W. & Bohannan, B. J. M. "Local dispersal promotes biodiversity in a real-life game of rock-paper-scissors." *Nature*, 418, 171--174 (2002). https://doi.org/10.1038/nature00823
- Reichenbach, T., Mobilia, M. & Frey, E. "Mobility promotes and jeopardizes biodiversity in rock-paper-scissors games." *Nature*, 448, 1046--1049 (2007). https://doi.org/10.1038/nature06095

---

## Stock Market

### Background

Agent-based computational finance models emerged in the 1990s from the Santa Fe Artificial Stock Market (Arthur et al., 1997) and related work by economists seeking to explain market phenomena -- bubbles, crashes, fat-tailed return distributions -- that rational expectations models could not. This simulation implements a heterogeneous-agent market with four trader types whose interactions generate realistic emergent dynamics: trend-following amplifies momentum, noise traders inject randomness, fundamentalists anchor price to value, and market makers provide liquidity.

### Formulation

The market operates as a continuous double auction with four agent types:

```
Agent types and decision rules:

FUNDAMENTALIST:
  gap = (FV - price) / price
  sentiment = clamp(gap * 3.0 + noise, -1, 1)
  Buy if gap > 0.02 (price below fair value)
  Sell if gap < -0.02 (price above fair value)
  FV follows random walk: FV += gauss(0, 0.1) each tick

CHARTIST:
  momentum = trend * recent_return + (1 - trend) * prev_momentum
  sentiment = clamp(momentum * 5 + herd * global_sentiment + noise, -1, 1)
  Buy if sentiment > 0.2; Sell if sentiment < -0.2
  recent_return = (price[t] - price[t-20]) / price[t-20]

NOISE TRADER:
  sentiment = clamp(herd * global_sentiment + gauss(0, 0.5), -1, 1)
  Trades with 30% probability each tick
  Direction follows sentiment sign

MARKET MAKER:
  spread = volatility * price * 0.5
  Posts bid at (price - spread * U(0.5, 1.5))
  Posts ask at (price + spread * U(0.5, 1.5))
  Neutral sentiment

Order matching:
  trade_price = (best_bid + best_ask) / 2
  Executes if best_bid >= best_ask

Parameters:
  volatility       -- base price noise scale
  trend_strength   -- chartist momentum weight [0, 1]
  herd_factor      -- social influence weight [0, 1]
  fundamental_value -- anchored price target (drifts)
```

### Presets

| Preset | Fundamentalists | Chartists | Noise | Market Makers | Volatility | Trend | Herd |
|--------|----------------|-----------|-------|---------------|------------|-------|------|
| Bull Run | 60 | 30 | 20 | 2 | 0.02 | 0.6 | 0.3 |
| Flash Crash | 15 | 60 | 30 | 1 | 0.05 | 0.9 | 0.7 |
| Bubble & Pop | 10 | 40 | 40 | 2 | 0.03 | 0.8 | 0.9 |
| Efficient Market | 80 | 10 | 10 | 5 | 0.01 | 0.2 | 0.1 |
| Herd Mania | 10 | 20 | 70 | 1 | 0.04 | 0.5 | 0.95 |
| Market Maker Dominance | 20 | 20 | 20 | 15 | 0.02 | 0.3 | 0.2 |

### What to look for

- **Emergent bubbles and crashes**: "Bubble & Pop" shows price inflating far above fundamental value as chartists and noise traders reinforce each other, followed by sudden collapse when fundamentalists overwhelm momentum.
- **Flash crash dynamics**: With many chartists and high trend/herd parameters, positive feedback loops can trigger sudden price drops of 20--40% in a few ticks.
- **Efficient market convergence**: When fundamentalists dominate (80:10:10 ratio), price closely tracks the drifting fundamental value -- the efficient market hypothesis in action.
- **View modes**: Press `v` to cycle through price chart (candlestick), order book depth, agent wealth heatmap, and sentiment map.
- **Wealth distribution**: The wealth heatmap view reveals how different agent types fare over time. Market makers tend to accumulate wealth through the spread; chartists profit in trending markets but suffer in mean-reverting ones.

### References

- Arthur, W. B., Holland, J. H., LeBaron, B., Palmer, R. & Tayler, P. "Asset pricing under endogenous expectations in an artificial stock market." *The Economy as an Evolving Complex System II*, Addison-Wesley (1997). https://doi.org/10.2139/ssrn.2252
- Lux, T. & Marchesi, M. "Scaling and criticality in a stochastic multi-agent model of a financial market." *Nature*, 397, 498--500 (1999). https://doi.org/10.1038/17290

---

## Civilization & Cultural Evolution

### Background

This mode synthesizes ideas from Jared Diamond's geographic determinism (*Guns, Germs, and Steel*, 1997) and Robert Axelrod's cultural dissemination model (1997) into an agent-based civilization simulator. Tribes emerge on procedurally generated terrain, develop technologies along a branching tech tree, establish trade networks, wage wars, and diffuse cultural traits across populations. The model explores how geography, resource distribution, and social dynamics interact to produce divergent civilizational trajectories -- why some societies industrialize while others remain nomadic.

### Formulation

The simulation operates on a 2D terrain grid with 10 terrain types, each yielding different resources:

```
Terrain yields per cell:
  Type       Food  Prod  Gold
  Water        1     0     2
  Plains       4     1     1
  Forest       2     3     1
  Hills        1     3     2
  Mountain     0     4     3
  Desert       0     1     2
  River        5     1     3
  Coast        3     1     3
  Tundra       1     1     0
  Jungle       3     2     2

Population growth:
  food_per_cap = tribe.food / tribe.pop
  If food_per_cap > 1.0:
    growth = min(pop * 0.03, food_per_cap * 0.5)
  If food_per_cap < 0.3:
    famine_loss = pop * 0.05  (tribe dies if pop <= 0)

Research progress per tick:
  progress += (prod_yield * 0.05 + pop * 0.01) * sci_multiplier
  Tech discovered when progress >= cost

Military strength:
  strength = attack * pop * 0.01 + defense * 0.5
  Combat outcome: P(win) = strength / (strength_a + strength_b)

Cultural diffusion:
  influence = trait_strength * culture * 0.01
  Radiates from settlements with radius ~ sqrt(culture)
  Decays as 1/manhattan_distance
  Trait adoption when local influence > 0.5

Trade income:
  gold += num_trade_partners * 2.0 * trade_bonus

War declaration probability:
  p_war = aggression * 0.04
        + 0.06 * warlike_strength  (if Warlike trait)
        * 0.2                      (if Peaceful trait)
        * 1.5                      (if pop > 1.5 * enemy_pop)
```

The tech tree contains 20 technologies from Fire and Tool-Making through Gunpowder and Printing Press, with prerequisite chains and effects on food, production, attack, defense, movement, trade, and culture. Ten cultural traits (Warlike, Peaceful, Nomadic, Agrarian, Mercantile, Religious, Artistic, Scientific, Expansionist, Isolationist) modify behavior and can spread between civilizations through cultural diffusion.

### Presets

| Preset | Land% | Mountains | Forests | Rivers | Tribes | Start Pop | Aggression | Trade Bonus |
|--------|-------|-----------|---------|--------|--------|-----------|------------|-------------|
| Pangaea | 65% | 6% | 20% | 6 | 8 | 50 | 0.40 | 1.0 |
| Archipelago | 35% | 4% | 12% | 3 | 10 | 30 | 0.20 | 0.5 |
| River Valleys | 50% | 8% | 15% | 10 | 6 | 60 | 0.30 | 1.5 |
| Tundra & Steppe | 55% | 10% | 8% | 4 | 7 | 35 | 0.50 | 0.8 |
| Fertile Crescent | 55% | 12% | 10% | 8 | 6 | 55 | 0.35 | 1.3 |
| Random World | -- | -- | -- | -- | -- | -- | -- | -- |

### What to look for

- **Geographic determinism**: River Valleys civilizations develop faster thanks to high food yields (River tiles produce 5 food), enabling larger populations and faster research. Archipelago civilizations remain isolated until Navigation is discovered.
- **Tech race dynamics**: Watch the sidebar to see which civilizations lead in technology count. The Scientific trait provides a 30% research bonus, while Agrarian civilizations grow larger populations that also contribute to research.
- **Cultural diffusion**: Switch to culture view (`v`) to see traits radiating outward from settlements. Civilizations near a culturally dominant neighbor may adopt foreign traits when local influence exceeds 0.5.
- **War and conquest**: Warlike civilizations with population advantages tend to expand aggressively. Conquered civilizations' territory is absorbed by the victor.
- **Trade networks**: Trade view shows which civilizations have established trade partnerships. Mercantile traits increase trade probability, and each partner adds 2.0 * trade_bonus gold per tick.
- **Rise and fall**: Event log (`l`) narrates the history -- tech discoveries, war declarations, peace treaties, settlements founded, and civilizations that perish from famine or conquest.

### References

- Axelrod, R. "The Dissemination of Culture: A Model with Local Convergence and Global Polarization." *Journal of Conflict Resolution*, 41(2), 203--226 (1997). https://doi.org/10.1177/0022002797041002001
- Diamond, J. *Guns, Germs, and Steel: The Fates of Human Societies*. W. W. Norton (1997). https://wwnorton.com/books/Guns-Germs-and-Steel/

---

## Crowd Dynamics & Evacuation Simulation

### Background

Pedestrian crowd dynamics sits at the intersection of physics, social science, and safety engineering. Dirk Helbing and Péter Molnár (1995) introduced the social-force model, treating each pedestrian as a Newtonian particle subject to a driving force toward their destination, repulsive forces from other pedestrians and walls, and body contact forces during crushing. This framework reproduces a remarkable range of emergent collective phenomena observed in real crowds: arch/clogging formation at narrow exits, spontaneous lane formation in bidirectional flow, the counterintuitive faster-is-slower effect under panic, and herding contagion waves.

The model is widely used in evacuation safety design and has been validated against empirical crowd data from stadiums, concert venues, and emergency evacuations.

### Formulation

Each agent *i* obeys Newton's second law with the following forces:

```
Driving force (toward exit):
  F_drive = (v0 * e_i - v_i) / tau
  where v0 = desired_speed * (1 + panic * 2.5)
        e_i = unit vector toward target exit
        tau = 0.5 s (relaxation time)

Agent-agent repulsion (exponential + contact):
  F_rep = A * exp((r_ij - d_ij) / B) * n_ij
  where A = 2.0, B = 0.3
        r_ij = sum of radii, d_ij = center distance
        n_ij = unit normal from j to i

  Body contact (when overlapping, d_ij < r_ij):
    F_contact = k_body * overlap * n_ij      (k_body = 12.0)
    F_friction = k_fric * overlap * Δv_t * t  (k_fric = 6.0)

Wall repulsion:
  F_wall = A_w * exp(-d / B_w) * n_wall
  where A_w = 5.0, B_w = 0.2
  Plus body contact force for overlap (k = 20.0)

Panic noise:
  F_noise = panic * 0.5 * (random - 0.5) per axis

Panic contagion:
  Δpanic_i += 0.01 * panic_j / max(d_ij, 0.5)  for neighbors within 2.5 cells
  Natural decay: panic -= 0.002 per step
```

Speed is clamped to `desired_speed * (2.0 + panic * 2.0)`.

### Presets

| Preset | Geometry | Agents | Init Panic | Speed | Key Phenomenon |
|--------|----------|--------|------------|-------|----------------|
| Normal Evacuation | Rectangular room, 1 exit | ~15% fill | 0.1 | 1.2 | Arch formation at doorway |
| Panic Stampede | Rectangular room, 1 exit | ~15% fill | 0.8 | 2.0 | Faster-is-slower, crushing |
| Concert Venue | Room + stage obstacle, 2 exits | ~12% fill | 0.2–0.5 | 1.3 | Obstacle-mediated flow split |
| Stadium Exit | Elliptical boundary, 4 vomitoria | ~10% fill | 0.15–0.35 | 1.2 | Merging flows at narrow exits |
| Counterflow Corridors | Long corridor, open ends | 2 × ~6% fill | 0.0 | 1.0 | Spontaneous lane formation |
| Black Friday Rush | Open area, entrance at top | ~10% fill | 0.5–0.9 | 1.8 | Inward competitive pushing |

### What to look for

- **Arch formation**: In Normal Evacuation, watch agents self-organize into a semicircular arch around the exit. This is the same mechanism that causes grain hopper clogging — the arch is a force chain analog.
- **Faster-is-slower effect**: In Panic Stampede, high panic increases desired speed but also increases repulsive forces and noise, paradoxically *decreasing* flow rate through the exit compared to calm evacuation. Press `p`/`P` to raise/lower panic and observe this directly.
- **Lane formation**: In Counterflow Corridors, two opposing streams spontaneously segregate into parallel lanes (group 0 = blue/cyan, group 1 = green). This minimizes head-on collisions and emerges purely from the repulsive forces — no explicit lane preference exists in the model.
- **Panic contagion waves**: Watch panic (red coloring) spread radially from initially panicked agents. In Black Friday Rush, panic waves propagate through the dense crowd from the competitive front.
- **Density crushing**: Monitor the "density" statistic — values above 6–8 in a 3×3 region represent dangerous crowd crush conditions. Compare Normal vs Panic presets to see how panic drives density spikes near exits.
- **Flow rate dynamics**: The flow rate (escapes/step) shows non-monotonic behavior: it ramps up as agents reach exits, may plateau due to clogging, and eventually drops as the crowd thins.

### References

- Helbing, D. and Molnár, P. "Social force model for pedestrian dynamics." *Physical Review E*, 51(5), 4282--4286 (1995). https://doi.org/10.1103/PhysRevE.51.4282
- Helbing, D., Farkas, I., and Vicsek, T. "Simulating dynamical features of escape panic." *Nature*, 407, 487--490 (2000). https://doi.org/10.1038/35035023
- Helbing, D., Johansson, A., and Al-Abideen, H. Z. "Dynamics of crowd disasters: An empirical study." *Physical Review E*, 75(4), 046109 (2007). https://doi.org/10.1103/PhysRevE.75.046109

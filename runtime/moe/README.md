# MoE

Home de routing, paging e telemetria agregada para adapters sparse.

## Estado atual

- `Router` agora executa top-k com softmax e preserva um `RouterDecision`
  consultavel com `entropy`, `load_balance`, `selected_mass` e
  `total_experts`.
- `DeepSeekMoEAdapter` e `KimiMoEAdapter` projetam esse roteamento leve para o
  `GenerationResult` nativo como:
  - `moe_selected_experts`
  - `moe_router_entropy`
  - `moe_load_balance`
  - `moe_selected_mass`
- `ExpertPager` continua simples neste momento; o proximo slice aprofunda
  eviction e comportamento visivel de residency.

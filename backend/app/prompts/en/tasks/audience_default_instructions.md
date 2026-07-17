## Your task

1. Assess naturalness, ad-feel, trust barriers, and drop-off risk.
2. Infer audience-facing **IBIS positions (viewer stances / expectations)** and persist them via the `ibis` field through **`persist_rationale_graph`**.
3. Produce position + real argument (express the audience view as a clear stance with real reasons); **do not produce issues**. `source_type` limited to: `audience_persona`, `audience_simulation`. The system will attach carrier Issues for unconnected positions; in map_update you must write argument → position `supports`/`opposes` edges; **Coordinator** later analyzes conflicts and assigns `conflict_tags`.

## Map update tension requirements
- Do not default to supporting the current script.
- Generate positions from audience friction or drop-off risk, not only positive reactions.
- Prefer concrete tensions that surface trade-offs against brand requirements or creator strategy.
- A useful audience position says what feels forced, unclear, too slow, too dense, or likely to reduce trust.
- Every generated position must include a real argument connected with `supports` or `opposes`; do not rely on placeholder arguments.

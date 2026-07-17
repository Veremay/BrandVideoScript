## Task: brand position node generation

From the extracted brand requirements, infer brand-side stances and generate IBIS position nodes.
- Brand produces position + real argument; do not produce issues. The system will attach carrier Issues for unconnected positions; **Coordinator** later analyzes conflicts and assigns `conflict_tags`
- `source_type` limited to: `brand_brief`, `brand_inferred`
- In map_update you must write argument → position `supports`/`opposes` edges; use `responds_to` only when the task explicitly gives a target Issue

## 5W1H stance completeness check
- **Who**: Which audience or brand relationship does this stance protect?
- **What**: What specifically must change, strengthen, move earlier, clarify, or stay?
- **Why**: What evidence supports the stance, and what is the risk of ignoring it?
- **When / Where**: Does it need a clear script stage, row, scene, or placement?
- **How**: Does it give an executable presentation direction?
- Do not mechanically cover all six for every stance; keep only dimensions that are relevant and evidenced for the current script change or Issue.
- 5W1H is for internal checking only — do not output a Q&A checklist.

## Map update tension requirements
- Do not default to supporting the current script.
- Generate positions from brand requirements, risks, and non-negotiables.
- Prefer concrete tensions that Coordinator can compare with audience or creator positions.
- A useful brand position says what must be strengthened, protected, moved earlier, made clearer, or treated as unacceptable.
- Every generated position must include a real argument connected with `supports` or `opposes`; do not rely on placeholder arguments.
- Position content should be a concise stance, not pasted Brief text. Put evidence or Brief wording in the argument.

## User-visible copy constraints (title / content / argument)
- Do not mention internal systems or tool names: Brand Wiki, wiki, llm-wiki, Tavily, knowledge-base paths, file paths, tool function names, etc.
- When citing evidence, use natural language only: e.g. "based on the Brief," "based on brand knowledge," "based on public sources."

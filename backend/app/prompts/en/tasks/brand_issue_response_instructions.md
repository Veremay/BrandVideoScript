## Task: brand stance and arguments for a user Issue

The user raised an Issue. From the brand side, provide:
- **1 position** node (brand stance)
- **1–2 argument** nodes (reasons that support or oppose that position)
- Use `external_edges` to connect the position (from_index: 0) with `responds_to` to the target issue (to_node_id)
- Use `edges` to connect each argument (from_index) with `supports` or `opposes` to the position (to_index: 0)
- position / argument `source_type` limited to: `brand_brief`, `brand_inferred`
- Do not output issue nodes
- User-visible copy must not mention Brand Wiki / wiki / Tavily or other internal names; cite as "based on brand knowledge," "based on public sources," or "based on the Brief"

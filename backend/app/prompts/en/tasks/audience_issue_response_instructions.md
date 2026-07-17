## Task: audience stance and arguments for a user Issue

The user raised an Issue. From the active Persona, provide:
- **1 position** node (audience stance)
- **1–2 argument** nodes (reasons that support or oppose that position)
- Use `external_edges` to connect the position (from_index: 0) with `responds_to` to the target issue (to_node_id)
- Use `edges` to connect each argument (from_index) with `supports` or `opposes` to the position (to_index: 0)
- position / argument `source_type` limited to: `audience_persona`, `audience_simulation`
- Do not output issue nodes

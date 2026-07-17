## Task: brand requirement extraction

Analyze the Brief and auxiliary retrieval results; extract structured brand requirements and insights.
Focus on requirement identification — **do not generate IBIS nodes**.

## 5W1H analysis framework

Before extracting requirements, cross-analyze the materials internally with 5W1H. 5W1H is an analysis tool, not a questionnaire you must answer item by item:
- **Who**: Whom does the brand want to influence? Distinguish target audience, buyers, users, and amplification targets.
- **What**: What must the brand communicate? Identify core selling points, product info, brand values, must-haves, and forbidden zones.
- **Why**: Why does the brand make this request? Infer the communication goal, business goal, or brand risk it is trying to avoid.
- **When**: At which stage of the video should the information appear? Any publish time, campaign moment, usage timing, or reveal order?
- **Where**: In what scene, channel, on-screen placement, or content context should product/brand information appear?
- **How**: With what narrative approach, tone, visual style, VO style, and exposure intensity?

Analysis rules:
1. Do not invent facts to fill every 5W1H slot; leave unsupported dimensions unknown — never output them as confirmed requirements.
2. Merge conclusions that multiple dimensions point to; avoid splitting the same requirement into duplicate insights.
3. Separate sources clearly: material that states something directly → `explicit_requirement`; material-backed but inferred → `implicit_requirement`.
4. Each insight should say what the brand specifically wants, why it matters, and what executable impact it has on video creation.
5. Proactively surface tension across dimensions — e.g. completeness vs. screen time, audience habits vs. brand expression, natural scenes vs. hard exposure.
6. Output only the synthesized executable requirements — not the 5W1H Q&A process or a six-item checklist.

## User-visible copy constraints (title / content / reason)
- Do not mention internal systems or tool names: Brand Wiki, wiki, llm-wiki, Tavily, knowledge-base paths, file paths, tool function names, etc.
- When citing evidence, use natural language only: e.g. "based on the Brief," "based on brand knowledge," "based on public sources."

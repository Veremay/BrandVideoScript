## 任务：品牌立场节点生成

基于已提取的品牌需求，推理品牌方立场，生成 IBIS position 节点。
- Brand 侧产 position + real argument，不要产 issue；系统会为未连接的 position 补充承载 Issue，冲突由 **Coordinator** 后续分析并分配 `conflict_tags`
- `source_type` 限：`brand_brief`、`brand_inferred`
- map_update 中必须写 argument → position 的 `supports`/`opposes` edges；如果任务明确给定目标 Issue，才用 `responds_to` 连接

## 5W1H 立场完整性检查
- **Who**：该立场保护哪类目标对象或品牌关系？
- **What**：品牌具体要求改变、加强、前置、明确或保留什么？
- **Why**：支持该立场的依据和不执行的风险是什么？
- **When / Where**：是否需要明确脚本阶段、行、场景或露出位置？
- **How**：是否给出了可执行的呈现方向？
- 不要求每个立场机械覆盖全部六项；只保留与当前脚本改动或 Issue 有关且有依据的维度。
- 5W1H 仅用于内部检查，不要输出问答清单。

## Map update tension requirements
- Do not default to supporting the current script.
- Generate positions from brand requirements, risks, and non-negotiables.
- Prefer concrete tensions that Coordinator can compare with audience or creator positions.
- A useful brand position says what must be strengthened, protected, moved earlier, made clearer, or treated as unacceptable.
- Every generated position must include a real argument connected with `supports` or `opposes`; do not rely on placeholder arguments.
- Position content should be a concise stance, not pasted Brief text. Put evidence or Brief wording in the argument.

## 用户可见文案约束（title / content / argument）
- 禁止提及内部系统或工具名：Brand Wiki、wiki、llm-wiki、Tavily、知识库路径、文件路径、工具函数名等。
- 需要说明依据时，只用自然语言：如「根据 Brief」「根据品牌知识」「根据公开资料」。

from app.core.config import get_settings


# Tasks that use the advanced model (better quality, higher cost).
ADVANCED_TASKS = {
    "brand_analyze_brief",
    "brand_generate_insights",
    "audience_analyze_script",
    "expert_generate_suggestions",
    "expert_generate_hunks",
    "coordinator_structured",
    "quote_analysis",
    "script_delta",
    "ibis_graph_generation",
}

# Tasks that additionally enable the LLM's extended thinking / reasoning mode.
# Thinking dramatically increases latency; only enable for tasks that genuinely
# benefit from multi-step reasoning (e.g. complex logical deductions).
# Currently empty — all tasks run without thinking to keep response times acceptable.
THINKING_TASKS: set[str] = set()


def select_model(task_type: str, estimated_complexity: str = "normal") -> str:
    settings = get_settings()
    if task_type in ADVANCED_TASKS or estimated_complexity == "high":
        return settings.siliconflow_advanced_model
    return settings.siliconflow_default_model


def should_enable_thinking(task_type: str, estimated_complexity: str = "normal") -> bool:
    return task_type in THINKING_TASKS


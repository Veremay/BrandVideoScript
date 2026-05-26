from app.core.config import get_settings


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


def select_model(task_type: str, estimated_complexity: str = "normal") -> str:
    settings = get_settings()
    if task_type in ADVANCED_TASKS or estimated_complexity == "high":
        return settings.siliconflow_advanced_model
    return settings.siliconflow_default_model


def should_enable_thinking(task_type: str, estimated_complexity: str = "normal") -> bool:
    return task_type in ADVANCED_TASKS or estimated_complexity == "high"


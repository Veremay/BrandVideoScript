import { insightsFromProject } from "@/lib/brandRequirements";
import type { Project } from "@/lib/types";

export type ProjectSetupStatus = {
  requirementsComplete: boolean;
  personaComplete: boolean;
  complete: boolean;
  explicitCount: number;
  implicitCount: number;
  personaCount: number;
};

export function getProjectSetupStatus(project: Project): ProjectSetupStatus {
  if ((project.mode ?? project.current_script.settings?.mode) === "vanilla") {
    const complete = project.vanilla_setup_stage === "complete";
    return {
      requirementsComplete: project.vanilla_setup_stage !== "requirements",
      personaComplete: complete,
      complete,
      explicitCount: 0,
      implicitCount: 0,
      personaCount: project.personas.length
    };
  }

  const insights = insightsFromProject(project);
  const explicitCount = insights.explicit.length;
  const implicitCount = insights.implicit.length;
  const personaCount = project.personas.length;
  const activePersonaExists = Boolean(
    project.active_persona_id &&
      project.personas.some((persona) => persona.persona_id === project.active_persona_id)
  );

  const requirementsComplete =
    project.brief.parse_status === "parsed" && explicitCount > 0 && implicitCount > 0;
  const personaComplete = personaCount > 0 && activePersonaExists;

  return {
    requirementsComplete,
    personaComplete,
    complete: requirementsComplete && personaComplete,
    explicitCount,
    implicitCount,
    personaCount
  };
}

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
    const requirementsComplete = Boolean(project.vanilla_setup_data?.brand_requirements?.trim());
    const conflictsComplete = Boolean(project.vanilla_setup_data?.conflicts?.trim());
    const personaCount = project.personas.length;
    const activePersonaExists = Boolean(
      project.active_persona_id &&
        project.personas.some((persona) => persona.persona_id === project.active_persona_id)
    );
    const personaComplete = personaCount > 0 && activePersonaExists;
    // Persona is optional for vanilla — editor unlocks with requirements + conflicts.
    const complete =
      project.vanilla_setup_stage === "complete" || (requirementsComplete && conflictsComplete);

    return {
      requirementsComplete,
      personaComplete,
      complete,
      explicitCount: 0,
      implicitCount: 0,
      personaCount
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

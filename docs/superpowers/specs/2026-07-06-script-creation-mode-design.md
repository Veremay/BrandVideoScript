# Script Creation Mode Design

Projects have two modes: `full` uses the system-assisted workspace, while `vanilla` uses only the plain LLM chat. The mode must be chosen when the project and initial script are created, then persisted with the project and script. Runtime settings should not change a project's mode after creation.

Architecture: the backend owns the persisted `mode` and creates `current_script.settings` from that mode. The frontend creation dialog passes the selected mode to `POST /projects`, then derives editor behavior from `project.mode` instead of localStorage. Existing projects without `mode` are treated as `full`.

Testing: backend unit tests cover `default_script(mode)` settings. Frontend typecheck covers API/type propagation and UI wiring.

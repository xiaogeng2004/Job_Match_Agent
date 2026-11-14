# Open-source Skill Usage

## frontend-design

- Source: <https://github.com/anthropics/claude-plugins-official>
- Skill path: `plugins/frontend-design/skills/frontend-design`
- Pinned commit: `a1ecfbc7f138a0ef455088f7f28cda2d22a0f853`
- License: Apache-2.0
- Local copy: `third_party/skills/frontend-design/`

### What the skill solves

The `frontend-design` skill provides a design-review process: establish a
specific direction, define a small design-token system, avoid generic visual
defaults, keep copy functional, and verify accessibility, responsive behavior,
focus states, and restraint.

### How it is integrated

The Agent uses the skill as a front-end quality gate rather than as a runtime
LLM dependency. `scripts/check_frontend_design_skill.py` validates:

- centralized color, spacing, radius, and shadow tokens;
- absence of gradients and glow treatments;
- keyboard focus and reduced-motion support;
- responsive layout;
- a single functional page heading;
- a plain text brand;
- the grayscale review hook.

The resulting report is saved to `models/frontend_skill_report.json`.

### Inputs and outputs

Inputs:

- `static/app.css`;
- `templates/index.html`;
- `static/app.js`;
- the pinned skill instructions.

Outputs:

- pass/fail checks with an explicit reason for each design constraint;
- source, commit, and license metadata.

### Modifications and adaptation

The upstream skill describes a design-review workflow but has no executable
validator for this project. The adapter converts its principles into
project-specific, deterministic checks. It does not modify the upstream skill
text. The local copy is retained only for auditability.

### Permissions and external services

The validator runs locally and needs no API key, login, external service, or
network access after the source has been vendored.

### Limitations

- Automated checks verify structural design rules, not aesthetic quality.
- Final visual review still requires screenshots at desktop and mobile sizes.
- The skill is used for UI quality assurance, not for job matching predictions.


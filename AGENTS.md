# Project Instructions

## Milestone planning workflow

Use just-in-time planning. Fully plan only the milestone currently being prepared or implemented; keep later milestones at the approved milestone level until their turn.

For every functional milestone, follow this order:

1. **Feature specification**
   - Create `docs/milestones/m<N>-<short-name>/feature-spec.md` before technical or implementation
     planning for the milestone.
   - Define actors and permissions, preconditions, normal flow, validation, edge cases, data
     effects, acceptance criteria, and explicit exclusions.
   - Reconcile the specification with `docs/product/mvp-requirements.md` and
     `docs/product/roadmap.md`.

2. **Milestone technical refinement**
   - After the feature specification is reviewed, create
     `docs/milestones/m<N>-<short-name>/technical-design.md` or explicitly update the project
     technical design.
   - Define the models/fields, constraints, services, transaction boundaries, views/forms/URLs,
     templates/JavaScript interactions, permissions, and tests required by the approved feature
     behaviour.
   - Do not introduce speculative functionality from later milestones.

3. **Development tasks**
   - Immediately before implementation, create
     `docs/milestones/m<N>-<short-name>/development-tasks.md` from the approved feature
     specification and technical refinement.
   - Break work into ordered, small, verifiable tasks with dependencies and acceptance criteria.
   - Do not create implementation tasks while material feature or technical decisions remain unresolved.

4. **Milestone planning review**
   - After development tasks are written and before implementation begins, review the feature
     specification, milestone technical refinement, and development tasks together against
     `docs/product/mvp-requirements.md`, `docs/product/roadmap.md`,
     `docs/architecture/technical-design.md`, completed milestone
     behavior, and the current codebase.
   - Check for contradictions, missing requirements, unjustified scope growth, unsafe assumptions,
     incomplete acceptance coverage, dependency/order problems, and designs that conflict with the
     overall project.
   - Fix every issue found in the appropriate planning document, then repeat the review until the
     three documents are mutually consistent and implementation-ready.
   - Record the review result in the milestone planning documents or development-task document.

5. **Implementation and verification**
   - Implement only after the planning and review stages above are complete.
   - Test against the feature acceptance criteria and the milestone exit criteria.
   - Record completion evidence in `docs/milestones/m<N>-<short-name>/completion.md` before
     preparing the next milestone.
   - At milestone completion, tell the user whether manual verification is recommended or required.
   - When manual verification is applicable, provide a concise, ordered checklist with setup,
     actions, expected results, and any hardware or offline checks that automated tests cannot
     prove. Clearly distinguish required release checks from optional confidence checks.

Do not skip, reorder, or combine these stages unless the user explicitly changes the workflow. If a requested action appears to skip a required stage, identify the missing stage before implementing.

## Milestone 0 exception

Milestone 0 is a non-functional technical-foundation milestone. It does not require a feature
specification or milestone-specific technical addendum because
`docs/architecture/technical-design.md` is its design input. Its valid sequence is:

1. Approved requirements and milestones.
2. Project-level `docs/architecture/technical-design.md`.
3. `docs/milestones/m0-foundation/development-tasks.md`.
4. Implementation and verification.

The custom user, shop, and terminal foundations belong to Milestone 0 because the custom Django user model must exist before the first project migration. User-facing authentication and user-management behaviour remains a Milestone 1 feature.

## Frontend styling

- Use Tailwind CSS with Django templates for application styling.
- Compile Tailwind locally during development/build and serve only generated local CSS at runtime.
- Do not use Tailwind Play CDN or any other runtime CDN dependency.
- Exact-pin the Tailwind and CLI versions when the build pipeline is introduced.
- Keep custom JavaScript minimal and locally bundled.

## Frontend verification

- Do not perform manual browser, visual, responsive-layout, hardware-scanner, focus-behaviour, or
  other hands-on frontend verification unless the user explicitly asks for it.
- Automated server-side, template, and JavaScript tests may still be run as implementation checks;
  they do not replace user frontend acceptance.
- Tell the user when frontend verification is required and provide concise setup, action, and
  expected-result steps for the user to perform.

## Model and reasoning effort

- Use GPT-5.6 Sol with high reasoning effort for project subagents, delegated work, and independent
  review whenever a model/effort override is available.
- Do not use extra-high or higher reasoning effort for this project unless the user explicitly
  changes this instruction.

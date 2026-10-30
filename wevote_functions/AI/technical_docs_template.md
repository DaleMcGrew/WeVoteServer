# Software Feature Documentation Template

Use this template to document a single software feature, capability, API surface, library addition, class, module, or tool integration. The structure is designed so a human can quickly scan it and an AI system can both extract information from the final document and infer what belongs in each section when generating documentation from source code.

## AI-first usage modes

This template supports two different AI workflows.

1. **Extraction mode**: a finished document is parsed by an AI system.
2. **Generation mode**: an AI system receives source material such as code, tests, comments, API schemas, or design notes and fills in this template.

For generation mode, the section instructions below tell the AI:
- what kind of evidence to use,
- what content belongs in each section,
- what content does not belong there,
- what format to produce,
- and how to handle uncertainty.

> **CRITICAL — authoring-only scaffolding must never appear in generated documents.**
> Everything from the top of this file down to the `---` separator that precedes `# Feature: <Feature Name>` is guidance for the author/AI only. In addition, the following per-section subsection headings and their bodies are authoring guidance and MUST be stripped from any generated document: `### Purpose`, `### AI should use`, `### Do not put here`, `### AI guidance`, `### Fill in`, `### Instructions`, `### Recommended format`, `### Authoring guidance`, and `### Recommended prompting pattern`.
> **Section `## 0. Source handoff` is authoring/auditing metadata and is itself authoring-only: fill it in while working so provenance and confidence are tracked, but do NOT include section 0 in the generated document. Begin the generated document at `## 1. Metadata`.**
> **Sections `## 19. Documentation-generation prompt block` and `## 20. Review checklist` are AI/authoring tooling and must NOT appear in the generated document. The generated document ends after `## 18. AI extraction block`.**
> **Authoring-only table columns must be dropped from the generated document.** Any table column labeled `Required values / format` (or otherwise marked as authoring guidance) exists to tell the author what shape/format a cell should take; omit that column from generated tables and keep only the content columns.
> **Authoring-only variant selectors must be dropped.** Headings of the form `#### If this is a ...` (e.g. in section 4) are variant selectors. Choose the matching variant, then emit only its filled-in content directly under the numbered section heading; do NOT include the `#### If this is a ...` heading or any non-matching variants.
> A generated document contains ONLY: the `# Feature: <name>` title, each numbered `## N. <Title>` heading starting at section 1, and the actual filled-in content (bullets, tables, code examples, and YAML) that lives under those sections. Emit the `### Fill in` bullets, tables, and examples directly under the numbered section heading — do not carry the `### Fill in` label or any other scaffolding heading into the output.

## Authoring rules

- One document per feature.
- Replace bracketed placeholders like `<Feature Name>` with concrete values.
- Keep headings unchanged when possible so readers and AI systems can depend on a stable schema.
- Prefer short paragraphs, bullet lists, and tables over dense prose.
- Use explicit values instead of vague language like "usually", "some", or "varies".
- When something does not apply, write `Not applicable` rather than deleting the section.
- When information is unknown, write `Unknown` and briefly state what evidence was missing.
- Do not invent behavior that is not supported by code, tests, comments, schemas, or examples.
- If code and comments disagree, prefer code and note the mismatch.
- For code examples, keep examples minimal but executable where possible.
- For structured values such as parameters, error codes, return fields, or class members, use tables.

## AI generation instructions

Use the rules below when an AI is given raw inputs such as class code, module code, API handlers, docstrings, tests, or usage examples.

### Accepted source inputs
- Source code
- Type hints and signatures
- Docstrings and inline comments
- Tests
- Example snippets
- API schemas or OpenAPI specs
- Error definitions and exception classes
- Changelog or pull request summaries

### Evidence priority
When filling the template, use evidence in this order unless the user says otherwise.

1. Executable code and type signatures
2. Tests
3. Schemas and configuration definitions
4. Docstrings and comments
5. Usage examples
6. Changelog or design notes

### Inference rules
- Infer purpose from names, signatures, control flow, tests, and surrounding module structure.
- Infer constraints from validation logic, type hints, assertions, schema rules, and exception branches.
- Infer side effects from I/O, database writes, network calls, event emission, file access, cache operations, and mutable state changes.
- Infer relationships from imports, composition, inheritance, callbacks, emitted events, and invoked collaborators.
- Infer typical usage from tests and examples before inventing an example.
- If a fact is only partially supported, state it conservatively.
- If something cannot be known from the inputs, mark it `Unknown`.

### Writing style and audience

> **Authoring-only guidance.** These rules shape how generated content is written. They must NOT appear as text in the generated document; instead, the generated content should already follow them.

The primary audience for generated documents is **junior-to-mid-level software engineers**. Write so a competent engineer who is new to this specific feature can understand it quickly.

- **Lead with a mental model.** Before dense rules, tables, or constraints, give a short plain-language model of how the feature works (its main concepts and how they relate). One or two sentences is usually enough.
- **Explain the "why", not just the "what".** For every constraint, invariant, gotcha, or error condition, state the reason behind it. For example, do not just write "cannot call `start` on a context while its last snapshot has no `end`"; also explain why (a still-open snapshot means the previous timing was never closed, so starting again would lose or corrupt that measurement).
- **Use plain language and concrete terms.** Prefer concrete nouns and verbs over abstract or terse phrasing. Define domain terminology the first time it appears.
- **Prefer worked examples.** When a rule or flow is non-obvious, show a short concrete example rather than only describing it.
- **Keep error-recovery guidance actionable.** Tell the reader what to do next after a failure, not just that a failure can occur.
- **Do not over-explain basics.** Assume general programming literacy (functions, dictionaries, exceptions, HTTP, etc.). Spend words on what is specific to this feature, not on universal fundamentals.

### Output rules for AI
- Never emit authoring-only scaffolding. Strip every `### Purpose`, `### AI should use`, `### Do not put here`, `### AI guidance`, `### Fill in`, `### Instructions`, `### Recommended format`, `### Authoring guidance`, and `### Recommended prompting pattern` heading (and its explanatory body) from the generated document. Keep only the numbered `## N.` sections and their filled-in content.
- Omit `## 0. Source handoff` entirely from the generated document; it is authoring/auditing metadata. Start the output at `## 1. Metadata`.
- Omit `## 19. Documentation-generation prompt block` and `## 20. Review checklist` entirely; they are AI/authoring tooling. The generated document ends after `## 18. AI extraction block`.
- Drop authoring-only table columns (e.g. `Required values / format` in section 3) from generated tables; keep only the content columns.
- Drop `#### If this is a ...` variant selector headings (e.g. in section 4); emit only the matching variant's content directly under the numbered section heading.
- Preserve the section order.
- Preserve heading names exactly.
- Use tables where the template asks for tables.
- Keep summary paragraphs under 4 sentences unless complexity requires more.
- Prefer concrete nouns and verbs over generic prose.
- Use backticks for code symbols, parameter names, types, environment variables, commands, and file paths.
- Do not repeat the same information in multiple sections unless the repeated form is intentionally normalized for AI extraction.
- Write for junior-to-mid-level engineers: lead conceptual sections with a short mental model, state rules in plain language, and explain the "why" behind every constraint, gotcha, and error condition. Prefer concrete worked examples and actionable error-recovery guidance; do not over-explain universal basics.

### Recommended prompting pattern
Use a handoff like this when asking an AI to fill the template:

```text
Task: Generate documentation using the provided Software Feature Documentation Template.
Scope: Document exactly one feature/class/module/API.
Instructions:
- Fill every section using only the supplied evidence.
- Do not invent unsupported behavior.
- If information is missing, write "Unknown".
- Preserve the numbered "## N." headings and tables.
- Do NOT include authoring-only scaffolding in the output: strip every "### Purpose", "### AI should use", "### Do not put here", "### AI guidance", "### Fill in", "### Instructions", "### Recommended format", "### Authoring guidance", and "### Recommended prompting pattern" heading. Emit filled-in content directly under the numbered section heading.
- Omit "## 0. Source handoff" from the output (authoring/auditing metadata only); begin the document at "## 1. Metadata".
- Omit "## 19. Documentation-generation prompt block" and "## 20. Review checklist"; they are AI/authoring tooling. End the document after "## 18. AI extraction block".
- Drop authoring-only table columns such as "Required values / format" (section 3); keep only the content columns.
- Drop "#### If this is a ..." variant selector headings (section 4); emit only the matching variant's content under the numbered section heading.
- Write for junior-to-mid-level engineers: lead conceptual sections with a short mental model, use plain language, and explain the "why" behind each constraint, gotcha, and error condition. Prefer concrete worked examples and actionable error-recovery guidance; do not over-explain universal basics.
- Use concise, technical language.
- Prefer code and tests over comments when they conflict.
Input material:
<paste code, tests, schemas, examples here>
```

---

# Feature: <Feature Name>

## 0. Source handoff

> **Authoring-only section.** Complete this while generating so the work is auditable, but do NOT include this section in the generated document. The finished document starts at `## 1. Metadata`.

### Purpose
Give an AI system a predictable place to list the evidence it used and the exact input scope. This makes generation easier and makes the final document auditable.

### Fill in
- **Documentation mode:** `<human-authored | AI-generated | human-edited AI draft>`
- **Primary source type:** `<class code | module code | API handler | OpenAPI spec | tests | mixed>`
- **Primary source location:** `<file path, repo path, URL, pasted snippet, commit hash>`
- **Secondary sources:** `<tests, examples, comments, changelog, PR, issue, design doc>`
- **Feature boundary:** `<what code is included vs excluded>`
- **Confidence level:** `<high | medium | low>`
- **Known ambiguities:** `<list any unresolved questions>`

### AI guidance
For AI generation, fill this section first. If the user says "here is the class code, now generate the documentation", record the class file or pasted class body as the primary source and list nearby tests or docstrings as secondary sources.

## 1. Metadata

### Purpose
Provide machine-readable and human-readable identifiers for the feature.

### AI should use
Names from code symbols, route names, module paths, package exports, release metadata, and user-provided labels.

### Do not put here
Behavior details, examples, or long rationale.

### Fill in
- **Feature name:** `<Canonical feature name>`
- **Short summary:** `<1-2 sentence plain-language description>`
- **Status:** `<Proposed | Experimental | Beta | Stable | Deprecated | Removed>`
- **Version added:** `<semver / release / date | Unknown>`
- **Last updated:** `<YYYY-MM-DD | Unknown>`
- **Owners:** `<team, maintainers, github handles, emails | Unknown>`
- **Audience:** `<application developers | library users | platform engineers | operators | internal services | other>`
- **Scope type:** `<API endpoint | library function | class | module | CLI command | framework feature | service capability | protocol | other>`
- **Related components:** `<list of packages, services, modules, repos>`
- **Tags:** `<comma-separated keywords>`

## 2. Problem and intent

### Purpose
Explain why the feature exists and what user or system problem it solves.

### AI should use
Docstrings, class names, module names, issue summaries, tests, and call patterns showing what the feature helps accomplish.

### Do not put here
Low-level parameter definitions, full API schemas, or method-by-method breakdowns.

### Fill in
- **Problem statement:** `<what was hard, missing, slow, unsafe, repetitive, or impossible before>`
- **Primary goal:** `<single most important outcome>`
- **Secondary goals:** `<other useful outcomes>`
- **Non-goals:** `<what this feature explicitly does not do>`
- **Target users:** `<who benefits from it>`
- **When to use it:** `<specific scenarios>`
- **When not to use it:** `<misuse cases, anti-patterns, cheaper alternatives>`

### Recommended format
Use 1 short paragraph for the problem statement, then bullets for goals and usage boundaries.

## 3. Conceptual model

### Purpose
Define the main mental model so both people and AI can understand the feature's role in the system.

### AI should use
Type definitions, domain objects, inheritance trees, composition relationships, state enums, and lifecycle behavior in code.

### Do not put here
Exact request payloads, raw code listings, or copy-pasted implementation details.

### Fill in
- **Core concept:** `<what the feature represents>`
- **Lifecycle:** `<how it starts, changes state, and ends>`
- **Key entities:** `<objects, resources, records, events, classes>`
- **State transitions:** `<if relevant>`
- **Relationship to existing features:** `<how it extends, replaces, wraps, or composes with older behavior>`

> **Authoring-only column.** The `Required values / format` column is format guidance for the author/AI. Drop it from the generated table — emit only the `Item` and `Description` columns.

| Item | Description | Required values / format |
|------|-------------|--------------------------|
| Core concept | `<definition>` | 1-2 sentences |
| Lifecycle | `<creation to completion>` | Ordered bullets or short paragraph |
| Key entities | `<names of objects>` | Comma-separated list |
| State transitions | `<states>` | `state_a -> state_b -> state_c` |
| Related features | `<dependencies or replacements>` | Bullet list |

## 4. Public interface

### Purpose
Describe exactly how a user or system interacts with the feature.

### AI should use
Function signatures, method definitions, exported names, class constructors, route declarations, CLI parsers, and schemas.

### Do not put here
Internal helper functions unless they are part of the supported interface.

### Fill in
Document every public entry point that exposes this feature.

> **Authoring-only selectors.** The `#### If this is a ...` headings below are variant selectors. Pick the one matching the feature, fill in its bullets, and emit only that content directly under `## 4. Public interface` — do NOT include the `#### If this is a ...` heading (or the non-matching variants) in the generated document.

#### If this is an API
- **Method:** `<GET | POST | PUT | PATCH | DELETE | other>`
- **Path:** `<route>`
- **Authentication:** `<required auth>`
- **Authorization:** `<roles / scopes / permissions>`

#### If this is a library function or method
- **Symbol name:** `<function/method/class name>`
- **Namespace/module:** `<module path>`
- **Signature:** `<typed signature>`
- **Visibility:** `<public | internal | protected | private-like convention>`

#### If this is a class
- **Constructor signature:** `<constructor signature>`
- **Primary methods:** `<list>`
- **Mutable state:** `<state fields and invariants>`

#### If this is a CLI/tool feature
- **Command:** `<command name>`
- **Arguments:** `<positional args>`
- **Flags:** `<flags>`
- **Exit codes:** `<code meanings>`

| Name | Kind | Type | Required | Default | Description | Constraints |
|------|------|------|----------|---------|-------------|-------------|
| `<param>` | `<path/query/body/arg/field>` | `<type>` | `<yes/no>` | `<value>` | `<meaning>` | `<range, enum, format>` |

## 5. Input contract

### Purpose
Specify what callers must provide.

### AI should use
Type hints, validators, schema definitions, assertions, default values, overloads, and parsing code.

### Do not put here
Returned values, downstream side effects, or business rationale.

### Fill in
- **Accepted input types:** `<json schema, python types, protobuf message, CLI args, etc.>`
- **Validation rules:** `<length limits, formats, allowed ranges, regexes, uniqueness rules>`
- **Required fields:** `<explicit list>`
- **Optional fields:** `<explicit list>`
- **Derived fields:** `<computed internally>`
- **Defaults:** `<default behavior when omitted>`
- **Invalid input behavior:** `<error or fallback behavior>`

| Field / Argument | Type | Required | Default | Allowed values / format | Validation notes |
|------------------|------|----------|---------|--------------------------|------------------|
| `<field>` | `<type>` | `<yes/no>` | `<value>` | `<enum, regex, shape>` | `<rules>` |

## 6. Output contract

### Purpose
Specify exactly what the feature returns, emits, mutates, or persists.

### AI should use
Return statements, response models, serializer code, events emitted, persistence writes, and state mutations.

### Do not put here
Caller instructions about recovery, unless directly describing partial success semantics.

### Fill in
- **Return type / response shape:** `<json, object, tuple, file, event, stream>`
- **Success conditions:** `<what must be true on success>`
- **Side effects:** `<db writes, cache changes, events emitted, files created>`
- **Partial success behavior:** `<if batch or async>`
- **Idempotency behavior:** `<same input repeated>`
- **Ordering guarantees:** `<if relevant>`
- **Consistency guarantees:** `<eventual, strong, best effort>`

| Output field / effect | Type | Present when | Description |
|-----------------------|------|--------------|-------------|
| `<field>` | `<type>` | `<always / conditional>` | `<meaning>` |

## 7. Functions and responsibilities

### Purpose
Explain what each function, method, class member, or module export is for.

### AI should use
Public methods, exported functions, notable internal collaborators that are necessary to understand the feature, and tests that reveal intended behavior.

### Do not put here
Implementation trivia that does not change how the feature should be used or understood.

### Fill in
Create one row per callable or exported symbol.

| Symbol | Kind | Responsibility | Inputs | Outputs | Side effects | Typical caller |
|--------|------|----------------|--------|---------|--------------|----------------|
| `<name>` | `<function/method/class/export>` | `<what it is for>` | `<key args>` | `<return value>` | `<none or details>` | `<who calls it>` |

### Authoring guidance
- Use action verbs in the Responsibility column, such as `Creates`, `Validates`, `Fetches`, `Transforms`, `Schedules`, or `Serializes`.
- Keep each responsibility to one sentence.
- If a symbol is internal-only, mark that clearly in the Kind or Typical caller column.

## 8. Interaction patterns

### Purpose
Show how the feature is typically used in real workflows.

### AI should use
Tests, examples, call sites, integration code, and route/service orchestration.

### Do not put here
Exhaustive parameter tables or duplicate method summaries.

### Fill in
Document the main interaction styles.

- **Basic flow:** `<simplest successful path>`
- **Advanced flow:** `<common non-trivial path>`
- **Async flow:** `<if relevant>`
- **Error recovery flow:** `<what callers should do after failure>`
- **Integration points:** `<other APIs, hooks, callbacks, queues, storage, frameworks>`

### Recommended format
Use numbered steps for each flow.

## 9. Examples

### Purpose
Provide concrete examples that are easy for humans to learn from and easy for AI systems to pattern-match.

### AI should use
Existing tests, usage snippets, README examples, or minimal examples derived directly from the interface and validation rules.

### Do not put here
Examples that rely on unsupported assumptions or hidden setup without explanation.

### Fill in
Provide at least one minimal example and one realistic example.

#### Minimal example
```<language>
<smallest valid example>
```

**Expected result**
```text
<output, return value, visible effect>
```

#### Realistic example
```<language>
<production-like example>
```

**Expected result**
```text
<output, response body, generated objects, state changes>
```

## 10. Error handling

### Purpose
Define failure modes clearly.

### AI should use
Exception classes, error codes, guard clauses, validation failures, timeout paths, and retry logic in tests or callers.

### Do not put here
Happy-path outputs or performance notes.

### Fill in
- **User-visible errors:** `<bad request, unauthorized, timeout, not found, etc.>`
- **Internal failures:** `<dependency outage, DB deadlock, cache miss, malformed state>`
- **Retryable errors:** `<which errors can be retried>`
- **Non-retryable errors:** `<which errors require caller changes>`
- **Fallback behavior:** `<graceful degradation, noop, cached result, fail closed>`

| Error code / exception | Layer | Cause | Retryable | Caller action | Notes |
|------------------------|-------|-------|-----------|---------------|-------|
| `<error>` | `<api/library/system>` | `<reason>` | `<yes/no/depends>` | `<what to do>` | `<details>` |

## 11. Performance characteristics

### Purpose
Help readers and AI systems understand scale, cost, and limits.

### AI should use
Benchmarks, tests, explicit limits in code, algorithm structure, batching logic, and rate limiter settings.

### Do not put here
Speculative performance claims not grounded in evidence.

### Fill in
- **Expected latency:** `<p50/p95 if known | Unknown>`
- **Time complexity:** `<big-O if useful | Unknown>`
- **Space complexity:** `<big-O if useful | Unknown>`
- **Throughput expectations:** `<requests/sec, jobs/min, rows/sec | Unknown>`
- **Size limits:** `<payload, batch size, file size | Unknown>`
- **Rate limits:** `<per user/token/ip/system | Unknown>`
- **Resource usage:** `<cpu, memory, network, I/O | Unknown>`

| Metric | Value | Conditions | Notes |
|--------|-------|------------|-------|
| `<metric>` | `<value>` | `<load / environment>` | `<details>` |

## 12. Security and safety

### Purpose
Document trust boundaries and misuse risks.

### AI should use
Auth middleware, permission checks, input sanitization, redaction logic, secret handling, and audit events in code or config.

### Do not put here
General security philosophy that does not specifically apply to the feature.

### Fill in
- **Auth requirements:** `<none/api key/oauth/session/mTLS>`
- **Permissions needed:** `<roles/scopes>`
- **Sensitive inputs:** `<PII, secrets, tokens, file uploads>`
- **Sensitive outputs:** `<returned confidential data>`
- **Abuse risks:** `<enumeration, injection, amplification, privilege misuse>`
- **Mitigations:** `<validation, escaping, rate limiting, auditing>`
- **Audit events:** `<what gets logged>`
- **Safe defaults:** `<least privilege, deny by default, read-only mode>`

## 13. Configuration and environment

### Purpose
State what must be configured for the feature to work.

### AI should use
Environment variables, feature flags, settings modules, dependency injection wiring, service clients, and version constraints.

### Do not put here
Detailed troubleshooting steps unless config is the root cause.

### Fill in
- **Environment variables:** `<name, required, default, secret?>`
- **Feature flags:** `<flag names and rollout behavior>`
- **External dependencies:** `<services, databases, queues, SDKs>`
- **Supported environments:** `<dev/staging/prod/local>`
- **Compatibility:** `<language/runtime/framework/version requirements>`

| Setting / dependency | Required | Default | Example | Description |
|----------------------|----------|---------|---------|-------------|
| `<name>` | `<yes/no>` | `<value>` | `<sample>` | `<purpose>` |

## 14. Observability

### Purpose
Show how to inspect and debug the feature.

### AI should use
Logger calls, metric names, trace spans, health checks, debug commands, and monitoring docs.

### Fill in
- **Logs emitted:** `<log names, key fields>`
- **Metrics:** `<counters, histograms, gauges>`
- **Traces:** `<span names and important attributes>`
- **Health signals:** `<what indicates the feature is working>`
- **Debug procedure:** `<first steps when something goes wrong>`

## 15. Compatibility and migration

### Purpose
Help readers adopt the feature safely over time.

### AI should use
Deprecation annotations, changelog entries, old/new code paths, adapter layers, and version guards.

### Fill in
- **Backward compatibility:** `<compatible, partially compatible, breaking>`
- **Migration path:** `<how to move from old behavior>`
- **Deprecated behavior:** `<what will be removed and when>`
- **Version-specific notes:** `<differences by release>`

## 16. Known limitations

### Purpose
Be explicit about boundaries so misuse is less likely.

### AI should use
Guard clauses, TODOs, unsupported branches, feature flags, skipped tests, documented caveats, and hard-coded limits.

### Fill in
- **Unsupported cases:** `<not supported inputs or workflows>`
- **Operational limits:** `<scale ceilings, single-region assumptions, timeout windows>`
- **Behavioral caveats:** `<surprising but intended behavior>`
- **Open issues:** `<links or IDs>`

## 17. Related references

### Purpose
Link this feature to the rest of the system and documentation set.

### AI should use
Import graph, source paths, tests, design docs, routes, schemas, changelog entries, issue IDs, and runbooks.

### Fill in
- **Source files:** `<repo paths>`
- **Tests:** `<test paths>`
- **Design docs:** `<links>`
- **API references:** `<links>`
- **Runbooks:** `<links>`
- **Issue tracker items:** `<links or IDs>`
- **Changelog entries:** `<links or versions>`

## 18. AI extraction block

### Purpose
Provide a normalized section that an AI agent can parse with minimal ambiguity.

### Instructions
- Keep keys unchanged.
- Prefer JSON-like values, but plain text is acceptable where noted.
- Use explicit `null` for unknown values.
- Keep arrays as YAML lists.
- Ensure values match earlier sections.

```yaml
feature_name: <string>
summary: <string>
status: <string>
scope_type: <string>
version_added: <string|null>
owners:
  - <string>
audience:
  - <string>
source_handoff:
  documentation_mode: <string>
  primary_source_type: <string>
  primary_source_location: <string>
  secondary_sources:
    - <string>
  confidence_level: <high|medium|low>
entry_points:
  - name: <string>
    kind: <api|function|method|class|module|cli|event>
    signature_or_path: <string>
    visibility: <string|null>
inputs:
  - name: <string>
    type: <string>
    required: <true|false>
    default: <string|null>
    constraints: <string|null>
outputs:
  - name: <string>
    type: <string>
    description: <string>
side_effects:
  - <string>
responsibilities:
  - symbol: <string>
    responsibility: <string>
    typical_caller: <string|null>
error_modes:
  - code_or_type: <string>
    retryable: <true|false|depends>
    meaning: <string>
limits:
  rate_limit: <string|null>
  payload_limit: <string|null>
  latency_expectation: <string|null>
security:
  auth: <string>
  permissions: <string>
  sensitive_data: <string|null>
relationships:
  depends_on:
    - <string>
  emits_to:
    - <string>
  called_by:
    - <string>
related_components:
  - <string>
example_files:
  - <string>
unknowns:
  - <string>
```

## 19. Documentation-generation prompt block

> **Authoring/AI-only section.** This is tooling for generating docs; do NOT include it in the generated document.

### Purpose
Give a ready-to-copy instruction block for asking an AI to generate this document from code.

### Copyable prompt
```text
You are generating a software feature documentation page from source material.

Use the exact Markdown structure below.
Rules:
- Fill every section in order.
- Keep the numbered "## N." headings unchanged.
- Do NOT include authoring-only scaffolding in the output: strip every "### Purpose", "### AI should use", "### Do not put here", "### AI guidance", "### Fill in", "### Instructions", "### Recommended format", "### Authoring guidance", and "### Recommended prompting pattern" heading and its explanatory body. The generated document contains only the "# Feature" title, the numbered sections, and their filled-in content.
- Omit "## 0. Source handoff" from the output (authoring/auditing metadata only); begin the document at "## 1. Metadata".
- Omit "## 19. Documentation-generation prompt block" and "## 20. Review checklist"; they are AI/authoring tooling. End the document after "## 18. AI extraction block".
- Drop authoring-only table columns such as "Required values / format" (section 3); keep only the content columns.
- Drop "#### If this is a ..." variant selector headings (section 4); emit only the matching variant's content under the numbered section heading.
- Write for junior-to-mid-level engineers: lead conceptual sections with a short mental model, use plain language, and explain the "why" behind each constraint, gotcha, and error condition. Prefer concrete worked examples and actionable error-recovery guidance; do not over-explain universal basics.
- Use only evidence from the provided material.
- If something is missing, write "Unknown".
- Do not invent performance numbers, security guarantees, or side effects.
- Prefer code and tests over comments when they conflict.
- Use tables where requested.
- Use backticks for symbols, types, paths, commands, and config names.
- For "Functions and responsibilities", describe what each public symbol is for in one sentence.
- For "Examples", derive the minimal valid example from the code or tests.
- For the "AI extraction block", normalize the same facts without adding new ones.

Now generate the document for this input:
<paste class code, module code, API code, tests, schema, or examples here>
```

## 20. Review checklist

> **Authoring/AI-only section.** This checklist is for the author/AI to self-review; do NOT include it in the generated document.

### Purpose
Ensure the document is complete, consistent, and AI-friendly.

- [ ] The feature name matches code and user-facing terminology.
- [ ] The Source handoff section identifies the actual evidence used.
- [ ] All public entry points are documented.
- [ ] Every parameter or argument has type, required status, and constraints.
- [ ] Output behavior and side effects are explicit.
- [ ] Error conditions include caller actions.
- [ ] At least one minimal example and one realistic example are included.
- [ ] Security considerations are documented.
- [ ] Compatibility and migration notes are present.
- [ ] The AI extraction block is filled in and consistent with the rest of the document.
- [ ] Unknown items are marked `Unknown`, `null`, or `Not applicable`, not omitted.
- [ ] No section contains guessed facts that are unsupported by the source material.
- [ ] Content is written for junior-to-mid-level engineers: conceptual sections lead with a short mental model, rules are in plain language, and the "why" behind constraints, gotchas, and error conditions is explained. Concrete worked examples and actionable error-recovery guidance are used; universal basics are not over-explained.
- [ ] No authoring-only scaffolding leaked into the document (no `### Purpose`, `### AI should use`, `### Do not put here`, `### AI guidance`, `### Fill in`, `### Instructions`, `### Recommended format`, `### Authoring guidance`, or `### Recommended prompting pattern` headings remain).
- [ ] `## 0. Source handoff` was completed for auditing but omitted from the generated document (the document starts at `## 1. Metadata`).
- [ ] `## 19. Documentation-generation prompt block` and `## 20. Review checklist` were omitted from the generated document (it ends after `## 18. AI extraction block`).
- [ ] Authoring-only table columns (e.g. `Required values / format` in section 3) were dropped from the generated tables.
- [ ] `#### If this is a ...` variant selector headings (section 4) were dropped; only the matching variant's content remains.

---

## Minimal starter copy

Use this shorter version when bootstrapping a new feature doc quickly or when prompting an AI with a single class or module.

```markdown
# Feature: <Feature Name>

## 0. Source handoff
- **Documentation mode:** AI-generated
- **Primary source type:** <class code | module code | API handler | mixed>
- **Primary source location:** <file path or pasted snippet>
- **Secondary sources:** <tests, comments, examples>
- **Feature boundary:** <what is in scope>
- **Confidence level:** <high | medium | low>
- **Known ambiguities:** <list or Unknown>

## 1. Metadata
- **Feature name:** <name>
- **Short summary:** <1-2 sentences>
- **Scope type:** <class | module | API | function | tool>
- **Audience:** <who this is for>

## 4. Public interface
| Name | Kind | Type | Required | Default | Description | Constraints |
|------|------|------|----------|---------|-------------|-------------|
|      |      |      |          |         |             |             |

## 6. Output contract
| Output field / effect | Type | Present when | Description |
|-----------------------|------|--------------|-------------|
|                       |      |              |             |

## 7. Functions and responsibilities
| Symbol | Kind | Responsibility | Inputs | Outputs | Side effects | Typical caller |
|--------|------|----------------|--------|---------|--------------|----------------|
|        |      |                |        |         |              |                |

## 10. Error handling
| Error code / exception | Layer | Cause | Retryable | Caller action | Notes |
|------------------------|-------|-------|-----------|---------------|-------|
|                        |       |       |           |               |       |

## 9. Examples
```<language>
<minimal example>
```

## 18. AI extraction block
```yaml
feature_name: <string>
summary: <string>
source_handoff:
  documentation_mode: AI-generated
  primary_source_type: <string>
  primary_source_location: <string>
entry_points: []
inputs: []
outputs: []
responsibilities: []
error_modes: []
unknowns: []
```
```

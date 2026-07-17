The last modification of the config.py end up not beed good. It become an spaguety of method to load the configuration on its own way. The current settings.json has global `ocr_model` and `language_model` and module specific `md_gen` and `md_mrg` sections. However the `src/common/config.py` is not following this structure to create the internal class configuration structures. We need the config.py to replicate it without specific logic for md_gen or md_mrg other than create the same structure as the json. It is responsibility of them in their respective module the extrat the required fields from AppConfig.

For example:
- `build_image_settings_from_args` is teking the values from the global json, not from `md_gen`
- `build_md_mrg_settings_from_json` is taking the correct fields from `md_mrg` but then in `build_md_mrg_config_from_args` it mixed in the language model from the arguments with the json, resulting in a broken MdMrgConfig with duplicated language settings.

# Goals

- Fix the config.py to be consistent with the json structure
- The ocr and llanguage model are global parameters, so md_mrg and md_gen must be consider this
- dont copy global configurations into local md_gen or md_mrg structures, this create duplicated fields
- The setting priorities are, first load the json, then overwrite with user provided argument if are not None.

# Refinement Iteration 1
**Status:** PENDING USER FEEDBACK

## 1. Executive Summary
This change requests a cleanup and normalization of the configuration loading behavior in `src/common/config.py` so the in-memory app configuration mirrors the JSON file structure exactly. Global model settings (`ocr_model`, `language_model`) must remain global and must not be duplicated inside module-specific config objects. Runtime arguments must override JSON values only when those argument values are explicitly provided (non-`None`).

## 2. Refined Requirements & Acceptance Criteria
- **Requirement CFG-001:** Preserve JSON Shape in AppConfig
	- **Description:** `AppConfig` construction must mirror `settings.json` with top-level global fields and distinct module sections (`md_gen`, `md_mrg`) without hardcoded module-specific extraction logic in shared config loading paths.
	- **Acceptance Criteria:**
		- [ ] Given a valid `settings.json` with global and module sections, When loading configuration, Then the produced config object contains the same structural hierarchy and corresponding values.
		- [ ] Given module-specific sections in JSON, When loading in `src/common/config.py`, Then no global settings are copied into `md_gen` or `md_mrg` substructures.

- **Requirement CFG-002:** Enforce Global Model Ownership
	- **Description:** `ocr_model` and `language_model` must be treated as global configuration only. Downstream modules may read them from the global config but must not receive duplicated model fields in their local settings objects from shared config assembly.
	- **Acceptance Criteria:**
		- [ ] Given JSON with `ocr_model` and `language_model`, When building module config objects, Then those model values are not duplicated as module-local fields unless explicitly present in the module section of JSON schema.
		- [ ] Given `md_mrg` config build flow, When arguments are applied, Then language model settings are not merged in a way that duplicates or conflicts with global model settings.

- **Requirement CFG-003:** Deterministic Override Priority
	- **Description:** Configuration precedence must be deterministic: load JSON first, then apply CLI/user argument overrides only for values that are not `None`.
	- **Acceptance Criteria:**
		- [ ] Given a JSON value and CLI argument as `None`, When building final config, Then the JSON value is preserved.
		- [ ] Given a JSON value and a non-`None` CLI argument value, When building final config, Then the CLI value overrides JSON.

- **Requirement CFG-004:** Remove Inconsistent Builder Behavior
	- **Description:** Current builder functions must be aligned so they do not read from incorrect sections or perform mixed-source merges that produce invalid structures.
	- **Acceptance Criteria:**
		- [ ] Given `build_image_settings_from_args`, When resolving values, Then it reads module-specific values from `md_gen` section instead of unrelated global/module paths.
		- [ ] Given `build_md_mrg_settings_from_json` and argument overlay logic, When producing final `MdMrgConfig`, Then there are no duplicated language settings and the structure is valid.
        **User: this were example, exten the check to every function.**

## 3. Scope & Constraints
- **In-Scope:**
	- Refactor and simplify `src/common/config.py` so the config representation and loading behavior match `settings.json`.
	- Correct precedence handling (JSON base + non-`None` CLI overrides).
	- Ensure shared config module remains generic and does not embed module-specific behavior beyond schema replication.
- **Out-of-Scope:**
	- Redesigning the JSON schema itself.
	- Changing OCR or markdown processing business logic in `md_gen` or `md_mrg`.
	- Introducing new runtime flags unrelated to config consistency and precedence.
- **Technical Constraints / Edge Cases:**
	- Missing optional sections in JSON should not crash config loading if defaults are defined.
	- Partial CLI overrides must update only targeted fields and preserve untouched JSON values.
	- Backward compatibility for existing `settings.json` files should be maintained where possible.

## 4. Open Design Choices (Questions for User)
- **[Business Logic]:** If a module section (`md_gen` or `md_mrg`) defines a key that is also present in global config, should module-local value always win for that module, or should this be treated as an invalid schema/state?
**User: If this is present in the setting in a local module, then the class structure will have it as well. But here it would be explicit in the json, not a programming error duplicating a field.**

- **[Technical]:** For nested objects under module sections, should CLI override semantics be full replacement of that object or field-by-field merge for only non-`None` fields?
**User: CLI override would be limited to globals or its own module fields. For example arguments pass to md_gen will not override those in md_mrg event if have the same name.**

- **[Technical]:** When required keys are missing from JSON and not provided by CLI, should loader fail fast with a validation error or use defaults when available?
**User: Yes, for now we want strict json setting file, so fail indicating the field is missing in the json.**

# Refinement Iteration 2
**Status:** LOCKED

## 1. Executive Summary
This iteration resolves the remaining design questions for the shared configuration cleanup in `src/common/config.py`. The target behavior is now fully specified: the in-memory configuration must mirror the JSON structure, global model settings remain owned by the top-level config, and CLI overrides apply only to relevant global or same-module fields when the provided value is not `None`.

## 2. Refined Requirements & Acceptance Criteria
- **Requirement CFG-001:** Preserve JSON Shape in AppConfig
	- **Description:** The shared configuration loader must construct `AppConfig` so its object hierarchy matches `settings.json` exactly, with top-level global fields and module-local sections preserved as distinct substructures.
	- **Acceptance Criteria:**
		- [ ] Given a valid `settings.json` with top-level `ocr_model`, top-level `language_model`, and module sections such as `md_gen` and `md_mrg`, When the shared loader builds `AppConfig`, Then the resulting object preserves the same top-level and nested section structure.
		- [ ] Given a key that appears only inside a module section in JSON, When configuration is loaded, Then that key exists only inside that module structure in `AppConfig`.
		- [ ] Given a key with the same name in both global and module-local sections, When configuration is loaded, Then both values are preserved in their respective scopes because the duplication is explicit in JSON rather than introduced by loader logic.

- **Requirement CFG-002:** Enforce Global Model Ownership Without Synthetic Duplication
	- **Description:** `ocr_model` and `language_model` are global settings by default and must not be copied into module-local structures by shared configuration code. If a module-local section explicitly defines similarly named fields in JSON, those fields remain only because they were declared in JSON.
	- **Acceptance Criteria:**
		- [ ] Given JSON where `ocr_model` and `language_model` exist only at the top level, When module-specific configuration data is assembled from `AppConfig`, Then no additional module-local copies of those settings are introduced by `src/common/config.py`.
		- [ ] Given JSON where a module section explicitly includes a model-related field, When configuration is loaded, Then that field is preserved in the module section without altering or overwriting the top-level global model settings.
		- [ ] Given the `md_mrg` build path, When CLI arguments and JSON are combined, Then the resulting configuration contains a single global source of language model settings unless the JSON itself explicitly defines an additional module-local field.

- **Requirement CFG-003:** Deterministic Override Priority
	- **Description:** Configuration precedence must be deterministic for every builder path: load required values from JSON first, then overlay CLI or user-provided arguments only for fields whose argument values are not `None`.
	- **Acceptance Criteria:**
		- [ ] Given a JSON value and a corresponding CLI argument value of `None`, When final configuration is produced, Then the JSON value remains unchanged.
		- [ ] Given a JSON value and a corresponding non-`None` CLI argument value, When final configuration is produced, Then the CLI value overrides the JSON value for that same field.
		- [ ] Given multiple possible builder functions in `src/common/config.py`, When they apply overrides, Then they all follow the same precedence rule and no function uses a different merge order.

- **Requirement CFG-004:** Restrict CLI Overrides to Global or Same-Module Fields
	- **Description:** CLI overrides must be scope-aware. A command may override top-level global fields and fields within its own module section, but it must not override fields in another module section even if names overlap.
	- **Acceptance Criteria:**
		- [ ] Given CLI arguments passed to `md_gen`, When final configuration is built, Then those arguments may override matching global fields and matching fields inside `md_gen` only.
		- [ ] Given CLI arguments passed to `md_gen`, When `md_mrg` contains fields with the same names, Then those `md_mrg` fields are not changed by the `md_gen` invocation.
		- [ ] Given CLI arguments passed to `md_mrg`, When final configuration is built, Then those arguments may override matching global fields and matching fields inside `md_mrg` only.

- **Requirement CFG-005:** Align All Shared Builder Functions With the Same Rules
	- **Description:** Every configuration-building function in `src/common/config.py`, not only the examples called out in the request, must follow the same structural, scope, and precedence rules.
	- **Acceptance Criteria:**
		- [ ] Given any helper or builder function in `src/common/config.py`, When it reads configuration values, Then it sources them from the correct JSON scope rather than from unrelated global or other-module sections.
		- [ ] Given any helper or builder function in `src/common/config.py`, When it overlays CLI values, Then it applies only non-`None` overrides within the allowed scope.
		- [ ] Given the full set of config builders, When compared as a group, Then none of them produce duplicated synthetic fields, cross-module leakage, or mixed-source merges that violate the shared rules.

- **Requirement CFG-006:** Strict Required-Field Validation
	- **Description:** The JSON settings file is currently strict. Required fields must be present in the JSON configuration, and config loading must fail clearly when they are missing rather than silently defaulting them.
	- **Acceptance Criteria:**
		- [ ] Given a required field missing from `settings.json`, When configuration loading runs, Then it fails with a validation error indicating the missing field.
		- [ ] Given a required field missing from JSON and a CLI argument that does not provide a non-`None` replacement, When configuration loading runs, Then it still fails instead of inventing a default.
		- [ ] Given optional fields with defined defaults in the schema, When they are omitted, Then they may still use those explicit defaults without weakening required-field validation.

## 3. Scope & Constraints
- **In-Scope:**
	- Refactor and simplify `src/common/config.py` so the shared loader mirrors the JSON schema instead of reconstructing module-specific shapes.
	- Normalize all builder/helper functions in `src/common/config.py` to use the same scope and override rules.
	- Preserve explicit JSON duplication across scopes when present in the file, while preventing programmatic duplication introduced by shared config code.
	- Enforce strict required-field validation for the current JSON settings workflow.
- **Out-of-Scope:**
	- Redesigning the JSON schema or renaming existing top-level or module section keys.
	- Changing OCR, markdown generation, merge planning, or other business logic in `md_gen` or `md_mrg` beyond how those modules read from `AppConfig`.
	- Introducing new CLI flags, new config sections, or cross-module override features.
- **Technical Constraints / Edge Cases:**
	- Missing module sections should only be tolerated if the schema defines them as optional; otherwise loading must fail clearly.
	- Nested override behavior is field-by-field for relevant non-`None` values within the allowed scope, not broad replacement of unrelated sections.
	- Explicitly duplicated keys between global and module-local JSON scopes are valid and must be preserved as separate scoped values.
	- Backward compatibility should be maintained for existing valid `settings.json` files that already follow the current schema.

**LOCKED**
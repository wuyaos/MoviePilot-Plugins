---
name: moviepilot-v2-plugin-dev
description: Build and maintain MoviePilot V2 plugins using the official V2 development contract from jxxghp/MoviePilot-Plugins/docs/V2_Plugin_Development.md. Use when creating new V2 plugins, upgrading V1 plugins to V2, wiring get_form/get_page/get_api/get_service, validating package.v2.json metadata, or troubleshooting V2 plugin registration/render issues.
---

# MoviePilot V2 Plugin Dev

## Purpose
Provide a repeatable workflow for developing and validating MoviePilot V2 plugins in this repository, aligned with the official V2 contract.

Primary reference:
- `references/V2_Plugin_Development.md`

## Use When
- User asks to create a new MoviePilot plugin for V2.
- User asks to migrate V1 plugin to V2.
- User asks why plugin is not visible / API not registered / service not loaded / page not rendered.
- User asks to standardize plugin metadata, versioning, or release checklist.

## Do Not Use When
- Request is unrelated to MoviePilot plugin development.
- Request is only generic Python refactor with no plugin contract surface.

## Workflow
1. Identify plugin mode and target:
- `vuetify` JSON mode (default) or `vue` federated mode.
- New plugin (`plugins.v2/<id>/`) or migration from `plugins/<id>/`.

2. Validate filesystem and metadata contract:
- Plugin path under `plugins.v2/<plugin_id_lower>/`.
- Class metadata fields exist and are internally consistent.
- `package.v2.json` has plugin entry.
- `plugin_version` equals metadata `version`.

3. Validate required _PluginBase methods:
- `init_plugin`
- `get_state`
- `get_api`
- `get_form`
- `get_page`
- `stop_service`

4. Validate optional surfaces only when needed:
- `get_command` for slash commands.
- `get_service` for schedulers/services.
- `get_dashboard` / `get_dashboard_meta` for dashboards.
- `get_render_mode` + `get_sidebar_nav` for Vue full page plugins.

5. Enforce V2 operational rules:
- Service `id` must be stable and unique.
- API auth (`bear` vs `apikey`) should match usage scenario.
- Avoid hardcoded plugin IDs for clone/fork friendliness.
- Prefer `_PluginBase` helpers: `update_config/get_config/get_data_path/save_data/get_data/post_message`.

6. Run minimum verification:
- `python3 -m py_compile plugins.v2/<id>/__init__.py`
- `python3 -m compileall plugins.v2/<id>`
- `git diff --check`

7. Publish checklist pass:
- Path, naming, metadata, version alignment, history updated, release flag (if required).

## Fast Commands
Use these from repo root:

```bash
# locate candidate plugin files
rg --files plugins.v2

# validate one plugin quickly
python3 -m py_compile plugins.v2/<plugin_id>/__init__.py
python3 -m compileall plugins.v2/<plugin_id>

# verify metadata entry exists
rg -n '"<PluginClassName>"\s*:\s*\{' package.v2.json
```

## Scaffolding Template
Minimal template files are provided in:
- `templates/minimal_v2_plugin/__init__.py`
- `templates/minimal_v2_plugin/requirements.txt`
- `templates/minimal_v2_plugin/package.v2.entry.json`

Copy and adapt them when creating a new plugin.

## Troubleshooting Router
When plugin behavior is inconsistent with this repo alone, inspect host/frontend integration points referenced by the official doc:
- `MoviePilot/app/core/plugin.py`
- `MoviePilot/app/api/endpoints/plugin.py`
- `MoviePilot/app/plugins/__init__.py`
- `MoviePilot-Frontend/docs/module-federation-guide.md`
- `MoviePilot-Frontend/src/utils/federationLoader.ts`

## Notes
- Keep diffs minimal and reversible.
- Prefer compatibility-preserving migrations when IDs/routes are already in use.
- If changing externally visible IDs, add a transitional compatibility path.

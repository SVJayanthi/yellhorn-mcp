# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.6.1] - 2025-07-14

### Added

- Added `revise_workplan` tool to update existing workplans based on revision instructions
  - Fetches existing workplan from GitHub issue
  - Launches background AI process to revise based on instructions
  - Updates issue with revised workplan once complete
  - Uses same codebase analysis mode and model as original workplan

## [0.6.0] - 2025-07-14

### Changed

- Major refactoring of codebase architecture (#95):
  - Split monolithic `server.py` into focused modules for better organization
  - Added comprehensive type annotations using modern Python 3.10+ syntax
  - Removed legacy Gemini 1.5 model support
  - Improved code modularity with clear interfaces between components

### Fixed

- Fixed failing tests and resolved type annotation issues (#96):
  - Corrected type hints in `cost_tracker.py` for flexible usage metadata handling
  - Improved exception handling in asynchronous flows
  - Fixed LSP context output to exclude code fences
  - Enhanced test reliability with proper GitHub CLI command mocks
  - Aligned OpenAI Deep Research tool configuration with expected values

- Fixed typing issues in cost_tracker.py using type-safe approaches (#97):
  - Introduced explicit Protocol classes for OpenAI and Gemini usage metadata
  - Refactored `format_metrics_section_raw` to use type-safe branches
  - Eliminated unchecked attribute access and `getattr` usage on untyped objects
  - Resolved all Pyright type checking errors in cost tracking module

- Fixed workplan judgment sub-issue creation and completion metrics (#104):
  - Corrected judgment process to update existing placeholder issue instead of creating duplicate
  - Removed redundant completion metrics from issue bodies (now only in comments)
  - Ensured model name is always displayed in completion comments as fallback when version is unavailable

## [0.5.2] - 2025-07-06

### Changed

- Updated default Gemini model names from preview versions to stable versions:
  - `gemini-2.5-pro-preview-05-06` → `gemini-2.5-pro`
  - `gemini-2.5-flash-preview-05-20` → `gemini-2.5-flash`
- Updated model names throughout documentation, examples, and tests
- Updated pricing configuration keys to use the new stable model names

## [0.5.1] - 2025-07-06

### Added

- Added support for OpenAI Deep Research models (`o3-deep-research` and `o4-mini-deep-research`)
- Added automatic `web_search_preview` and `code_interpreter` tools for Deep Research models
- Added metadata comments to workplan and judgment GitHub issues for improved transparency
- Added submission metadata comments showing query status, model configuration, and start time
- Added completion metadata comments with performance metrics, token usage, and estimated costs
- Added URL extraction and preservation in references sections
- Added Pydantic models for submission and completion metadata
- Added comment formatting utilities

### Changed

- Migrated all OpenAI integration from Chat Completions API to the new Responses API
- Updated dependency versions for mcp, google-genai, aiohttp, pydantic, and openai packages

## [0.5.0] - 2025-06-01

### Added

- Added Google Gemini Search Grounding as default feature for all Gemini models
- Added `YELLHORN_MCP_SEARCH` environment variable (default: "on") to control search grounding
- Added `--no-search-grounding` CLI flag to disable search grounding
- Added `disable_search_grounding` parameter to all MCP tools
- Added automatic conversion of Gemini citations to Markdown footnotes in responses
- Added URL extraction from workplan descriptions and judgements to preserve links in References section

## [0.4.0] - 2025-04-30

### Added

- Added new "lsp" codebase reasoning mode that only extracts function signatures and docstrings, resulting in lighter prompts
- Added directory tree visualization to all prompt formats for better codebase structure understanding
- Added Go language support to LSP mode with exported function and type signatures
- Added optional gopls integration for higher-fidelity Go API extraction when available
- Added jedi dependency for robust Python code analysis with graceful fallback
- Added full content extraction for files affected by diffs in judge_workplan
- Added Python class attribute extraction to LSP mode for regular classes, dataclasses, and Pydantic models
- Added Go struct field extraction to LSP mode for better API representation
- Added debug mode to create_workplan and judge_workplan tools to view the full prompt in a GitHub comment
- Added type annotations (parameter and return types) to function signatures in Python and Go LSP mode
- Added Python Enum extraction in LSP mode
- Added improved Go receiver methods extraction with support for pointers and generics
- Added comprehensive E2E tests for LSP functionality
- Updated CLI, documentation, and example client to support the new mode

### Changed

- Removed redundant `<codebase_structure>` section from prompt format to improve conciseness
- Fixed code fence handling in LSP mode to prevent nested code fences (no more ```py inside another```py)

## [0.3.3] - 2025-04-28

### Removed

- Removed git worktree generation tool and all related helpers, CLI commands, docs and tests.

## [0.3.2] - 2025-04-28

### Added

- Add 'codebase_reasoning' parameter to create_workplan tool
- Improved error handling on create_workplan

## [0.3.1] - 2025-04-26

### Changed

- Clarified usage in Cursor/VSCode in `README.md` and try and fix a bug when judging workplans from a different directory.

## [0.3.0] - 2025-04-19

### Added

- Added support for OpenAI `gpt-4o`, `gpt-4o-mini`, `o4-mini`, and `o3` models.
- Added OpenAI SDK dependency with async client support.
- Added pricing configuration for OpenAI models.
- Added conditional API key validation based on the selected model.
- Updated metrics collection to handle both Gemini and OpenAI usage metadata.
- Added comprehensive test suite raising coverage to ≥70%.
- Integrated coverage gate in CI.

### Changed

- Modified `app_lifespan` to conditionally initialize either Gemini or OpenAI clients based on the selected model.
- Updated client references in `process_workplan_async` and `process_judgement_async` functions.
- Updated documentation and help text to reflect the new model options.

## [0.2.7] - 2025-04-19

### Added

- Added completion metrics to workplans and judgements, including token usage counts and estimated cost.
- Added pricing configuration for Gemini models with tiered pricing based on token thresholds.
- Added helper functions `calculate_cost` and `format_metrics_section` for metrics generation.

## [0.2.6] - 2025-04-18

### Changed

- Default Gemini model updated to `gemini-2.5-pro-preview-05-06`.
- Renamed "review" functionality to "judge" across the application (functions, MCP tool, GitHub labels, resource types, documentation) for better semantic alignment with AI evaluation tasks. The MCP tool is now `judge_workplan`. The associated GitHub label is now `yellhorn-judgement-subissue`. The resource type is now `yellhorn_judgement_subissue`.

### Added

- Added `gemini-2.5-flash-preview-05-20` as an available model option.
- Added `CHANGELOG.md` to track changes.

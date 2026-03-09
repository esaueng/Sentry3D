# Changelog

## 0.3.10 - 2026-03-08

- Force Update now runs a dedicated immediate capture + inference cycle instead of relying on the normal coordinator refresh queue
- Manual force refresh bypasses motion gating and capture backoff deterministically

## 0.3.9 - 2026-03-08

- Tightened the default prompt so `reason` is requested as a short 5-8 word sentence
- Normalized parsed `reason` text to a compact single-sentence summary so it fits better in Home Assistant

## 0.3.8 - 2026-03-08

- Force Update button now bypasses motion gating for one refresh and sends a frame to the LLM immediately
- Forced refresh will reuse the last captured frame if a fresh capture fails
- Parser now accepts common model-response variants such as fenced JSON, lowercase status values, and numeric/boolean strings

## 0.3.7 - 2026-03-08

- Prevented coordinator update exceptions from making all coordinator-backed entities unavailable
- When an internal update error occurs, Sentry3D now keeps entities online and surfaces the failure reason in state instead

## 0.3.6 - 2026-03-08

- Short explanation strings are now normalized more aggressively so they fit better in Home Assistant history/cards
- Added `unhealthy_confidence_threshold` option with a default of `0.9`
- `binary_sensor.unhealthy` and incident triggering now require UNHEALTHY confidence to clear the configured threshold

## 0.3.5 - 2026-03-07

- Derived `short_explanation` from `reason` when the model omits it, instead of failing the whole result
- Replaced the generic `No valid result` fallback with a short summary of the actual failure reason

## 0.3.4 - 2026-03-07

- Replaced the default vision prompt with a stricter build-plate-focused inspection prompt
- Kept `short_explanation` and `focus_region` in the default schema so the HA UI and overlay preview continue to work

## 0.3.3 - 2026-03-07

- Added optional `focus_region` parsing for unhealthy model responses
- Camera now serves an annotated preview image with a highlighted concern box and confidence label when available
- Exposed `focus_region` and `overlay_available` in Home Assistant entity state attributes

## 0.3.2 - 2026-03-07

- Added editable `vision_prompt` field to the Home Assistant config flow and options flow
- Stored the configured prompt in config/options and used it for Ollama/OpenAI inference requests

## 0.3.1 - 2026-03-03

- Config/options flow now uses a base step plus provider-specific step:
  - `ollama` shows only Ollama fields
  - `openai` shows only OpenAI fields
- Provider-specific requirements now apply only to the selected provider
- Added complete local brand asset variants (`dark_*`, `@2x`) under `custom_components/sentry3d/brand`

## 0.3.0 - 2026-03-02

- Renamed integration/domain to `sentry3d`
- Moved component path to `custom_components/sentry3d`
- Updated all entities/events/service prefixes and imports to `sentry3d`
- Updated project branding to `Sentry3D` across docs, translations, and metadata

## 0.2.0 - 2026-03-01

- Added motion-gated inference so LLM calls are skipped when no motion is detected
- Added `binary_sensor.sentry3d_motion_detected`
- Added `binary_sensor.sentry3d_llm_reachable`
- Added provider support for `ollama` and `openai` APIs via config/options flow
- Added OpenAI settings (`openai_base_url`, `openai_model`, `openai_api_key`)
- Added motion settings (`motion_detection_enabled`, `motion_threshold`)
- Added `llm_reachable`, `llm_provider`, and motion fields to coordinator state/history/diagnostics

## 0.1.6 - 2026-03-01

- CI/hassfest: sorted `manifest.json` keys to required order
- Added `CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)` to satisfy hassfest config schema guidance

## 0.1.5 - 2026-03-01

- CI: ignored HACS `description/topics` checks in workflow until repo metadata is set
- CI: simplified test dependencies to avoid Home Assistant package resolver conflicts

## 0.1.4 - 2026-03-01

- Added `EMPTY` model status for clearly empty build plates
- Added `short_explanation` output field and exposed it in HA state/history
- Added `button.sentry3d_force_update` to trigger immediate refresh

## 0.1.3 - 2026-03-01

- Avoided blocking config-entry reloads/options updates by running refresh in background

## 0.1.2 - 2026-03-01

- Changed setup flow to avoid blocking config entry startup on first camera refresh
- Added cancellation handling for RTSP capture refreshes to keep integration running

## 0.1.1 - 2026-03-01

- Fixed Home Assistant startup crash caused by a `name` property conflict in the coordinator
- Added HACS-compliant brand assets and corrected `hacs.json` schema

## 0.1.0 - 2026-03-01

- Initial HACS custom integration release
- Added config flow and options flow for RTSP/Ollama settings
- Added DataUpdateCoordinator-based frame capture + inference pipeline
- Added strict JSON parsing with deterministic HEALTHY/UNHEALTHY mapping
- Added incident detection with consecutive unhealthy threshold
- Added persistent notification support with rate limiting
- Added entities: sensors, binary sensors, and last-frame camera
- Added diagnostics endpoint with credential redaction
- Added history ring buffer with Store-backed restore support
- Added stub services: `pause_print` and `cancel_print`
- Added unit tests for parsing, incident logic, and notification rate limiting

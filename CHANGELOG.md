# Changelog

## 0.3.26 - 2026-03-14

- Preserved the last valid LLM classification when motion gating skips inference instead of overwriting the visible state with `UNKNOWN`
- Added `inference_skipped` and `skip_reason` attributes so skipped cycles are explicit without destroying the last real result

## 0.3.25 - 2026-03-14

- Added runtime prompt/model-output diagnostics to the status entity so it is easier to verify whether Sentry3D is using the expected prompt and what raw model text was returned

## 0.3.24 - 2026-03-14

- Added frame hash and reuse diagnostics so Home Assistant can show whether new captures are changing or an older frame was reused
- Hardened ffmpeg capture for lower-latency RTSP frame grabs to reduce stale buffered images

## 0.3.23 - 2026-03-13

- Tuned the packaged default vision prompt to focus on only very obvious print failures, especially severe spaghetti and other clearly visible major defects

## 0.3.22 - 2026-03-13

- Replaced the packaged default vision prompt with the updated active-print FDM inspection prompt focused on visible build plate conditions

## 0.3.21 - 2026-03-13

- Changed the packaged default Ollama model to `gemma3:4b`

## 0.3.20 - 2026-03-12

- Marked the base setup/options form as a non-final step so Home Assistant renders `Next` instead of `Submit` before provider-specific settings

## 0.3.19 - 2026-03-12

- Replaced the packaged default vision prompt with the exact build-plate-focused prompt text requested for FDM print inspection

## 0.3.18 - 2026-03-12

- Added a dedicated `Reason` sensor and exposed the full reason as an attribute on `Short Explanation` so the full explanation remains readable in Home Assistant even though the frontend truncates long state strings

## 0.3.17 - 2026-03-12

- Stopped invalid `focus_region` overlay coordinates from forcing model results into `UNKNOWN`; bad overlay boxes are now ignored while keeping the health classification

## 0.3.16 - 2026-03-12

- Fixed a coordinator crash caused by a missing `STATUS_UNHEALTHY` import during result finalization, which was forcing valid updates into `UNKNOWN`

## 0.3.15 - 2026-03-12

- Made motion detection bypass explicit so disabling it no longer participates in inference gating
- Reworked the motion sensitivity setting so higher values trigger motion more easily
- Renamed the UI label from `Motion Threshold` to `Motion Sensitivity`

## 0.3.14 - 2026-03-08

- Persisted the latest captured, LLM, and overlay preview frames so the camera entity can restore a real image after reloads/restarts instead of dropping to unavailable

## 0.3.13 - 2026-03-08

- Replaced the packaged default vision prompt with the updated build-plate-focused inspection prompt
- Added a `Use Default Prompt` setup/options toggle so a saved custom prompt can be reset back to the packaged default on submit

## 0.3.12 - 2026-03-08

- Tightened `short_explanation` normalization to strip filler phrases and cap output more aggressively for Home Assistant history cards
- Updated the default prompt to request 2-4 word short explanations without filler wording

## 0.3.11 - 2026-03-08

- Fixed `LLM Reachable` semantics so it reflects whether the Ollama/OpenAI endpoint answered over HTTP
- Parse failures and other post-response model issues no longer incorrectly mark the LLM as unreachable

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

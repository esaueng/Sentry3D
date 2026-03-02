# Changelog

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

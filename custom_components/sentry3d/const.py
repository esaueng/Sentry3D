"""Constants for Sentry3D."""

from __future__ import annotations

DOMAIN = "sentry3d"

PLATFORMS = ["sensor", "binary_sensor", "camera", "button"]

CONF_NAME = "name"
CONF_RTSP_URL = "rtsp_url"
CONF_OLLAMA_BASE_URL = "ollama_base_url"
CONF_OLLAMA_MODEL = "ollama_model"
CONF_CHECK_INTERVAL_SEC = "check_interval_sec"
CONF_OLLAMA_TIMEOUT_SEC = "ollama_timeout_sec"
CONF_HISTORY_SIZE = "history_size"
CONF_UNHEALTHY_CONSECUTIVE_THRESHOLD = "unhealthy_consecutive_threshold"
CONF_UNHEALTHY_CONFIDENCE_THRESHOLD = "unhealthy_confidence_threshold"
CONF_MAX_BACKOFF_SEC = "max_backoff_sec"
CONF_CAPTURE_METHOD = "capture_method"
CONF_NOTIFY_ON_INCIDENT = "notify_on_incident"
CONF_MIN_NOTIFICATION_INTERVAL_SEC = "min_notification_interval_sec"
CONF_MOTION_DETECTION_ENABLED = "motion_detection_enabled"
CONF_MOTION_THRESHOLD = "motion_threshold"
CONF_LLM_PROVIDER = "llm_provider"
CONF_OPENAI_BASE_URL = "openai_base_url"
CONF_OPENAI_MODEL = "openai_model"
CONF_OPENAI_API_KEY = "openai_api_key"
CONF_VISION_PROMPT = "vision_prompt"
CONF_USE_DEFAULT_VISION_PROMPT = "use_default_vision_prompt"

CAPTURE_METHOD_FFMPEG = "ffmpeg"
CAPTURE_METHOD_OPENCV = "opencv"

STATUS_HEALTHY = "HEALTHY"
STATUS_UNHEALTHY = "UNHEALTHY"
STATUS_EMPTY = "EMPTY"
STATUS_UNKNOWN = "UNKNOWN"

LLM_PROVIDER_OLLAMA = "ollama"
LLM_PROVIDER_OPENAI = "openai"

EVENT_INCIDENT = "sentry3d_incident"
EVENT_CONTROL_STUB = "sentry3d_control_stub"

SERVICE_PAUSE_PRINT = "pause_print"
SERVICE_CANCEL_PRINT = "cancel_print"

DEFAULT_NAME = "Sentry3D"
DEFAULT_CHECK_INTERVAL_SEC = 2
DEFAULT_OLLAMA_TIMEOUT_SEC = 30
DEFAULT_HISTORY_SIZE = 200
DEFAULT_UNHEALTHY_CONSECUTIVE_THRESHOLD = 3
DEFAULT_UNHEALTHY_CONFIDENCE_THRESHOLD = 0.9
DEFAULT_MAX_BACKOFF_SEC = 60
DEFAULT_CAPTURE_METHOD = CAPTURE_METHOD_FFMPEG
DEFAULT_NOTIFY_ON_INCIDENT = True
DEFAULT_MIN_NOTIFICATION_INTERVAL_SEC = 300
DEFAULT_MOTION_DETECTION_ENABLED = True
DEFAULT_MOTION_THRESHOLD = 8.0
DEFAULT_LLM_PROVIDER = LLM_PROVIDER_OLLAMA
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"

MAX_HTTP_RETRIES = 3
INVALID_JSON_RETRY_COUNT = 1

STORAGE_VERSION = 1
STORAGE_KEY_PREFIX = f"{DOMAIN}_history"

SYSTEM_PROMPT = """FDM 3D Print Vision Inspector

Input: 1 RGB image of an active FDM print.

Task:
Inspect ONLY the build plate and all printed material attached to it.
Output: HEALTHY or UNHEALTHY.

Scope (Strict)

Focus only on:
* Build plate / print bed
* Printed parts, supports, skirts, brims, rafts
* Loose filament on the plate
* First layers and visible printed geometry attached to the plate

Ignore:
* Printer frame, gantry, belts, motors
* Enclosure, background, reflections
* Nozzle appearance alone
* Anything outside the build plate

Use non-plate context only if it clearly shows a failure affecting the plate print (e.g., nozzle dragging through the part).

Decision Rule
* If ANY visible defect exists on the build plate or attached print -> UNHEALTHY
* If unsure -> UNHEALTHY (lower confidence)
* Only output HEALTHY if plate contents clearly show no visible defect
* Do not guess hidden issues

Visible Defects (Trigger UNHEALTHY)
* Warping or lifting from bed
* Detached part
* Spaghetti / loose filament
* Layer shift
* Large blob or clump
* Severe under-extrusion (clear gaps)
* Severe over-extrusion (clear bulging)
* Failed/collapsed supports
* Missing print where clearly expected
* Nozzle dragging affecting plate print

Judge only what is visible.

Build Plate Priority
1. Identify the build plate
2. Evaluate everything on it
3. Prioritize:
   * Bed adhesion
   * Geometry correctness
   * Loose filament
   * Support integrity
   * Print presence

If partially visible -> judge only visible area.
If not visible enough -> UNHEALTHY (low confidence).

Confidence (0.01-0.99)
* 0.90-0.99 = clear evidence
* 0.70-0.89 = strong evidence
* 0.40-0.69 = uncertain
* 0.10-0.39 = very uncertain, leaning UNHEALTHY

Never output 0.0 or 1.0.

Signals (Set true only if clearly visible)
* bed_adhesion_ok
* spaghetti_detected
* layer_shift_detected
* detached_part_detected
* blob_detected
* supports_failed_detected
* print_missing_detected

bed_adhesion_ok = true only if visible parts are clearly well attached.
If lifting, detachment, or unclear -> false.

If unsure about any signal -> false.

Compatibility fields for Home Assistant UI:
* reason must be very short, one sentence, about 5-8 words max
* short_explanation must be 2-4 words, max about 20 characters, no filler words
* if a localized unhealthy area is visible, set focus_region to a normalized box around it; otherwise set focus_region to null

Output (JSON only, no extra text)

{
\"status\": \"HEALTHY\" | \"UNHEALTHY\",
\"confidence\": number,
\"reason\": string,
\"short_explanation\": string,
\"focus_region\": {
\"x\": number,
\"y\": number,
\"width\": number,
\"height\": number
} | null,
\"signals\": {
\"bed_adhesion_ok\": boolean,
\"spaghetti_detected\": boolean,
\"layer_shift_detected\": boolean,
\"detached_part_detected\": boolean,
\"blob_detected\": boolean,
\"supports_failed_detected\": boolean,
\"print_missing_detected\": boolean
}
}"""

USER_PROMPT = (
    "Analyze this printer image with build plate contents as the primary subject "
    "and return JSON only. When UNHEALTHY and a localized problem is visible, "
    "include focus_region."
)

DEFAULT_VISION_PROMPT = SYSTEM_PROMPT

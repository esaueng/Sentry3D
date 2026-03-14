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
DEFAULT_OLLAMA_MODEL = "gemma3:4b"
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"

MAX_HTTP_RETRIES = 3
INVALID_JSON_RETRY_COUNT = 1

STORAGE_VERSION = 1
STORAGE_KEY_PREFIX = f"{DOMAIN}_history"

SYSTEM_PROMPT = """You are a vision inspector for active FDM 3D prints.

You will receive 1 RGB image of a printer during an active print.

Your task:
Inspect only the build plate region and the printed material attached to it.
Classify the print state as HEALTHY or UNHEALTHY.

Focus only on very obvious, clearly visible problems.
Do not infer subtle, hidden, or speculative defects.

PRIMARY INSPECTION TARGET

Inspect only:
- the build plate / print bed
- printed parts attached to the bed
- skirts, brims, rafts
- supports
- loose filament on the bed
- first layers and visible printed geometry

Treat the build plate contents as the main subject.

Ignore these unless they clearly affect the plate print:
- printer frame
- gantry
- belts or motors
- enclosure
- background objects
- lighting reflections
- nozzle appearance alone
- areas outside the build plate

Use non-plate context only when it directly shows a failure affecting the printed material on the plate.

VERY OBVIOUS UNHEALTHY CONDITIONS

Only output UNHEALTHY when one of these is clearly obvious:
- spaghetti or loose filament all over the print or bed
- part fully detached from the bed
- major lifting or warping from the bed
- large filament blob or clump
- supports clearly collapsed
- printed object obviously missing from the bed
- nozzle dragging through the print and visibly disturbing it

Do not flag minor stringing, small imperfections, subtle roughness, or uncertain defects as UNHEALTHY.

HEALTHY CONDITIONS

Output HEALTHY when the build plate contents look generally normal and there is no obvious failure.
Minor cosmetic issues should still be treated as HEALTHY.

DECISION RULE

HEALTHY:
- no obvious failure is visible

UNHEALTHY:
- an obvious failure is visible

If you are unsure and the issue is not clearly obvious, prefer HEALTHY.
If visibility is too poor to judge, use UNHEALTHY with low confidence only when the image clearly prevents inspection.

SIGNAL RULES

Set signals to true only if the issue is clearly obvious.
If uncertain, set false.

Signals:
- bed_adhesion_ok
- spaghetti_detected
- layer_shift_detected
- detached_part_detected
- blob_detected
- supports_failed_detected
- print_missing_detected

Rule for bed_adhesion_ok:
true only when printed material clearly appears flat and attached to the bed.

CONFIDENCE SCALE

0.90-0.99 = very clear obvious failure or very clear healthy print
0.70-0.89 = strong visible evidence
0.40-0.69 = limited certainty
0.10-0.39 = weak evidence

Never output exactly 0.0 or 1.0.

OUTPUT FORMAT

Return valid JSON only.

{
  "status": "HEALTHY" | "UNHEALTHY",
  "confidence": number,
  "reason": "short visual explanation focused on the build plate",
  "signals": {
    "bed_adhesion_ok": boolean,
    "spaghetti_detected": boolean,
    "layer_shift_detected": boolean,
    "detached_part_detected": boolean,
    "blob_detected": boolean,
    "supports_failed_detected": boolean,
    "print_missing_detected": boolean
  }
}

The reason must reference only visible evidence on the build plate."""

USER_PROMPT = (
    "Analyze this printer image with build plate contents as the primary subject "
    "and return JSON only. When UNHEALTHY and a localized problem is visible, "
    "include focus_region."
)

DEFAULT_VISION_PROMPT = SYSTEM_PROMPT

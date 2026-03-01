"""Constants for PrinterSentry."""

from __future__ import annotations

DOMAIN = "printersentry"

PLATFORMS = ["sensor", "binary_sensor", "camera"]

CONF_NAME = "name"
CONF_RTSP_URL = "rtsp_url"
CONF_OLLAMA_BASE_URL = "ollama_base_url"
CONF_OLLAMA_MODEL = "ollama_model"
CONF_CHECK_INTERVAL_SEC = "check_interval_sec"
CONF_OLLAMA_TIMEOUT_SEC = "ollama_timeout_sec"
CONF_HISTORY_SIZE = "history_size"
CONF_UNHEALTHY_CONSECUTIVE_THRESHOLD = "unhealthy_consecutive_threshold"
CONF_MAX_BACKOFF_SEC = "max_backoff_sec"
CONF_CAPTURE_METHOD = "capture_method"
CONF_NOTIFY_ON_INCIDENT = "notify_on_incident"
CONF_MIN_NOTIFICATION_INTERVAL_SEC = "min_notification_interval_sec"

CAPTURE_METHOD_FFMPEG = "ffmpeg"
CAPTURE_METHOD_OPENCV = "opencv"

STATUS_HEALTHY = "HEALTHY"
STATUS_UNHEALTHY = "UNHEALTHY"
STATUS_UNKNOWN = "UNKNOWN"

EVENT_INCIDENT = "printersentry_incident"
EVENT_CONTROL_STUB = "printersentry_control_stub"

SERVICE_PAUSE_PRINT = "pause_print"
SERVICE_CANCEL_PRINT = "cancel_print"

DEFAULT_NAME = "PrinterSentry"
DEFAULT_CHECK_INTERVAL_SEC = 2
DEFAULT_OLLAMA_TIMEOUT_SEC = 30
DEFAULT_HISTORY_SIZE = 200
DEFAULT_UNHEALTHY_CONSECUTIVE_THRESHOLD = 3
DEFAULT_MAX_BACKOFF_SEC = 60
DEFAULT_CAPTURE_METHOD = CAPTURE_METHOD_FFMPEG
DEFAULT_NOTIFY_ON_INCIDENT = True
DEFAULT_MIN_NOTIFICATION_INTERVAL_SEC = 300

MAX_HTTP_RETRIES = 3
INVALID_JSON_RETRY_COUNT = 1

STORAGE_VERSION = 1
STORAGE_KEY_PREFIX = f"{DOMAIN}_history"

SYSTEM_PROMPT = """You are an FDM 3D print vision inspector.

Input: 1 RGB image from a live printer camera.
Output: JSON ONLY matching the schema below. No markdown. No extra text.

DECISION (strict):

* Output \"UNHEALTHY\" if ANY visible defect exists.
* If unsure, output \"UNHEALTHY\" with lower confidence.
* Output \"HEALTHY\" only when the print clearly looks normal and stable.

VISIBLE DEFECTS (UNHEALTHY if any are visible):

* bed adhesion failure: lifting/warping edges, corners up, raft/skirt peeling
* detached part: part moved, fallen, not where it should be
* spaghetti: loose strands/nesting in air or around nozzle/part
* layer shift: horizontal step/misalignment between layers
* blob/clump: large molten mass, filament ball, nozzle wrapped/engulfed
* severe under-extrusion: big gaps, missing lines, collapsed sparse walls
* severe over-extrusion: heavy bulging, smeared walls, excessive buildup
* supports failed/collapsed
* print missing: mostly empty bed where print should be
* nozzle dragging/collision: nozzle plowing into print, part wobbling from contact

Judge ONLY what is visible. Do not guess hidden issues.

CONFIDENCE (0.0–1.0, never exactly 0.0 or 1.0):

* 0.90–0.99 clear evidence
* 0.70–0.89 strong evidence
* 0.40–0.69 uncertain
* 0.10–0.39 very uncertain but leaning UNHEALTHY

SIGNALS:
Set TRUE only if clearly visible; if unsure set FALSE.
If status is HEALTHY, then all defect signals must be FALSE.
bed_adhesion_ok may be TRUE only when adhesion clearly looks solid.

REASON:
One short sentence describing the key visible evidence (no speculation).

REQUIRED JSON SCHEMA:
{
\"status\": \"HEALTHY\" | \"UNHEALTHY\",
\"confidence\": number,
\"reason\": string,
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

USER_PROMPT = "Analyze this printer camera frame and return JSON only."

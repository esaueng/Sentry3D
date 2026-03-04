# Sentry3D

Sentry3D is a Home Assistant custom integration (HACS-compatible) that monitors a 3D printer RTSP/RTSPS camera stream and classifies print health as `HEALTHY`, `UNHEALTHY`, or `EMPTY` using a remote vision LLM (Ollama or OpenAI-compatible API).

It runs inside Home Assistant (Core / Container / OS). This repository does **not** run an Ollama container.

## Features

- Samples an RTSP camera frame every configurable interval
- Motion-gates inference: only calls LLM when camera motion is detected
- Sends frame + strict safety prompt to the selected LLM provider over HTTP
- Strict JSON parsing to normalize model output into:
  - `status`: `HEALTHY` / `UNHEALTHY` / `EMPTY` / `UNKNOWN`
  - `confidence`: `0.0` to `1.0` (for model outputs)
  - `reason`: short explanation
  - `short_explanation`: compact UI-friendly phrase
  - `signals`: defect booleans
- Incident logic using consecutive unhealthy threshold
- Home Assistant entities:
  - `sensor.sentry3d_status`
  - `sensor.sentry3d_confidence`
  - `sensor.sentry3d_short_explanation`
  - `binary_sensor.sentry3d_unhealthy`
  - `binary_sensor.sentry3d_incident_active`
  - `binary_sensor.sentry3d_motion_detected`
  - `binary_sensor.sentry3d_llm_reachable`
  - `camera.sentry3d_last_frame` (shows the latest frame that was sent to the LLM)
  - `button.sentry3d_force_update`
- Event on incident trigger: `sentry3d_incident`
- Optional persistent notification on incident with rate-limiting
- Ring-buffer history (last `N`) with optional restore on restart via HA `Store`
- Diagnostics endpoint with URL credential redaction
- Stub printer-control services:
  - `sentry3d.pause_print`
  - `sentry3d.cancel_print`

## Requirements

1. Home Assistant with support for custom components.
1. RTSP camera URL from your printer/camera.
1. Reachable LLM endpoint from the Home Assistant host/network (`ollama` or `openai` provider).
1. A vision-capable model available for your selected provider.

On the **remote Ollama host**:

```bash
ollama pull <model>
```

Example model names: `llava`, `llava:13b`, or another vision-capable model available in your Ollama setup.

## Installation

### HACS (Custom Repository)

1. Open HACS in Home Assistant.
1. Add this repository as a custom repository (category: Integration).
1. Install `Sentry3D`.
1. Restart Home Assistant.

### Manual

1. Copy `custom_components/sentry3d` into your HA config directory under `custom_components/`.
1. Restart Home Assistant.

## Configuration

1. In Home Assistant UI, go to `Settings -> Devices & Services -> Add Integration`.
1. Search for `Sentry3D`.
1. Enter required values:
   - `name` (default `Sentry3D`)
   - `rtsp_url`
   - `ollama_base_url` (example: `http://ollama-host:11434`)
   - `ollama_model`
1. Optionally tune advanced fields:
   - `llm_provider` (`ollama` or `openai`)
   - `check_interval_sec` (default `2`)
   - `ollama_timeout_sec` (default `30`)
   - `openai_base_url` (default `https://api.openai.com`)
   - `openai_model` (default `gpt-4o-mini`)
   - `openai_api_key` (required only when provider is `openai`)
   - `motion_detection_enabled` (default `true`)
   - `motion_threshold` (default `8.0`)
   - `history_size` (default `200`)
   - `unhealthy_consecutive_threshold` (default `3`)
   - `max_backoff_sec` (default `60`)
   - `capture_method` (`ffmpeg` default or `opencv`)
   - `notify_on_incident` (default `true`)
   - `min_notification_interval_sec` (default `300`)

Options can be updated later via the integration options dialog. Changes are applied dynamically.

## Incident Behavior

- Incident triggers when `UNHEALTHY` appears for `M` consecutive checks.
- On trigger:
  - `incident_active` becomes `true`
  - Event `sentry3d_incident` is fired
  - Optional persistent notification is created
- Incident clears after a `HEALTHY` or `EMPTY` result.
- While incident is active, additional notifications are rate-limited by `min_notification_interval_sec`.

## Events and Services

### Event: `sentry3d_incident`

Payload includes:

- `entry_id`
- `name`
- `status`
- `confidence`
- `reason`
- `timestamp`
- `signals`

### Event: `sentry3d_control_stub`

Fired when a stub control service is called.

### Services (stub only)

- `sentry3d.pause_print`
- `sentry3d.cancel_print`

These services do not control hardware. They only log and fire a stub event.

## Example Automation Ideas

- Trigger on `binary_sensor.sentry3d_incident_active` turning on
- Trigger on event `sentry3d_incident`
- Route alert to mobile app, Pushover, Telegram, Slack, etc.

## Troubleshooting

### RTSP connectivity

- Verify RTSP/RTSPS URL format and credentials.
- Test stream from the HA host network with ffmpeg/vlc.
- If your camera prefers UDP, note this integration currently uses ffmpeg with TCP transport for reliability.

### ffmpeg not available

- Home Assistant container/OS usually includes ffmpeg support, but availability can vary.
- If ffmpeg capture fails, switch `capture_method` to `opencv` only if OpenCV is available in your HA runtime.

### Ollama timeouts or model errors

- Confirm `ollama_base_url` is reachable from Home Assistant.
- Confirm model exists on remote host (`ollama list` or `ollama pull <model>`).
- Increase `ollama_timeout_sec` for larger models.

### OpenAI/API provider issues

- Ensure `llm_provider` is `openai`.
- Confirm `openai_base_url`, `openai_model`, and `openai_api_key`.
- Check `binary_sensor.sentry3d_llm_reachable` and status attributes for reachability.

### JSON parsing failures

- Sentry3D enforces strict JSON output.
- Invalid output is retried once, then marked `UNKNOWN`.
- Check Home Assistant logs for parser details.

## Development

Run tests:

```bash
pytest -q
```

## License

MIT

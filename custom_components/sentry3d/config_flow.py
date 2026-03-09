"""Config flow for Sentry3D."""

from __future__ import annotations

import hashlib
from typing import Any
from urllib.parse import urlparse

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
)

from .const import (
    CAPTURE_METHOD_FFMPEG,
    CAPTURE_METHOD_OPENCV,
    CONF_CAPTURE_METHOD,
    CONF_CHECK_INTERVAL_SEC,
    CONF_HISTORY_SIZE,
    CONF_LLM_PROVIDER,
    CONF_MAX_BACKOFF_SEC,
    CONF_MIN_NOTIFICATION_INTERVAL_SEC,
    CONF_MOTION_DETECTION_ENABLED,
    CONF_MOTION_THRESHOLD,
    CONF_NAME,
    CONF_NOTIFY_ON_INCIDENT,
    CONF_OLLAMA_BASE_URL,
    CONF_OLLAMA_MODEL,
    CONF_OLLAMA_TIMEOUT_SEC,
    CONF_OPENAI_API_KEY,
    CONF_OPENAI_BASE_URL,
    CONF_OPENAI_MODEL,
    CONF_RTSP_URL,
    CONF_USE_DEFAULT_VISION_PROMPT,
    CONF_UNHEALTHY_CONSECUTIVE_THRESHOLD,
    CONF_UNHEALTHY_CONFIDENCE_THRESHOLD,
    CONF_VISION_PROMPT,
    DEFAULT_CAPTURE_METHOD,
    DEFAULT_CHECK_INTERVAL_SEC,
    DEFAULT_HISTORY_SIZE,
    DEFAULT_LLM_PROVIDER,
    DEFAULT_MAX_BACKOFF_SEC,
    DEFAULT_MIN_NOTIFICATION_INTERVAL_SEC,
    DEFAULT_MOTION_DETECTION_ENABLED,
    DEFAULT_MOTION_THRESHOLD,
    DEFAULT_NAME,
    DEFAULT_NOTIFY_ON_INCIDENT,
    DEFAULT_OPENAI_BASE_URL,
    DEFAULT_OPENAI_MODEL,
    DEFAULT_OLLAMA_TIMEOUT_SEC,
    DEFAULT_UNHEALTHY_CONSECUTIVE_THRESHOLD,
    DEFAULT_UNHEALTHY_CONFIDENCE_THRESHOLD,
    DEFAULT_VISION_PROMPT,
    DOMAIN,
    LLM_PROVIDER_OLLAMA,
    LLM_PROVIDER_OPENAI,
)


def _default_values() -> dict[str, Any]:
    return {
        CONF_NAME: DEFAULT_NAME,
        CONF_RTSP_URL: "rtsp://",
        CONF_LLM_PROVIDER: DEFAULT_LLM_PROVIDER,
        CONF_OLLAMA_BASE_URL: "http://ollama-host:11434",
        CONF_OLLAMA_MODEL: "llava",
        CONF_OPENAI_BASE_URL: DEFAULT_OPENAI_BASE_URL,
        CONF_OPENAI_MODEL: DEFAULT_OPENAI_MODEL,
        CONF_OPENAI_API_KEY: "",
        CONF_VISION_PROMPT: DEFAULT_VISION_PROMPT,
        CONF_CHECK_INTERVAL_SEC: DEFAULT_CHECK_INTERVAL_SEC,
        CONF_OLLAMA_TIMEOUT_SEC: DEFAULT_OLLAMA_TIMEOUT_SEC,
        CONF_HISTORY_SIZE: DEFAULT_HISTORY_SIZE,
        CONF_UNHEALTHY_CONSECUTIVE_THRESHOLD: DEFAULT_UNHEALTHY_CONSECUTIVE_THRESHOLD,
        CONF_UNHEALTHY_CONFIDENCE_THRESHOLD: DEFAULT_UNHEALTHY_CONFIDENCE_THRESHOLD,
        CONF_MAX_BACKOFF_SEC: DEFAULT_MAX_BACKOFF_SEC,
        CONF_CAPTURE_METHOD: DEFAULT_CAPTURE_METHOD,
        CONF_NOTIFY_ON_INCIDENT: DEFAULT_NOTIFY_ON_INCIDENT,
        CONF_MIN_NOTIFICATION_INTERVAL_SEC: DEFAULT_MIN_NOTIFICATION_INTERVAL_SEC,
        CONF_MOTION_DETECTION_ENABLED: DEFAULT_MOTION_DETECTION_ENABLED,
        CONF_MOTION_THRESHOLD: DEFAULT_MOTION_THRESHOLD,
    }


def _entry_defaults(entry: config_entries.ConfigEntry) -> dict[str, Any]:
    defaults = _default_values()
    for key, fallback in defaults.items():
        defaults[key] = entry.options.get(key, entry.data.get(key, fallback))
    return defaults


def _build_base_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=defaults[CONF_NAME]): TextSelector(),
            vol.Required(CONF_RTSP_URL, default=defaults[CONF_RTSP_URL]): TextSelector(),
            vol.Required(
                CONF_LLM_PROVIDER,
                default=defaults[CONF_LLM_PROVIDER],
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[LLM_PROVIDER_OLLAMA, LLM_PROVIDER_OPENAI],
                    mode=SelectSelectorMode.DROPDOWN,
                    translation_key=CONF_LLM_PROVIDER,
                )
            ),
        }
    )


def _runtime_schema_fields(defaults: dict[str, Any]) -> dict[Any, Any]:
    return {
        vol.Required(
            CONF_CHECK_INTERVAL_SEC,
            default=defaults[CONF_CHECK_INTERVAL_SEC],
        ): NumberSelector(
            NumberSelectorConfig(min=1, max=3600, mode=NumberSelectorMode.BOX)
        ),
        vol.Required(
            CONF_OLLAMA_TIMEOUT_SEC,
            default=defaults[CONF_OLLAMA_TIMEOUT_SEC],
        ): NumberSelector(
            NumberSelectorConfig(min=5, max=300, mode=NumberSelectorMode.BOX)
        ),
        vol.Required(CONF_HISTORY_SIZE, default=defaults[CONF_HISTORY_SIZE]): NumberSelector(
            NumberSelectorConfig(min=10, max=2000, mode=NumberSelectorMode.BOX)
        ),
        vol.Required(
            CONF_UNHEALTHY_CONSECUTIVE_THRESHOLD,
            default=defaults[CONF_UNHEALTHY_CONSECUTIVE_THRESHOLD],
        ): NumberSelector(
            NumberSelectorConfig(min=1, max=100, mode=NumberSelectorMode.BOX)
        ),
        vol.Required(
            CONF_UNHEALTHY_CONFIDENCE_THRESHOLD,
            default=defaults[CONF_UNHEALTHY_CONFIDENCE_THRESHOLD],
        ): NumberSelector(
            NumberSelectorConfig(
                min=0.1,
                max=0.99,
                step=0.01,
                mode=NumberSelectorMode.BOX,
            )
        ),
        vol.Required(
            CONF_MAX_BACKOFF_SEC,
            default=defaults[CONF_MAX_BACKOFF_SEC],
        ): NumberSelector(
            NumberSelectorConfig(min=1, max=600, mode=NumberSelectorMode.BOX)
        ),
        vol.Required(
            CONF_CAPTURE_METHOD,
            default=defaults[CONF_CAPTURE_METHOD],
        ): SelectSelector(
            SelectSelectorConfig(
                options=[CAPTURE_METHOD_FFMPEG, CAPTURE_METHOD_OPENCV],
                mode=SelectSelectorMode.DROPDOWN,
                translation_key=CONF_CAPTURE_METHOD,
            )
        ),
        vol.Required(
            CONF_NOTIFY_ON_INCIDENT,
            default=defaults[CONF_NOTIFY_ON_INCIDENT],
        ): BooleanSelector(),
        vol.Required(
            CONF_MIN_NOTIFICATION_INTERVAL_SEC,
            default=defaults[CONF_MIN_NOTIFICATION_INTERVAL_SEC],
        ): NumberSelector(
            NumberSelectorConfig(min=0, max=86400, mode=NumberSelectorMode.BOX)
        ),
        vol.Required(
            CONF_MOTION_DETECTION_ENABLED,
            default=defaults[CONF_MOTION_DETECTION_ENABLED],
        ): BooleanSelector(),
        vol.Required(
            CONF_MOTION_THRESHOLD,
            default=defaults[CONF_MOTION_THRESHOLD],
        ): NumberSelector(
            NumberSelectorConfig(min=0.1, max=255.0, mode=NumberSelectorMode.BOX)
        ),
    }


def _build_ollama_schema(defaults: dict[str, Any]) -> vol.Schema:
    fields: dict[Any, Any] = {
        vol.Required(
            CONF_OLLAMA_BASE_URL,
            default=defaults[CONF_OLLAMA_BASE_URL],
        ): TextSelector(),
        vol.Required(
            CONF_OLLAMA_MODEL,
            default=defaults[CONF_OLLAMA_MODEL],
        ): TextSelector(),
        vol.Required(
            CONF_VISION_PROMPT,
            default=defaults[CONF_VISION_PROMPT],
        ): TextSelector(TextSelectorConfig(multiline=True)),
        vol.Optional(
            CONF_USE_DEFAULT_VISION_PROMPT,
            default=False,
        ): BooleanSelector(),
    }
    fields.update(_runtime_schema_fields(defaults))
    return vol.Schema(fields)


def _build_openai_schema(defaults: dict[str, Any]) -> vol.Schema:
    fields: dict[Any, Any] = {
        vol.Required(
            CONF_OPENAI_BASE_URL,
            default=defaults[CONF_OPENAI_BASE_URL],
        ): TextSelector(),
        vol.Required(
            CONF_OPENAI_MODEL,
            default=defaults[CONF_OPENAI_MODEL],
        ): TextSelector(),
        vol.Required(
            CONF_OPENAI_API_KEY,
            default=defaults[CONF_OPENAI_API_KEY],
        ): TextSelector(),
        vol.Required(
            CONF_VISION_PROMPT,
            default=defaults[CONF_VISION_PROMPT],
        ): TextSelector(TextSelectorConfig(multiline=True)),
        vol.Optional(
            CONF_USE_DEFAULT_VISION_PROMPT,
            default=False,
        ): BooleanSelector(),
    }
    fields.update(_runtime_schema_fields(defaults))
    return vol.Schema(fields)


def _validate_base_input(user_input: dict[str, Any]) -> dict[str, Any]:
    data = dict(user_input)

    name = str(data[CONF_NAME]).strip() or DEFAULT_NAME
    data[CONF_NAME] = name

    rtsp_url = str(data[CONF_RTSP_URL]).strip()
    parsed_rtsp = urlparse(rtsp_url)
    if parsed_rtsp.scheme not in {"rtsp", "rtsps"} or not parsed_rtsp.netloc:
        raise ValueError("invalid_rtsp_url")
    data[CONF_RTSP_URL] = rtsp_url

    provider = str(data[CONF_LLM_PROVIDER]).strip().lower()
    if provider not in {LLM_PROVIDER_OLLAMA, LLM_PROVIDER_OPENAI}:
        raise ValueError("invalid_llm_provider")
    data[CONF_LLM_PROVIDER] = provider

    return data


def _validate_runtime_input(user_input: dict[str, Any]) -> dict[str, Any]:
    data = dict(user_input)

    numeric_fields = (
        CONF_CHECK_INTERVAL_SEC,
        CONF_OLLAMA_TIMEOUT_SEC,
        CONF_HISTORY_SIZE,
        CONF_UNHEALTHY_CONSECUTIVE_THRESHOLD,
        CONF_MAX_BACKOFF_SEC,
        CONF_MIN_NOTIFICATION_INTERVAL_SEC,
    )
    for key in numeric_fields:
        data[key] = int(data[key])

    data[CONF_MOTION_THRESHOLD] = float(data[CONF_MOTION_THRESHOLD])
    if data[CONF_MOTION_THRESHOLD] <= 0:
        raise ValueError("invalid_motion_threshold")

    data[CONF_UNHEALTHY_CONFIDENCE_THRESHOLD] = float(
        data[CONF_UNHEALTHY_CONFIDENCE_THRESHOLD]
    )
    if not 0 < data[CONF_UNHEALTHY_CONFIDENCE_THRESHOLD] < 1:
        raise ValueError("invalid_unhealthy_confidence_threshold")

    data[CONF_MOTION_DETECTION_ENABLED] = bool(data[CONF_MOTION_DETECTION_ENABLED])
    data[CONF_NOTIFY_ON_INCIDENT] = bool(data[CONF_NOTIFY_ON_INCIDENT])

    capture_method = str(data[CONF_CAPTURE_METHOD])
    if capture_method not in {CAPTURE_METHOD_FFMPEG, CAPTURE_METHOD_OPENCV}:
        raise ValueError("invalid_capture_method")
    data[CONF_CAPTURE_METHOD] = capture_method

    return data


def _validate_ollama_input(user_input: dict[str, Any]) -> dict[str, Any]:
    data = dict(user_input)
    use_default_prompt = bool(data.pop(CONF_USE_DEFAULT_VISION_PROMPT, False))

    base_url = str(data[CONF_OLLAMA_BASE_URL]).strip().rstrip("/")
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("invalid_ollama_url")
    data[CONF_OLLAMA_BASE_URL] = base_url

    model = str(data[CONF_OLLAMA_MODEL]).strip()
    if not model:
        raise ValueError("invalid_model")
    data[CONF_OLLAMA_MODEL] = model

    if use_default_prompt:
        data[CONF_VISION_PROMPT] = DEFAULT_VISION_PROMPT
    else:
        vision_prompt = str(data[CONF_VISION_PROMPT]).strip()
        if not vision_prompt:
            raise ValueError("missing_vision_prompt")
        data[CONF_VISION_PROMPT] = vision_prompt

    return data


def _validate_openai_input(user_input: dict[str, Any]) -> dict[str, Any]:
    data = dict(user_input)
    use_default_prompt = bool(data.pop(CONF_USE_DEFAULT_VISION_PROMPT, False))

    openai_base = str(data[CONF_OPENAI_BASE_URL]).strip().rstrip("/")
    parsed_openai = urlparse(openai_base)
    if parsed_openai.scheme not in {"http", "https"} or not parsed_openai.netloc:
        raise ValueError("invalid_openai_url")
    data[CONF_OPENAI_BASE_URL] = openai_base

    openai_model = str(data[CONF_OPENAI_MODEL]).strip()
    if not openai_model:
        raise ValueError("invalid_openai_model")
    data[CONF_OPENAI_MODEL] = openai_model

    openai_api_key = str(data[CONF_OPENAI_API_KEY]).strip()
    if not openai_api_key:
        raise ValueError("missing_openai_api_key")
    data[CONF_OPENAI_API_KEY] = openai_api_key

    if use_default_prompt:
        data[CONF_VISION_PROMPT] = DEFAULT_VISION_PROMPT
    else:
        vision_prompt = str(data[CONF_VISION_PROMPT]).strip()
        if not vision_prompt:
            raise ValueError("missing_vision_prompt")
        data[CONF_VISION_PROMPT] = vision_prompt

    return data


def _merge_flow_data(defaults: dict[str, Any], *sources: dict[str, Any]) -> dict[str, Any]:
    merged = dict(defaults)
    for source in sources:
        merged.update(source)
    return merged


class Sentry3DConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the config flow for Sentry3D."""

    VERSION = 1

    _defaults: dict[str, Any]
    _base_input: dict[str, Any]

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle base settings step."""
        errors: dict[str, str] = {}
        self._defaults = getattr(self, "_defaults", _default_values())

        if user_input is not None:
            try:
                self._base_input = _validate_base_input(user_input)
            except ValueError as err:
                errors["base"] = str(err)
            else:
                self._defaults.update(self._base_input)
                if self._base_input[CONF_LLM_PROVIDER] == LLM_PROVIDER_OPENAI:
                    return await self.async_step_openai()
                return await self.async_step_ollama()
            self._defaults.update(user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=_build_base_schema(self._defaults),
            errors=errors,
        )

    async def async_step_ollama(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle Ollama provider and runtime settings step."""
        if not hasattr(self, "_base_input"):
            return await self.async_step_user()

        errors: dict[str, str] = {}
        defaults = self._defaults

        if user_input is not None:
            try:
                runtime_input = _validate_runtime_input(user_input)
                provider_input = _validate_ollama_input(user_input)
            except ValueError as err:
                errors["base"] = str(err)
            else:
                validated = _merge_flow_data(
                    defaults,
                    self._base_input,
                    runtime_input,
                    provider_input,
                )
                unique_source = (
                    f"{validated[CONF_RTSP_URL]}::{validated[CONF_LLM_PROVIDER]}::{validated[CONF_OLLAMA_BASE_URL]}"
                )
                unique_id = hashlib.sha256(unique_source.encode("utf-8")).hexdigest()
                await self.async_set_unique_id(f"{DOMAIN}_{unique_id}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=validated[CONF_NAME],
                    data=validated,
                )
            defaults.update(user_input)

        return self.async_show_form(
            step_id="ollama",
            data_schema=_build_ollama_schema(defaults),
            errors=errors,
        )

    async def async_step_openai(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle OpenAI provider and runtime settings step."""
        if not hasattr(self, "_base_input"):
            return await self.async_step_user()

        errors: dict[str, str] = {}
        defaults = self._defaults

        if user_input is not None:
            try:
                runtime_input = _validate_runtime_input(user_input)
                provider_input = _validate_openai_input(user_input)
            except ValueError as err:
                errors["base"] = str(err)
            else:
                validated = _merge_flow_data(
                    defaults,
                    self._base_input,
                    runtime_input,
                    provider_input,
                )
                unique_source = (
                    f"{validated[CONF_RTSP_URL]}::{validated[CONF_LLM_PROVIDER]}::{validated[CONF_OPENAI_BASE_URL]}"
                )
                unique_id = hashlib.sha256(unique_source.encode("utf-8")).hexdigest()
                await self.async_set_unique_id(f"{DOMAIN}_{unique_id}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=validated[CONF_NAME],
                    data=validated,
                )
            defaults.update(user_input)

        return self.async_show_form(
            step_id="openai",
            data_schema=_build_openai_schema(defaults),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(entry: config_entries.ConfigEntry) -> "Sentry3DOptionsFlow":
        """Create options flow."""
        return Sentry3DOptionsFlow(entry)


class Sentry3DOptionsFlow(config_entries.OptionsFlow):
    """Handle options for Sentry3D."""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self._entry = entry
        self._defaults = _entry_defaults(entry)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage base options step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                self._base_input = _validate_base_input(user_input)
            except ValueError as err:
                errors["base"] = str(err)
            else:
                self._defaults.update(self._base_input)
                if self._base_input[CONF_LLM_PROVIDER] == LLM_PROVIDER_OPENAI:
                    return await self.async_step_openai()
                return await self.async_step_ollama()
            self._defaults.update(user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=_build_base_schema(self._defaults),
            errors=errors,
        )

    async def async_step_ollama(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage Ollama provider and runtime options."""
        if not hasattr(self, "_base_input"):
            return await self.async_step_init()

        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                runtime_input = _validate_runtime_input(user_input)
                provider_input = _validate_ollama_input(user_input)
            except ValueError as err:
                errors["base"] = str(err)
            else:
                merged = _merge_flow_data(
                    self._defaults,
                    self._base_input,
                    runtime_input,
                    provider_input,
                )
                return self.async_create_entry(title="", data=merged)
            self._defaults.update(user_input)

        return self.async_show_form(
            step_id="ollama",
            data_schema=_build_ollama_schema(self._defaults),
            errors=errors,
        )

    async def async_step_openai(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage OpenAI provider and runtime options."""
        if not hasattr(self, "_base_input"):
            return await self.async_step_init()

        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                runtime_input = _validate_runtime_input(user_input)
                provider_input = _validate_openai_input(user_input)
            except ValueError as err:
                errors["base"] = str(err)
            else:
                merged = _merge_flow_data(
                    self._defaults,
                    self._base_input,
                    runtime_input,
                    provider_input,
                )
                return self.async_create_entry(title="", data=merged)
            self._defaults.update(user_input)

        return self.async_show_form(
            step_id="openai",
            data_schema=_build_openai_schema(self._defaults),
            errors=errors,
        )

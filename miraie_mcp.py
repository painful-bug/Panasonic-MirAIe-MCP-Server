#!/usr/bin/env python3
"""
MCP Server for Panasonic MirAIe AC Control.
"""

import asyncio
import json
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from api import MirAIeAPI
from device import Device
from enums import AuthType, DisplayState, FanMode, HVACMode, PowerPlan, PresetMode, SwingMode

load_dotenv()


class ACDeviceManager:
    """Manager class for handling AC device connections and operations."""

    def __init__(self, auth_type: Optional[AuthType] = None):
        self.login_id = os.getenv("MIRAIE_LOGIN_ID")
        self.password = os.getenv("MIRAIE_PASSWORD")
        self.auth_type = self._resolve_auth_type(auth_type)
        self.api: Optional[MirAIeAPI] = None
        self.devices: List[Device] = []
        self._initialized = False

    def _resolve_auth_type(self, auth_type: Optional[AuthType]) -> AuthType:
        if auth_type is not None:
            return auth_type

        auth_type_raw = os.getenv("MIRAIE_AUTH_TYPE")
        if auth_type_raw:
            auth_type_value = auth_type_raw.strip().lower()
            auth_type_map = {
                "mobile": AuthType.MOBILE,
                "email": AuthType.EMAIL,
                "username": AuthType.USERNAME,
            }
            if auth_type_value not in auth_type_map:
                raise ValueError("Invalid MIRAIE_AUTH_TYPE. Expected one of: mobile, email, username.")
            return auth_type_map[auth_type_value]

        if self.login_id and "@" in self.login_id:
            return AuthType.EMAIL

        return AuthType.MOBILE

    async def __aenter__(self):
        self.api = MirAIeAPI(
            auth_type=self.auth_type,
            login_id=self.login_id,
            password=self.password,
        )
        await self.api.__aenter__()
        await self.api.initialize()
        self.devices = list(self.api.devices)
        self._initialized = True
        print(f"Initialized AC Manager with {len(self.devices)} devices", file=sys.stderr)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.api:
            await self.api.__aexit__(exc_type, exc_val, exc_tb)
        self._initialized = False

    def get_device_by_name(self, name: str) -> Optional[Device]:
        if not self._initialized:
            raise RuntimeError("ACDeviceManager not initialized. Use within async context.")
        for device in self.devices:
            if device.friendly_name.lower() == name.lower():
                return device
        return None

    def get_all_devices(self) -> List[Device]:
        if not self._initialized:
            raise RuntimeError("ACDeviceManager not initialized. Use within async context.")
        return self.devices.copy()


device_manager: Optional[ACDeviceManager] = None
timer_jobs: dict[str, asyncio.Task] = {}
schedule_jobs: dict[str, asyncio.Task] = {}
VALID_DAYS = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}


@asynccontextmanager
async def get_device_context():
    global device_manager
    if device_manager is None:
        device_manager = ACDeviceManager()
    async with device_manager as manager:
        yield manager


def _powerchill_enabled(device: Device) -> bool:
    return getattr(device.status, "preset_mode", PresetMode.NONE) == PresetMode.BOOST


def _active_power_plan(device: Device) -> str:
    return PowerPlan.ECO.value if getattr(device.status, "preset_mode", PresetMode.NONE) == PresetMode.ECO else PowerPlan.NORMAL.value


def _status_payload(device: Device) -> Dict[str, Any]:
    status = device.status
    return {
        "is_online": status.is_online,
        "power": status.power_mode.value,
        "mode": status.hvac_mode.value,
        "temperature": status.temperature,
        "room_temperature": status.room_temp,
        "fan_mode": status.fan_mode.value,
        "display_state": status.display_state.value,
        "preset_mode": status.preset_mode.value,
        "power_plan": _active_power_plan(device),
        "powerchill_mode": _powerchill_enabled(device),
        "vertical_swing_mode": status.vertical_swing_mode.value,
        "horizontal_swing_mode": status.horizontal_swing_mode.value,
    }


def _device_payload(device: Device) -> Dict[str, Any]:
    return {
        "name": device.friendly_name,
        "device_id": device.device_id,
        "area_name": getattr(device, "area_name", None),
        "model_name": getattr(device, "model_name", None),
        "brand": getattr(device, "brand", None),
        "firmware_version": getattr(device, "firmware_version", None),
        "status": _status_payload(device),
    }


def _get_target_devices(manager: ACDeviceManager, device_name: Optional[str]) -> List[Device]:
    if device_name:
        device = manager.get_device_by_name(device_name)
        if not device:
            raise ValueError(f"Device '{device_name}' not found")
        return [device]
    return manager.get_all_devices()


def _apply_optional_runtime_settings(device: Device, options: Dict[str, Any]) -> None:
    if options.get("mode") is not None:
        device.set_hvac_mode(HVACMode(options["mode"]))
    if options.get("temperature") is not None:
        device.set_temperature(options["temperature"])
    if options.get("fan_mode") is not None:
        device.set_fan_mode(FanMode(options["fan_mode"]))
    if options.get("power_plan") is not None:
        device.set_power_plan(PowerPlan(options["power_plan"]))
    if options.get("powerchill_mode") is not None:
        device.set_powerchill_mode(bool(options["powerchill_mode"]))


async def _run_timer_action(job_id: str, action: Dict[str, Any]) -> None:
    await asyncio.sleep(action["delay_minutes"] * 60)
    async with get_device_context() as manager:
        devices = _get_target_devices(manager, action.get("device_name"))
        for device in devices:
            if action["timer_action"] == "turn_on":
                device.turn_on()
                _apply_optional_runtime_settings(device, action)
            else:
                device.turn_off()
    timer_jobs.pop(job_id, None)


def _weekday_to_index(day: str) -> int:
    mapping = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
    return mapping[day]


def _next_schedule_run(time_hhmm: str, days_of_week: List[str]) -> datetime:
    hour_str, minute_str = time_hhmm.split(":")
    hour = int(hour_str)
    minute = int(minute_str)

    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise ValueError("time must be in HH:MM (24-hour) format")

    now = datetime.now()
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    day_indexes = sorted(_weekday_to_index(day) for day in days_of_week)

    for offset in range(8):
        test_date = candidate + timedelta(days=offset)
        if test_date.weekday() in day_indexes and test_date > now:
            return test_date

    return candidate + timedelta(days=7)


async def _run_schedule_loop(schedule_id: str, schedule: Dict[str, Any]) -> None:
    while True:
        next_run = _next_schedule_run(schedule["time"], schedule["days_of_week"])
        sleep_seconds = max((next_run - datetime.now()).total_seconds(), 0)
        await asyncio.sleep(sleep_seconds)
        async with get_device_context() as manager:
            devices = _get_target_devices(manager, schedule.get("device_name"))
            for device in devices:
                if schedule["schedule_action"] == "turn_on":
                    device.turn_on()
                    _apply_optional_runtime_settings(device, schedule)
                else:
                    device.turn_off()
        # Loop to schedule the next matching day.
        if schedule_id not in schedule_jobs:
            return


def _json_response(data: Any) -> List[TextContent]:
    return [TextContent(type="text", text=json.dumps(data, indent=2))]


SERVER_NAME = "miraie-ac"
server = Server(SERVER_NAME)


@server.list_tools()
async def list_tools() -> List[Tool]:
    return [
        Tool(name="get_devices", description="Get status of all AC devices including detailed runtime state", inputSchema={"type": "object", "properties": {}, "required": []}),
        Tool(name="turn_on_device", description="Turn on a specific AC device by name, or all devices if no name specified", inputSchema={"type": "object", "properties": {"device_name": {"type": "string"}}, "required": []}),
        Tool(name="turn_off_device", description="Turn off a specific AC device by name, or all devices if no name specified", inputSchema={"type": "object", "properties": {"device_name": {"type": "string"}}, "required": []}),
        Tool(name="set_temperature", description="Set temperature for a specific AC device by name, or all devices if no name specified", inputSchema={"type": "object", "properties": {"temperature": {"type": "integer", "minimum": 16, "maximum": 30}, "device_name": {"type": "string"}}, "required": ["temperature"]}),
        Tool(name="set_fan_mode", description="Set fan mode for a specific AC device by name, or all devices if no name specified", inputSchema={"type": "object", "properties": {"fan_mode": {"type": "string", "enum": ["auto", "low", "medium", "high", "quiet"]}, "device_name": {"type": "string"}}, "required": ["fan_mode"]}),
        Tool(name="set_mode", description="Set operating mode for a specific AC device by name, or all devices if no name specified", inputSchema={"type": "object", "properties": {"mode": {"type": "string", "enum": ["auto", "cool", "heat", "dry", "fan"]}, "device_name": {"type": "string"}}, "required": ["mode"]}),
        Tool(name="set_display_state", description="Turn AC display on/off for a specific AC device by name, or all devices if no name specified", inputSchema={"type": "object", "properties": {"display_state": {"type": "string", "enum": ["on", "off"]}, "device_name": {"type": "string"}}, "required": ["display_state"]}),
        Tool(name="get_device_info", description="Get detailed information about a specific AC device", inputSchema={"type": "object", "properties": {"device_name": {"type": "string"}}, "required": ["device_name"]}),
        Tool(name="set_preset_mode", description="Set preset mode for a specific AC device by name, or all devices if no name specified", inputSchema={"type": "object", "properties": {"preset_mode": {"type": "string", "enum": ["none", "eco", "boost"]}, "device_name": {"type": "string"}}, "required": ["preset_mode"]}),
        Tool(name="set_v_swing", description="Set vertical swing mode for a specific AC device by name, or all devices if no name specified", inputSchema={"type": "object", "properties": {"vertical_swing_mode": {"type": "string", "enum": ["0", "1", "2", "3", "4", "5"]}, "device_name": {"type": "string"}}, "required": ["vertical_swing_mode"]}),
        Tool(name="set_h_swing", description="Set horizontal swing mode for a specific AC device by name, or all devices if no name specified", inputSchema={"type": "object", "properties": {"horizontal_swing_mode": {"type": "string", "enum": ["0", "1", "2", "3", "4", "5"]}, "device_name": {"type": "string"}}, "required": ["horizontal_swing_mode"]}),
        Tool(name="set_power_plan", description="Set active AC power plan to eco or normal for one device or all devices", inputSchema={"type": "object", "properties": {"power_plan": {"type": "string", "enum": ["eco", "normal"]}, "device_name": {"type": "string"}}, "required": ["power_plan"]}),
        Tool(name="toggle_powerchill_mode", description="Toggle powerchill mode for one device or all devices", inputSchema={"type": "object", "properties": {"device_name": {"type": "string"}}, "required": []}),
        Tool(
            name="set_timer",
            description="Set a one-time AC timer (delayed turn on/off), with optional runtime settings for turn_on",
            inputSchema={
                "type": "object",
                "properties": {
                    "timer_id": {"type": "string"},
                    "timer_action": {"type": "string", "enum": ["turn_on", "turn_off"]},
                    "delay_minutes": {"type": "integer", "minimum": 1, "maximum": 1440},
                    "device_name": {"type": "string"},
                    "mode": {"type": "string", "enum": ["auto", "cool", "heat", "dry", "fan"]},
                    "temperature": {"type": "integer", "minimum": 16, "maximum": 30},
                    "fan_mode": {"type": "string", "enum": ["auto", "low", "medium", "high", "quiet"]},
                    "power_plan": {"type": "string", "enum": ["eco", "normal"]},
                    "powerchill_mode": {"type": "boolean"},
                },
                "required": ["timer_action", "delay_minutes"],
            },
        ),
        Tool(
            name="set_schedule",
            description="Set or update a recurring AC schedule by day and time",
            inputSchema={
                "type": "object",
                "properties": {
                    "schedule_id": {"type": "string"},
                    "schedule_action": {"type": "string", "enum": ["turn_on", "turn_off"]},
                    "time": {"type": "string", "description": "24-hour HH:MM"},
                    "days_of_week": {
                        "type": "array",
                        "items": {"type": "string", "enum": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]},
                        "minItems": 1,
                    },
                    "enabled": {"type": "boolean"},
                    "device_name": {"type": "string"},
                    "mode": {"type": "string", "enum": ["auto", "cool", "heat", "dry", "fan"]},
                    "temperature": {"type": "integer", "minimum": 16, "maximum": 30},
                    "fan_mode": {"type": "string", "enum": ["auto", "low", "medium", "high", "quiet"]},
                    "power_plan": {"type": "string", "enum": ["eco", "normal"]},
                    "powerchill_mode": {"type": "boolean"},
                },
                "required": ["schedule_id", "schedule_action", "time", "days_of_week"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    try:
        if name in {"get_devices", "get_device_status"}:
            async with get_device_context() as manager:
                devices = manager.get_all_devices()
                result = {"device_count": len(devices), "devices": [_device_payload(device) for device in devices]}
                return _json_response(result)

        if name == "turn_on_device":
            async with get_device_context() as manager:
                devices = _get_target_devices(manager, arguments.get("device_name"))
                for device in devices:
                    device.turn_on()
                return [TextContent(type="text", text=f"Turned on {len(devices)} device(s)")]

        if name == "turn_off_device":
            async with get_device_context() as manager:
                devices = _get_target_devices(manager, arguments.get("device_name"))
                for device in devices:
                    device.turn_off()
                return [TextContent(type="text", text=f"Turned off {len(devices)} device(s)")]

        if name == "set_temperature":
            temperature = arguments["temperature"]
            async with get_device_context() as manager:
                devices = _get_target_devices(manager, arguments.get("device_name"))
                for device in devices:
                    device.set_temperature(temperature)
                return [TextContent(type="text", text=f"Set temperature to {temperature}°C for {len(devices)} device(s)")]

        if name == "set_fan_mode":
            fan_mode = FanMode(arguments["fan_mode"])
            async with get_device_context() as manager:
                devices = _get_target_devices(manager, arguments.get("device_name"))
                for device in devices:
                    device.set_fan_mode(fan_mode)
                return [TextContent(type="text", text=f"Set fan mode to {fan_mode.value} for {len(devices)} device(s)")]

        if name == "set_mode":
            mode = HVACMode(arguments["mode"])
            async with get_device_context() as manager:
                devices = _get_target_devices(manager, arguments.get("device_name"))
                for device in devices:
                    device.set_hvac_mode(mode)
                return [TextContent(type="text", text=f"Set mode to {mode.value} for {len(devices)} device(s)")]

        if name == "set_display_state":
            display_state = DisplayState(arguments["display_state"])
            async with get_device_context() as manager:
                devices = _get_target_devices(manager, arguments.get("device_name"))
                for device in devices:
                    device.set_display_state(display_state)
                return [TextContent(type="text", text=f"Set display state to {display_state.value} for {len(devices)} device(s)")]

        if name == "set_preset_mode":
            preset_mode = PresetMode(arguments["preset_mode"])
            async with get_device_context() as manager:
                devices = _get_target_devices(manager, arguments.get("device_name"))
                for device in devices:
                    device.set_preset_mode(preset_mode)
                return [TextContent(type="text", text=f"Set preset mode to {preset_mode.value} for {len(devices)} device(s)")]

        if name in {"set_v_swing", "set_vertical_swing_mode"}:
            mode = SwingMode(int(arguments["vertical_swing_mode"]))
            async with get_device_context() as manager:
                devices = _get_target_devices(manager, arguments.get("device_name"))
                for device in devices:
                    device.set_vertical_swing_mode(mode)
                return [TextContent(type="text", text=f"Set vertical swing mode to {mode.value} for {len(devices)} device(s)")]

        if name in {"set_h_swing", "set_horizontal_swing_mode"}:
            mode = SwingMode(int(arguments["horizontal_swing_mode"]))
            async with get_device_context() as manager:
                devices = _get_target_devices(manager, arguments.get("device_name"))
                for device in devices:
                    device.set_horizontal_swing_mode(mode)
                return [TextContent(type="text", text=f"Set horizontal swing mode to {mode.value} for {len(devices)} device(s)")]

        if name == "set_power_plan":
            power_plan = PowerPlan(arguments["power_plan"])
            async with get_device_context() as manager:
                devices = _get_target_devices(manager, arguments.get("device_name"))
                for device in devices:
                    device.set_power_plan(power_plan)
                return [TextContent(type="text", text=f"Set power plan to {power_plan.value} for {len(devices)} device(s)")]

        if name == "toggle_powerchill_mode":
            async with get_device_context() as manager:
                devices = _get_target_devices(manager, arguments.get("device_name"))
                result = []
                for device in devices:
                    enabled = not _powerchill_enabled(device)
                    device.set_powerchill_mode(enabled)
                    result.append({"device_name": device.friendly_name, "powerchill_mode": enabled})
                return _json_response({"updated": result})

        if name == "set_timer":
            timer_id = arguments.get("timer_id") or f"timer-{int(asyncio.get_running_loop().time())}"
            timer_action = arguments["timer_action"]
            delay_minutes = arguments["delay_minutes"]
            action = {
                "timer_action": timer_action,
                "delay_minutes": delay_minutes,
                "device_name": arguments.get("device_name"),
                "mode": arguments.get("mode"),
                "temperature": arguments.get("temperature"),
                "fan_mode": arguments.get("fan_mode"),
                "power_plan": arguments.get("power_plan"),
                "powerchill_mode": arguments.get("powerchill_mode"),
            }
            existing = timer_jobs.get(timer_id)
            if existing:
                existing.cancel()
            timer_jobs[timer_id] = asyncio.create_task(_run_timer_action(timer_id, action))
            return _json_response({"timer_id": timer_id, "status": "scheduled", "action": action})

        if name == "set_schedule":
            schedule_id = arguments["schedule_id"]
            enabled = arguments.get("enabled", True)

            existing = schedule_jobs.get(schedule_id)
            if existing:
                existing.cancel()
                schedule_jobs.pop(schedule_id, None)

            if not enabled:
                return _json_response({"schedule_id": schedule_id, "status": "disabled"})

            days_of_week = [day.lower() for day in arguments["days_of_week"]]
            invalid_days = [day for day in days_of_week if day not in VALID_DAYS]
            if invalid_days:
                raise ValueError(f"Invalid days_of_week values: {', '.join(invalid_days)}")

            schedule = {
                "schedule_action": arguments["schedule_action"],
                "time": arguments["time"],
                "days_of_week": days_of_week,
                "device_name": arguments.get("device_name"),
                "mode": arguments.get("mode"),
                "temperature": arguments.get("temperature"),
                "fan_mode": arguments.get("fan_mode"),
                "power_plan": arguments.get("power_plan"),
                "powerchill_mode": arguments.get("powerchill_mode"),
            }

            # Validate schedule time before creating the recurring task.
            _next_schedule_run(schedule["time"], schedule["days_of_week"])
            schedule_jobs[schedule_id] = asyncio.create_task(_run_schedule_loop(schedule_id, schedule))

            return _json_response({"schedule_id": schedule_id, "status": "enabled", "schedule": schedule})

        if name in {"get_device_info", "get_device_details"}:
            async with get_device_context() as manager:
                device = manager.get_device_by_name(arguments["device_name"])
                if not device:
                    raise ValueError(f"Device '{arguments['device_name']}' not found")
                details = {
                    "name": device.friendly_name,
                    "device_id": getattr(device, "device_id", "unknown"),
                    "model_name": getattr(device, "model_name", "unknown"),
                    "brand": getattr(device, "brand", "unknown"),
                    "category": getattr(device, "category", "unknown"),
                    "firmware_version": getattr(device, "firmware_version", "unknown"),
                    "mac_address": getattr(device, "mac_address", "unknown"),
                    "area_name": getattr(device, "area_name", "unknown"),
                    "status": _status_payload(device),
                }
                return _json_response(details)

        return [TextContent(type="text", text=f"Error: Unknown tool '{name}'")]

    except Exception as e:
        error_msg = f"Error executing {name}: {str(e)}"
        print(error_msg, file=sys.stderr)
        return [TextContent(type="text", text=error_msg)]


async def main():
    print("Starting Panasonic MirAIe AC MCP Server...", file=sys.stderr)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down server...", file=sys.stderr)
    except Exception as e:
        print(f"Server error: {e}", file=sys.stderr)
        sys.exit(1)

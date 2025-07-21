#!/usr/bin/env python3
"""
MCP Server for Panasonic MirAIe AC Control
Provides tools to control AC devices through the Model Context Protocol
"""

import asyncio
import json
import sys
import os
from typing import Any, Dict, List, Optional, Union
from contextlib import asynccontextmanager

# MCP imports
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from enums import *
# Your existing imports (adjust paths as needed)
from api import MirAIeAPI
from enums import AuthType
from device import Device
from dotenv import load_dotenv

load_dotenv()

# Your existing ACDeviceManager class
class ACDeviceManager:
    """Manager class for handling AC device connections and operations."""
    
    def __init__(self, auth_type: AuthType = AuthType.MOBILE):
        self.login_id = os.getenv("MIRAIE_LOGIN_ID")
        self.password = os.getenv("MIRAIE_PASSWORD")
        self.auth_type = auth_type
        self.api: Optional[MirAIeAPI] = None
        self.devices: List[Device] = []
        self._initialized = False
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.api = MirAIeAPI(
            auth_type=self.auth_type,
            login_id=self.login_id,
            password=self.password
        )
        await self.api.__aenter__() 
        await self.api.initialize()
        self.devices = list(self.api.devices)
        self._initialized = True
        print(f"Initialized AC Manager with {len(self.devices)} devices", file=sys.stderr)
        for device in self.devices:
            print(f"  - {device.friendly_name}", file=sys.stderr)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.api:
            await self.api.__aexit__(exc_type, exc_val, exc_tb)
        self._initialized = False
    
    def get_device_by_name(self, name: str) -> Optional[Device]:
        """Get device by friendly name."""
        if not self._initialized:
            raise RuntimeError("ACDeviceManager not initialized. Use within async context.")
        
        for device in self.devices:
            if device.friendly_name.lower() == name.lower():
                return device
        return None
    
    def get_all_devices(self) -> List[Device]:
        """Get all available devices."""
        if not self._initialized:
            raise RuntimeError("ACDeviceManager not initialized. Use within async context.")
        return self.devices.copy()


# Global device manager instance
device_manager: Optional[ACDeviceManager] = None

@asynccontextmanager
async def get_device_context():
    """Context manager to get initialized device manager."""
    global device_manager
    
    if device_manager is None:
        device_manager = ACDeviceManager()
    
    async with device_manager as manager:
        yield manager


# Create MCP server
server = Server("panasonic-miraie-ac")


# Define MCP tools
@server.list_tools()
async def list_tools() -> List[Tool]:
    """List all available AC control tools."""
    return [
        Tool(
            name="get_device_status",
            description="Get status of all AC devices including their names and IDs",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="turn_on_device",
            description="Turn on a specific AC device by name, or all devices if no name specified",
            inputSchema={
                "type": "object",
                "properties": {
                    "device_name": {
                        "type": "string",
                        "description": "Name of the device to turn on (optional - if not provided, turns on all devices)"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="turn_off_device", 
            description="Turn off a specific AC device by name, or all devices if no name specified",
            inputSchema={
                "type": "object",
                "properties": {
                    "device_name": {
                        "type": "string",
                        "description": "Name of the device to turn off (optional - if not provided, turns off all devices)"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="set_temperature",
            description="Set temperature for a specific AC device by name, or all devices if no name specified",
            inputSchema={
                "type": "object",
                "properties": {
                    "temperature": {
                        "type": "integer",
                        "description": "Temperature to set in Celsius (typically 16-30)",
                        "minimum": 16,
                        "maximum": 30
                    },
                    "device_name": {
                        "type": "string",
                        "description": "Name of the device to set temperature for (optional - if not provided, sets temperature for all devices)"
                    }
                },
                "required": ["temperature"]
            }
        ),
        Tool(
            name="set_fan_mode",
            description="Set fan mode for a specific AC device by name, or all devices if no name specified",
            inputSchema={
                "type": "object",
                "properties": {
                    "fan_mode": {
                        "type": "string",
                        "description": "Fan speed setting (auto, low, medium, high)",
                        "enum": ["auto", "low", "medium", "high"]
                    },
                    "device_name": {
                        "type": "string",
                        "description": "Name of the device to set fan speed for (optional - if not provided, sets fan speed for all devices)"
                    }
                },
                "required": ["fan_mode"]
            }
        ),
        Tool(
            name="set_mode",
            description="Set operating mode for a specific AC device by name, or all devices if no name specified",
            inputSchema={
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "string",
                        "description": "AC operating mode",
                        "enum": ["auto", "cool", "heat", "dry", "fan"]
                    },
                    "device_name": {
                        "type": "string",
                        "description": "Name of the device to set mode for (optional - if not provided, sets mode for all devices)"
                    }
                },
                "required": ["mode"]
            }
        ),
        Tool(
            name="get_device_details",
            description="Get detailed information about a specific AC device",
            inputSchema={
                "type": "object",
                "properties": {
                    "device_name": {
                        "type": "string",
                        "description": "Name of the device to get details for"
                    }
                },
                "required": ["device_name"]
            }
        ),
        Tool(
            name="set_preset_mode",
            description="Set preset mode for a specific AC device by name, or all devices if no name specified",
            inputSchema={
                "type": "object",
                "properties": {
                    "preset_mode": {
                        "type": "string",
                        "description": "Preset mode to set (none, eco, boost)",
                        "enum": ["none", "eco", "boost"]
                    },
                    "device_name": {
                        "type": "string",
                        "description": "Name of the device to set preset mode for (optional - if not provided, sets preset mode for all devices)"
                    }
                },
                "required": ["preset_mode"]
            }
        ),
        Tool(
            name="set_vertical_swing_mode",
            description="Set vertical swing mode for a specific AC device by name, or all devices if no name specified",
            inputSchema={
                "type": "object",
                "properties": {
                    "vertical_swing_mode": {
                        "type": "string",
                        "description": "Vertical swing mode to set (auto, 1, 2, 3, 4, 5)",
                        "enum": ["0", "1", "2", "3", "4", "5"]
                    },
                    "device_name": {
                        "type": "string",
                        "description": "Name of the device to set vertical swing mode for (optional - if not provided, sets vertical swing mode for all devices)"
                    }
                },
                "required": ["vertical_swing_mode"]
            }
        ),
        Tool(
            name="set_horizontal_swing_mode",
            description="Set horizontal swing mode for a specific AC device by name, or all devices if no name specified",
            inputSchema={
                "type": "object",
                "properties": {
                    "horizontal_swing_mode": {
                        "type": "string",
                        "description": "Horizontal swing mode to set (auto, 1, 2, 3, 4, 5)",
                        "enum": ["0", "1", "2", "3", "4", "5"]
                    },
                    "device_name": {
                        "type": "string",
                        "description": "Name of the device to set horizontal swing mode for (optional - if not provided, sets horizontal swing mode for all devices)"
                    }
                },
                "required": ["horizontal_swing_mode"]
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle tool calls."""
    try:
        if name == "get_device_status":
            async with get_device_context() as manager:
                devices = manager.get_all_devices()
                status_list = []
                for device in devices:
                    status_list.append({
                        "name": device.friendly_name,
                        "device_id": getattr(device, 'device_id', 'unknown'),
                        "model": getattr(device, 'model', 'unknown')
                    })
                result = {
                    "device_count": len(devices),
                    "devices": status_list
                }
                return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "turn_on_device":
            device_name = arguments.get("device_name")
            async with get_device_context() as manager:
                if device_name:
                    device = manager.get_device_by_name(device_name)
                    if not device:
                        return [TextContent(type="text", text=f"Error: Device '{device_name}' not found")]
                    device.turn_on()
                    result = f"Turned on {device.friendly_name}"
                else:
                    devices = manager.get_all_devices()
                    for device in devices:
                        device.turn_on()
                    result = f"Turned on {len(devices)} devices"
                return [TextContent(type="text", text=result)]
        
        elif name == "turn_off_device":
            device_name = arguments.get("device_name")
            async with get_device_context() as manager:
                if device_name:
                    device = manager.get_device_by_name(device_name)
                    if not device:
                        return [TextContent(type="text", text=f"Error: Device '{device_name}' not found")]
                    device.turn_off()
                    result = f"Turned off {device.friendly_name}"
                else:
                    devices = manager.get_all_devices()
                    for device in devices:
                        device.turn_off()
                    result = f"Turned off {len(devices)} devices"
                return [TextContent(type="text", text=result)]
        
        elif name == "set_temperature":
            temperature = arguments["temperature"]
            device_name = arguments.get("device_name")
            async with get_device_context() as manager:
                if device_name:
                    device = manager.get_device_by_name(device_name)
                    if not device:
                        return [TextContent(type="text", text=f"Error: Device '{device_name}' not found")]
                    device.set_temperature(temperature)
                    result = f"Set {device.friendly_name} to {temperature}°C"
                else:
                    devices = manager.get_all_devices()
                    for device in devices:
                        device.set_temperature(temperature)
                    result = f"Set temperature to {temperature}°C for {len(devices)} devices"
                return [TextContent(type="text", text=result)]
        
        elif name == "set_fan_mode":
            try:
                fan_mode = arguments["fan_mode"]
                print(f"DEBUG: Received fan_mode: {fan_mode} (type: {type(fan_mode)})", file=sys.stderr)
                
                # Convert string to FanMode enum object (not .name)
                fan_mode_enum = FanMode(fan_mode)
                print(f"DEBUG: Converted to enum: {fan_mode_enum} (type: {type(fan_mode_enum)})", file=sys.stderr)
                
                device_name = arguments.get("device_name")
                print(f"DEBUG: Device name: {device_name}", file=sys.stderr)
                
                async with get_device_context() as manager:
                    if device_name:
                        device = manager.get_device_by_name(device_name)
                        if not device:
                            return [TextContent(type="text", text=f"Error: Device '{device_name}' not found")]
                        print(f"DEBUG: Found device: {device.friendly_name}", file=sys.stderr)
                        print(f"DEBUG: Device control topic: {device.control_topic}", file=sys.stderr)
                        
                        # Pass the FanMode enum object to the device
                        print(f"DEBUG: Calling device.set_fan_mode with {fan_mode_enum}", file=sys.stderr)
                        device.set_fan_mode(fan_mode_enum)
                        result = f"Set {device.friendly_name} fan mode to {fan_mode_enum.value}"
                    else:
                        devices = manager.get_all_devices()
                        results = []
                        for device in devices:
                            print(f"DEBUG: Setting fan mode for device: {device.friendly_name}", file=sys.stderr)
                            device.set_fan_mode(fan_mode_enum)
                            results.append(f"Set {device.friendly_name} fan mode to {fan_mode_enum.value}")
                        result = "\n".join(results)
                    return [TextContent(type="text", text=result)]
            except Exception as e:
                error_details = f"Error in set_fan_mode: {str(e)} (type: {type(e).__name__})"
                print(error_details, file=sys.stderr)
                import traceback
                traceback.print_exc(file=sys.stderr)
                return [TextContent(type="text", text=error_details)]
        
        elif name == "set_mode":
            mode = arguments["mode"]
            mode_enum = HVACMode(mode)
            print("Mode: ", mode)
            device_name = arguments.get("device_name")
            async with get_device_context() as manager:
                if device_name:
                    device = manager.get_device_by_name(device_name)
                    if not device:
                        return [TextContent(type="text", text=f"Error: Device '{device_name}' not found")]
                    device.set_hvac_mode(mode_enum)
                    result = f"Set {device.friendly_name} mode to {mode_enum.value}"
                else:
                    devices = manager.get_all_devices()
                    results = []
                    for device in devices:
                        device.set_hvac_mode(mode_enum)
                        results.append(f"Set {device.friendly_name} mode to {mode_enum.value}")
                    result = "\n".join(results)
                return [TextContent(type="text", text=result)]
        
        elif name == "set_preset_mode":
            preset_mode = arguments["preset_mode"]
            preset_mode_enum = PresetMode(preset_mode)
            device_name = arguments.get("device_name")
            async with get_device_context() as manager:
                if device_name:
                    device = manager.get_device_by_name(device_name)
                    if not device:
                        return [TextContent(type="text", text=f"Error: Device '{device_name}' not found")]
                    # Assuming your device has a set_preset_mode method
                    if hasattr(device, 'set_preset_mode'):
                        device.set_preset_mode(preset_mode_enum)
                        result = f"Set {device.friendly_name} preset mode to {preset_mode_enum.value}"
                    else:
                        result = f"Preset mode control not available for {device.friendly_name}"
                else:
                    devices = manager.get_all_devices()
                    results = []
                    for device in devices:
                        if hasattr(device, 'set_preset_mode'):
                            device.set_preset_mode(preset_mode_enum)
                            results.append(f"Set {device.friendly_name} preset mode to {preset_mode_enum.value}")
                        else:
                            results.append(f"Preset mode control not available for {device.friendly_name}")
                    result = "\n".join(results)
                return [TextContent(type="text", text=result)]
        
        elif name == "set_vertical_swing_mode":
            vertical_swing_mode = arguments["vertical_swing_mode"]
            vertical_swing_mode_enum = SwingMode(vertical_swing_mode)
            device_name = arguments.get("device_name")
            async with get_device_context() as manager:
                if device_name:
                    device = manager.get_device_by_name(device_name)
                    if not device:
                        return [TextContent(type="text", text=f"Error: Device '{device_name}' not found")]
                    # Assuming your device has a set_vertical_swing_mode method
                    if hasattr(device, 'set_vertical_swing_mode'):
                        device.set_vertical_swing_mode(int(vertical_swing_mode_enum))
                        result = f"Set {device.friendly_name} vertical swing mode to {vertical_swing_mode_enum.value}"
                    else:
                        result = f"Vertical swing mode control not available for {device.friendly_name}"
                else:
                    devices = manager.get_all_devices()
                    results = []
                    for device in devices:
                        if hasattr(device, 'set_vertical_swing_mode'):
                            device.set_vertical_swing_mode(int(vertical_swing_mode_enum))
                            results.append(f"Set {device.friendly_name} vertical swing mode to {vertical_swing_mode_enum.value}")
                        else:
                            results.append(f"Vertical swing mode control not available for {device.friendly_name}")
                    result = "\n".join(results)
                return [TextContent(type="text", text=result)]
        
        elif name == "set_horizontal_swing_mode":
            horizontal_swing_mode = arguments["horizontal_swing_mode"]
            horizontal_swing_mode_enum = SwingMode(horizontal_swing_mode)
            device_name = arguments.get("device_name")
            async with get_device_context() as manager:
                if device_name:
                    device = manager.get_device_by_name(device_name)
                    if not device:
                        return [TextContent(type="text", text=f"Error: Device '{device_name}' not found")]
                    # Assuming your device has a set_horizontal_swing_mode method
                    if hasattr(device, 'set_horizontal_swing_mode'):
                        device.set_horizontal_swing_mode(horizontal_swing_mode_enum)
                        result = f"Set {device.friendly_name} horizontal swing mode to {horizontal_swing_mode_enum.value}"
                    else:
                        result = f"Horizontal swing mode control not available for {device.friendly_name}"
                else:
                    devices = manager.get_all_devices()
                    results = []
                    for device in devices:
                        if hasattr(device, 'set_horizontal_swing_mode'):
                            device.set_horizontal_swing_mode(horizontal_swing_mode_enum)
                            results.append(f"Set {device.friendly_name} horizontal swing mode to {horizontal_swing_mode_enum.value}")
                        else:
                            results.append(f"Horizontal swing mode control not available for {device.friendly_name}")
                    result = "\n".join(results)
                return [TextContent(type="text", text=result)]
        
        
        elif name == "get_device_details":
            device_name = arguments["device_name"]
            async with get_device_context() as manager:
                device = manager.get_device_by_name(device_name)
                if not device:
                    return [TextContent(type="text", text=f"Error: Device '{device_name}' not found")]
                
                # Get all available attributes from the device
                details = {
                    "name": device.friendly_name,
                    "device_id": getattr(device, 'device_id', 'unknown'),
                    "model": getattr(device, 'model', 'unknown'),
                    "available_methods": [method for method in dir(device) if not method.startswith('_') and callable(getattr(device, method))]
                }
                
                # Try to get current state if available
                if hasattr(device, 'get_state'):
                    try:
                        details["current_state"] = device.get_state()
                    except:
                        details["current_state"] = "unavailable"
                
                return [TextContent(type="text", text=json.dumps(details, indent=2))]
        
        else:
            return [TextContent(type="text", text=f"Error: Unknown tool '{name}'")]
            
    except Exception as e:
        error_msg = f"Error executing {name}: {str(e)}"
        print(error_msg, file=sys.stderr)
        return [TextContent(type="text", text=error_msg)]


async def main():
    """Main entry point for the MCP server."""
    print("Starting Panasonic MirAIe AC MCP Server...", file=sys.stderr)
    
    # Validate configuration
    # if LOGIN_ID == "your_phone_number_here" or PASSWORD == "your_password_here":
    #     print("ERROR: Please update LOGIN_ID and PASSWORD in the script with your credentials", file=sys.stderr)
    #     sys.exit(1)
    
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
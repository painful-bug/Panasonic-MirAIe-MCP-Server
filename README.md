# Panasonic MirAIe AC MCP Server

A Model Context Protocol (MCP) server that enables control of Panasonic MirAIe air conditioning devices through conversational AI. This server provides comprehensive AC control capabilities including temperature setting, mode changes, fan control, and device management.

## Features

### Device Control
- **Power Management**: Turn devices on/off individually or all at once
- **Temperature Control**: Set temperature (16-30°C) for specific devices or all devices
- **Mode Control**: Switch between operating modes (auto, cool, heat, dry, fan)
- **Fan Control**: Adjust fan speed (auto, low, medium, high)
- **Preset Modes**: Set energy-saving presets (none, eco, boost)

### Advanced Controls
- **Swing Control**: 
  - Vertical swing modes (positions 0-5)
  - Horizontal swing modes (positions 0-5)
- **Device Management**: 
  - List all connected devices
  - Get detailed device information
  - Individual device targeting by name

### Supported Operations
- `get_device_status` - List all available AC devices
- `turn_on_device` - Power on specific device or all devices
- `turn_off_device` - Power off specific device or all devices
- `set_temperature` - Set temperature for specific device or all devices
- `set_fan_mode` - Control fan speed settings
- `set_mode` - Change AC operating mode
- `set_preset_mode` - Apply energy presets
- `set_vertical_swing_mode` - Control vertical air direction
- `set_horizontal_swing_mode` - Control horizontal air direction
- `get_device_details` - Get comprehensive device information

## Requirements

### Python Dependencies
```
mcp>=0.1.0
python-dotenv
asyncio
fastapi (optional, for REST API)
```

### Environment Setup
The server requires Panasonic MirAIe account credentials configured as environment variables:

```bash
MIRAIE_LOGIN_ID=your_phone_number_or_email
MIRAIE_PASSWORD=your_password
```

## Installation & Setup

### 1. Clone and Install Dependencies
```bash
git clone https://github.com/painful-bug/Panasonic-MirAIe-MCP-Server.git
# OR
git clone https://github.com/Saboten758/Panasonic-MirAIe-MCP-Server.git
#THEN
cd miraie_mcp
pip install mcp python-dotenv
```

### 2. Configure Environment
Create a `.env` file in the project root:
```env
MIRAIE_LOGIN_ID=your_phone_number_or_email
MIRAIE_PASSWORD=your_password
```
A sample env is also provided as .env.sample

### 3. MCP Configuration
Add to your MCP client configuration (e.g., Claude Desktop config):

```json
{
  "mcpServers": {
    "panasonic-miraie-ac": {
      "command": "python",
      "args": ["/path/to/miraie_mcp/miraie_mcp.py"],
      "env": {
        "MIRAIE_LOGIN_ID": "your_credentials",
        "MIRAIE_PASSWORD": "your_password"
      }
    }
  }
}
```

### 4. Run the Server
```bash
python miraie_mcp.py
```

## Usage Examples

### Basic Device Control
```
# Turn on all AC units
"Turn on all AC devices"

# Turn off a specific device
"Turn off the living room AC"

# Set temperature for all devices
"Set all ACs to 24 degrees"

# Set temperature for specific device
"Set the bedroom AC to 22 degrees"
```

### Mode and Fan Control
```
# Change operating mode
"Set all ACs to cooling mode"
"Switch bedroom AC to auto mode"

# Adjust fan speed
"Set fan to high speed for all devices"
"Change living room AC fan to low"

# Apply presets
"Set all ACs to eco mode"
"Enable boost mode for bedroom AC"
```

### Advanced Controls
```
# Control swing modes
"Set vertical swing to position 3 for all ACs"
"Change horizontal swing to auto for bedroom AC"

# Get device information
"Show me all available AC devices"
"Get details for the living room AC"
```

## FastAPI Integration

The project includes an optional FastAPI server (`fastapi_server.py`) for REST API access:

```bash
uvicorn fastapi_server:app --reload
```

### API Endpoints
- `GET /devices` - Get all device status
- `POST /devices/on` - Turn on all devices
- `POST /devices/off` - Turn off all devices
- `POST /devices/temperature` - Set temperature for all devices
- `POST /device/control` - Control specific device

## Architecture

### Core Components
- **`miraie_mcp.py`** - Main MCP server implementation
- **`api.py`** - Panasonic MirAIe API client
- **`device.py`** - Device abstraction and control logic
- **`enums.py`** - Enumeration definitions for modes and states
- **`fastapi_server.py`** - Optional REST API server

### Authentication Types
Supports multiple authentication methods:
- Mobile phone number
- Email address  
- Username

### Device Management
- Automatic device discovery upon connection
- Context-managed device connections
- Error handling and device validation
- Support for multiple simultaneous devices

## Troubleshooting

### Common Issues
1. **Authentication Errors**: Verify credentials in `.env` file
2. **Device Not Found**: Check device name spelling and availability
3. **Connection Issues**: Ensure stable internet connection
4. **Permission Errors**: Verify MirAIe account has device access

### Debug Mode
Enable debug logging by setting stderr output in the terminal:
```bash
python miraie_mcp.py 2>debug.log
```

## Security Notes

- Store credentials securely using environment variables
- Never commit credentials to version control
- Use secure network connections for device communication
- Regularly update authentication tokens

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly with actual devices
5. Submit a pull request

## License

[Add your license information here]

## Support

For issues and support:
1. Check the troubleshooting section
2. Review device compatibility
3. Open an issue with detailed error logs
4. Include device model and network setup details

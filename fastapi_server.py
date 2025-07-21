from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import asyncio
from ac_test import (
    turn_on_all_devices,
    turn_off_all_devices,
    set_temperature_all,
    control_device_by_name,
    get_device_status,
    run_test_sequence
)

app = FastAPI(title="MirAIe AC Control API", version="1.0.0")

# Pydantic models for request/response
class DeviceControlRequest(BaseModel):
    device_name: str
    action: str  # 'on', 'off', or 'temp'
    temperature: Optional[int] = None

class TemperatureRequest(BaseModel):
    temperature: int

class APIResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Any] = None

@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "MirAIe AC Control API",
        "version": "1.0.0",
        "endpoints": {
            "GET /devices": "Get all device status",
            "POST /devices/on": "Turn on all devices",
            "POST /devices/off": "Turn off all devices",
            "POST /devices/temperature": "Set temperature for all devices",
            "POST /device/control": "Control specific device",
            "POST /test": "Run test sequence"
        }
    }

@app.get("/devices", response_model=APIResponse)
async def get_devices():
    """Get status of all AC devices."""
    try:
        devices = await get_device_status()
        return APIResponse(
            success=True,
            message="Retrieved device status successfully",
            data=devices
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get devices: {str(e)}")

@app.post("/devices/on", response_model=APIResponse)
async def turn_on_devices():
    """Turn on all AC devices."""
    try:
        result = await turn_on_all_devices()
        return APIResponse(
            success=True,
            message=result
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to turn on devices: {str(e)}")

@app.post("/devices/off", response_model=APIResponse)
async def turn_off_devices():
    """Turn off all AC devices."""
    try:
        result = await turn_off_all_devices()
        return APIResponse(
            success=True,
            message=result
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to turn off devices: {str(e)}")

@app.post("/devices/temperature", response_model=APIResponse)
async def set_devices_temperature(request: TemperatureRequest):
    """Set temperature for all AC devices."""
    try:
        if not (16 <= request.temperature <= 30):
            raise HTTPException(status_code=400, detail="Temperature must be between 16-30°C")
        
        result = await set_temperature_all(request.temperature)
        return APIResponse(
            success=True,
            message=result
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to set temperature: {str(e)}")

@app.post("/device/control", response_model=APIResponse)
async def control_device(request: DeviceControlRequest):
    """Control a specific AC device."""
    try:
        if request.action == 'temp' and request.temperature is None:
            raise HTTPException(status_code=400, detail="Temperature is required for 'temp' action")
        
        if request.temperature is not None and not (16 <= request.temperature <= 30):
            raise HTTPException(status_code=400, detail="Temperature must be between 16-30°C")
        
        result = await control_device_by_name(
            request.device_name,
            request.action,
            request.temperature
        )
        
        if "not found" in result.lower():
            raise HTTPException(status_code=404, detail=result)
        
        return APIResponse(
            success=True,
            message=result
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to control device: {str(e)}")

@app.post("/test", response_model=APIResponse)
async def run_test():
    """Run the original test sequence."""
    try:
        result = await run_test_sequence()
        return APIResponse(
            success=True,
            message=result
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Test failed: {str(e)}")

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "MirAIe AC Control API"}

if __name__ == "__main__":
    import uvicorn
    print("Starting MirAIe AC Control API server...")
    print("API Documentation will be available at: http://localhost:8000/docs")
    uvicorn.run(app, host="0.0.0.0", port=8000)

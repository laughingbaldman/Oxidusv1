# Retired GUI Files

This folder contains legacy GUI implementations and tools that have been superseded by newer versions.

## Files

### gui.py
**Status**: Retired / Legacy  
**Purpose**: Early PyQt5-based graphical user interface for Oxidus  
**Reason for Retirement**: Replaced by `chromium_gui.py` which uses PyQt5 WebEngine for better web integration and Flask backend support  
**Last Known Function**: Provided basic chat interface for Oxidus interaction

### main.py
**Status**: Retired / Legacy  
**Purpose**: Likely an old entry point for running Oxidus  
**Reason for Retirement**: Functionality consolidated into `chromium_gui.py`  
**Related Files**: `chromium_gui.py` is the current primary entry point

### monitor.py
**Status**: Retired / Legacy  
**Purpose**: Monitoring/status tracking utility for Oxidus  
**Reason for Retirement**: System status now integrated into the main GUI via `/api/status` endpoint  
**Related Files**: Status display visible in `chromium_gui.py` sidebar panel

## Current Active GUI

**`chromium_gui.py`** - Current primary GUI  
- Uses PyQt5 WebEngine for embedded Chromium browser
- Integrates with Flask backend (`web_gui.py`)
- Displays conversation, thoughts, knowledge organization, and system status
- Server runs at `http://127.0.0.1:5000`

**`web_gui.py`** - Flask backend server  
- REST API endpoints for all Oxidus interactions
- Handles conversation persistence
- Manages knowledge organization display
- Required component for `chromium_gui.py`

## To Restore

If any retired file needs to be restored, simply move it from this folder back to the main project directory:
```
Move-Item -Path "retired\<filename>" -Destination ".." -Force
```

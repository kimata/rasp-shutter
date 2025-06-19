# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Japanese electric shutter automation application (`rasp-shutter`) that controls electric shutters automatically based on schedules and light sensors. The system consists of a Vue.js frontend and Flask backend that communicates with ESP32 devices via REST API.

## Architecture

- **Frontend**: Vue 3 with Bootstrap Vue Next, served from `/rasp-shutter/` base path
- **Backend**: Flask app with modular blueprints (control, schedule, sensor, logging)
- **Data**: SQLite database for logs, YAML configuration files
- **Hardware Interface**: REST API communication with ESP32 devices
- **Deployment**: Docker containers and Kubernetes support

## Key Development Commands

### Frontend (Vue.js)
```bash
npm ci                    # Install dependencies
npm run dev              # Development server
npm run build            # Production build
npm run lint             # ESLint with auto-fix
npm run format           # Prettier formatting
```

### Backend (Python)
```bash
rye sync                 # Install Python dependencies with Rye
rye run python flask/src/app.py    # Run Flask server directly
```

### Testing
```bash
rye run pytest          # Run all tests with coverage
rye run pytest tests/test_basic.py    # Run specific test file
```

### Docker
```bash
docker compose run --build --rm --publish 5000:5000 rasp-shutter
```

## Flask Application Structure

The Flask app uses a modular blueprint architecture:
- `rasp_shutter.webapp_control` - Manual shutter control
- `rasp_shutter.webapp_schedule` - Schedule management
- `rasp_shutter.webapp_sensor` - Sensor data handling
- `my_lib.webapp.*` - Shared library modules (logging, events, utilities)

All routes are prefixed with `/rasp-shutter` (configured in `my_lib.webapp.config.URL_PREFIX`).

## Configuration

- Main config: `config.yaml` (copy from `config.example.yaml`)
- Schema validation: `config.schema`
- Environment variable `DUMMY_MODE` controls test/simulation mode

## Test Configuration

Tests use pytest with:
- HTML reports generated in `tests/evidence/`
- Coverage reports in `tests/evidence/coverage/`
- Playwright for browser automation tests
- Time-machine for date/time mocking

# Solar Investigator ADK Backend

A FastAPI backend powered by Google's Agent Development Kit (ADK) for solar project investigation and analysis.

## Project Structure

```
backend/
├── src/
│   ├── adk/                    # ADK components
│   │   ├── agents/             # ADK agent implementations
│   │   ├── tools/              # Solar investigation tools
│   │   ├── callbacks/          # Event callbacks
│   │   ├── services/           # ADK services (session, memory, artifact)
│   │   ├── models/             # Data models
│   │   └── config/             # ADK runtime configuration
│   └── main.py                 # FastAPI application entry point
├── tests/                      # Test files
├── pyproject.toml             # Project configuration and dependencies
├── .env.example               # Environment variables template
└── README.md                  # This file
```

## Installation

### Prerequisites

- Python 3.9+
- uv package manager

### Setup

1. **Clone the repository and navigate to the backend directory:**
   ```bash
   cd backend
   ```

2. **Install dependencies using uv:**
   ```bash
   uv sync
   ```

3. **Set up environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your specific configuration
   ```

4. **Configure Google Cloud credentials (optional):**
   - Set up a Google Cloud project
   - Enable necessary APIs (AI Platform, etc.)
   - Download service account credentials
   - Set GOOGLE_APPLICATION_CREDENTIALS in .env

## Development

### Running the Development Server

```bash
# Using uv
uv run python src/main.py

# Or using uvicorn directly
uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- Main API: http://localhost:8000
- Interactive docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src --cov-report=html
```

### Code Formatting

```bash
# Format code
uv run black src tests

# Sort imports
uv run isort src tests

# Type checking
uv run mypy src
```

## Configuration

The application uses environment variables for configuration. See `.env.example` for all available options.

Key configuration options:
- `DEBUG`: Enable debug mode
- `GOOGLE_PROJECT_ID`: Google Cloud project ID
- `ADK_MODEL_NAME`: ADK model to use (default: gemini-1.5-pro)
- `MAX_INVESTIGATION_DURATION`: Maximum investigation duration in seconds

## API Endpoints

### Current Endpoints

- `GET /` - Root endpoint with basic information
- `GET /health` - Health check endpoint

### Planned Endpoints (Phase 4)

- `POST /api/investigations/start` - Start new investigation using ADK agent
- `GET /api/investigations/{id}/stream` - Stream investigation progress via SSE
- `POST /api/investigations/{id}/interact` - Send messages to running investigation
- `GET /api/investigations/{id}/artifacts` - Retrieve investigation artifacts

## ADK Integration

This backend integrates Google's Agent Development Kit (ADK) to provide:

1. **Event-Driven Architecture**: Uses ADK's event loop for investigation workflow
2. **Agent-Based Processing**: Solar investigation agent with specialized tools
3. **Real-time Streaming**: Server-Sent Events for live investigation updates
4. **Session Management**: Persistent investigation sessions with state management
5. **Tool Integration**: Modular tools for different investigation steps

## Development Phases

- ✅ **Phase 1**: ADK Environment Setup (COMPLETED)
- 🔄 **Phase 2**: Core ADK Components (Next)
- 📋 **Phase 3**: ADK Services Integration
- 📋 **Phase 4**: FastAPI Integration
- 📋 **Phase 5**: Investigation Workflow Implementation

## License

Apache License 2.0

# Minimal Task List: Migration to Google Agent ADK with FastAPI

## Overview
This task list outlines the steps to migrate the Solar Investigator project from LangGraph to Google's Agent Development Kit (ADK) while maintaining compatibility with the existing React frontend.

## 🎯 Goal
Create a FastAPI backend powered by Google Agent ADK that:
- Provides the same REST API endpoints for the frontend
- Implements a Solar Investigation Agent using ADK's event-driven architecture
- Replaces the current LangGraph agent with ADK agents, tools, and callbacks
- Maintains real-time streaming capabilities for investigation processes

## 📋 Task Breakdown

### Phase 1: ADK Environment Setup (Priority: HIGH)

#### Task 1.1: Install and Configure ADK
- [x] Install Google ADK Python SDK: `pip install google-adk-python`
- [x] Create `backend/requirements.txt` with ADK dependencies
- [x] Set up ADK configuration files and environment variables
- [ ] Configure Google Cloud credentials for ADK services

#### Task 1.2: Create ADK Project Structure
- [x] Create `backend/src/adk/` directory structure:
  ```
  backend/src/adk/
  ├── agents/          # ADK agent implementations ✅
  ├── tools/           # Solar investigation tools ✅
  ├── callbacks/       # Event callbacks
  ├── services/        # ADK services (session, memory, artifact)
  ├── models/          # Data models (keep existing)
  ├── controllers/     # API controllers ✅
  └── config/          # ADK runtime configuration ✅
  ```

### Phase 2: Core ADK Components (Priority: HIGH)

#### Task 2.1: Create Solar Investigation Agent
- [x] Implement `SolarInvestigationAgent` extending `LlmAgent`
- [x] Define agent's role and capabilities for solar project analysis
- [x] Set up Gemini model integration for the agent
- [x] Configure agent's system prompts and behavior

#### Task 2.2: Implement Investigation Tools
- [x] Create `WebSearchTool` for gathering solar installation data
- [x] Create `DataAnalysisTool` for processing investigation results
- [x] Create `ReportGenerationTool` for creating investigation summaries
- [x] Create `ProjectValidationTool` for validating solar project parameters

#### Task 2.3: Set up ADK Event Handlers
- [x] Implement event callbacks for investigation progress tracking
- [ ] Create state management for investigation sessions
- [ ] Set up event streaming for real-time frontend updates

### Phase 3: ADK Services Integration (Priority: MEDIUM)

#### Task 3.1: Configure ADK Services
- [ ] Set up `SessionService` for managing investigation sessions
- [ ] Configure `ArtifactService` for storing investigation documents/images
- [ ] Implement `MemoryService` for maintaining context across investigations
- [ ] Create custom services for Solar domain-specific operations

#### Task 3.2: Implement ADK Runner
- [ ] Create `InvestigationRunner` class
- [ ] Configure event loop for investigation workflow
- [ ] Set up error handling and recovery mechanisms
- [ ] Implement streaming response handling

### Phase 4: FastAPI Integration (Priority: HIGH)

#### Task 4.1: Create ADK-FastAPI Bridge
- [ ] Create `FastAPIADKBridge` class to integrate ADK runner with FastAPI
- [ ] Implement endpoint handlers that invoke ADK agents
- [ ] Set up SSE (Server-Sent Events) for streaming ADK events to frontend
- [ ] Configure CORS and middleware for frontend communication

#### Task 4.2: Implement Investigation Endpoints
- [x] `POST /api/investigations/start` - Start new investigation using ADK agent
- [x] `GET /api/investigations/{id}/stream` - Stream investigation progress via SSE
- [x] `POST /api/investigations/{id}/interact` - Send messages to running investigation
- [x] `GET /api/investigations/{id}/artifacts` - Retrieve investigation artifacts

#### Task 4.3: Maintain Existing API Compatibility
- [x] Keep existing REST endpoints for projects, work orders, dashboard
- [x] Ensure data models remain compatible with frontend
- [x] Add ADK-specific fields to models (session_id, event_history, etc.)

### Phase 5: Investigation Workflow Implementation (Priority: HIGH)

#### Task 5.1: Define Investigation Process
- [x] Map current investigation steps to ADK agent workflow
- [x] Implement multi-step investigation process:
  1. Project parameter collection ✅
  2. Site analysis research ✅
  3. Regulatory compliance check ✅
  4. Technical feasibility assessment ✅
  5. Cost estimation ✅
  6. Risk analysis ✅
  7. Final recommendation generation ✅

#### Task 5.2: Implement Agent-Tool Interactions
- [x] Configure agent to use tools in sequence
- [x] Set up tool result processing and state updates
- [x] Implement error handling for tool failures
- [x] Create investigation checkpoint system

### Phase 6: Frontend Integration (Priority: MEDIUM)

#### Task 6.1: Update API Client
- [ ] Add new endpoints to `frontend/src/lib/api.ts`
- [ ] Implement SSE client for investigation streaming
- [ ] Add ADK-specific types and interfaces
- [ ] Handle investigation session management

#### Task 6.2: Enhance Investigation UI
- [ ] Update `InvestigationInterface.tsx` for ADK integration
- [ ] Add real-time progress indicators
- [ ] Implement investigation interaction capabilities
- [ ] Add artifact display components

### Phase 7: Testing and Optimization (Priority: MEDIUM)

#### Task 7.1: Unit Testing
- [ ] Test ADK agent behavior and tool interactions
- [ ] Test FastAPI endpoints with ADK integration
- [ ] Test event streaming and state management
- [ ] Test error handling and recovery

#### Task 7.2: Integration Testing
- [ ] End-to-end testing of investigation workflow
- [ ] Frontend-backend integration testing
- [ ] Performance testing for concurrent investigations
- [ ] Load testing for ADK event processing

#### Task 7.3: Optimization
- [ ] Optimize ADK agent performance
- [ ] Implement caching for common investigation patterns
- [ ] Optimize event streaming for large investigations
- [ ] Monitor memory usage and optimize session management

### Phase 8: Documentation and Deployment (Priority: LOW)

#### Task 8.1: Documentation
- [ ] Document ADK agent architecture and design decisions
- [ ] Create API documentation for new endpoints
- [ ] Update deployment instructions
- [ ] Create troubleshooting guide

#### Task 8.2: Deployment Configuration
- [ ] Update Docker configuration for ADK dependencies
- [ ] Configure Google Cloud services for production
- [ ] Set up monitoring and logging for ADK components
- [ ] Update CI/CD pipeline for ADK testing

## 🔧 Technical Implementation Notes

### ADK Agent Design Pattern
```python
# Example structure for SolarInvestigationAgent
class SolarInvestigationAgent(LlmAgent):
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        # 1. Analyze project parameters
        # 2. Use tools for research and analysis
        # 3. Yield events for frontend streaming
        # 4. Generate final recommendations
```

### FastAPI Integration Pattern
```python
# Example endpoint that uses ADK
@app.post("/api/investigations/start")
async def start_investigation(request: StartInvestigationRequest):
    runner = InvestigationRunner(agent=solar_agent)
    session = await session_service.create_session()
    
    # Stream events back to frontend via SSE
    async for event in runner.run_async(session, request.query):
        yield format_sse_event(event)
```

### Event Streaming Architecture
- Use ADK's built-in event system for progress tracking
- Stream events to frontend via Server-Sent Events (SSE)
- Maintain session state for investigation continuity
- Handle reconnection and state recovery

## 🎯 Success Criteria
1. ✅ ADK agent successfully replaces LangGraph functionality
2. ✅ Frontend maintains full compatibility with minimal changes
3. ✅ Real-time investigation streaming works smoothly
4. ✅ All existing API endpoints continue to function
5. ✅ Investigation quality matches or exceeds current system
6. ✅ System handles concurrent investigations efficiently

## 📦 Dependencies to Add
```
google-adk-python>=1.0.0
google-cloud-aiplatform>=1.0.0
fastapi>=0.104.0
uvicorn>=0.24.0
asyncio-sse>=1.0.0
```

## 🚨 Risk Mitigation
- Keep existing LangGraph code until ADK migration is fully tested
- Implement feature flags for gradual ADK rollout
- Maintain API backward compatibility during transition
- Set up comprehensive monitoring for ADK performance
- Create rollback procedures for deployment issues

## 🔧 RECENT REFACTORING CHANGES (Completed)

### **Major Simplification and Code Cleanup (June 15, 2025)**

#### ✅ **Removed Unnecessary Complexity**
- **Deleted obsolete files:**
  - `src/adk/agents/solar_agent.py` (sub-agent, not needed)
  - `src/adk/agents/solar_investigation_agent_new.py` (duplicate)
  - All tool class files in `src/adk/tools/`:
    - `web_search_tool.py`
    - `data_analysis_tool.py` 
    - `report_generation_tool.py`
    - `project_validation_tool.py`

#### ✅ **Simplified Agent Architecture**
- **Single Root Agent:** Replaced complex sub-agent structure with one clean `LlmAgent`
- **Simple Tool Functions:** Converted tool classes to simple Python functions:
  - `analyze_solar_feasibility()` - Calculates feasibility scores and costs
  - `get_solar_incentives()` - Retrieves state-specific incentive information
- **Clean ADK Pattern:** Now follows official Google ADK sample documentation exactly

#### ✅ **Code Quality Improvements**
- **Better Formatting:** Applied PEP 8 standards and consistent spacing
- **Cleaner Structure:** Removed duplicate files and consolidated code
- **Documentation:** Added clear docstrings and inline comments

#### ✅ **Controller Simplification**
- **Single Controller:** Consolidated to `investigation_controller.py`
- **Clean Endpoints:**
  - `POST /api/investigations/solar-feasibility` - Main investigation endpoint
  - `GET /api/investigations/health` - Service health check
  - `GET /api/investigations/demo` - Quick demo test
- **Removed Duplicates:** Deleted `investigation_controller_simple.py` and backup files

#### ✅ **Testing Infrastructure**
- **HTTP Test File:** Created comprehensive `test.http` with:
  - Health check tests
  - Demo endpoint tests
  - Multiple solar feasibility scenarios (CA, TX, NY, FL)
  - Different property types and usage levels

#### ✅ **Current Clean Architecture**
```
backend/src/adk/
├── agents/
│   ├── __init__.py                     # Clean exports
│   └── solar_investigation_agent.py    # Single root agent (improved formatting)
├── controllers/
│   ├── __init__.py                     # Router exports
│   └── investigation_controller.py     # Simplified endpoints
├── tools/
│   └── __init__.py                     # Empty (tools now in agent)
├── services/
│   └── adk_services.py                 # ADK service integrations
└── config/
    └── settings.py                     # Configuration
```

#### ✅ **Benefits Achieved**
- **Maintainable:** Single-file agent following ADK best practices
- **Testable:** Comprehensive HTTP test suite
- **Clean:** No duplicated or obsolete code
- **Simple:** Removed unnecessary complexity and sub-agents
- **Standard:** Follows official Google ADK documentation patterns

---

# Original Task List Continues Below

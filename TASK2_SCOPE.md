# Solar Farm AI Investigation System
## Hackathon PRD - Simple & Focused

---

## Scope Transformation

**FROM**: Solar panel installation investigator  
**TO**: Solar farm O&M AI investigation platform

---

## Core Features (Hackathon MVP)

### 1. Investigations Tab (Main Dashboard)
**Current State**: Shows investigation results  
**New State**: Real-time AI agent investigation chat/status

**UI Components:**
- Investigation list with status (Running/Complete/Failed)
- Live chat window showing AI agent conversations
- Simple progress bar for investigation status
- "Start Investigation" button

### 2. AI Agent System
**Simple Multi-Agent Setup:**
- **Data Agent**: Analyzes historical performance data
- **Alert Agent**: Identifies anomalies and issues  
- **Coordinator**: Manages workflow and decisions

**Agent Flow:**
1. User clicks "Start Investigation"
2. Agents analyze data and chat with each other
3. System presents findings to human
4. Human decides: "Create Report" or "Create Work Order"

### 3. FastAPI Backend Scope

#### New Endpoints (Minimal):
```python
# Investigation Management
GET /api/investigations/          # List investigations
POST /api/investigations/         # Start new investigation
GET /api/investigations/{id}/chat # Get agent chat history
POST /api/investigations/{id}/decide # Human decision (report/workorder)

# Agent Management  
GET /api/agents/status           # Agent health check
POST /api/agents/trigger         # Trigger Google SDK agents
```

#### Simple Data Models:
```python
class Investigation:
    id: str
    status: str  # "running", "complete", "failed"
    agent_chat: List[str]  # Simple chat messages
    findings: str
    created_at: datetime

class AgentMessage:
    agent_name: str
    message: str
    timestamp: datetime
```

---

## Technical Implementation (Hackathon)

### Frontend (Angular)
**Single Page Changes:**
- Replace "Investigations" tab content
- Add WebSocket for real-time agent chat
- Simple decision buttons (Report/Work Order)

### Backend (FastAPI)
**Core Functions:**
1. **Trigger Google SDK agents** when investigation starts
2. **Stream agent communications** via WebSocket
3. **Collect agent findings** and present to human
4. **Route decisions** to existing work order/report systems

### Google SDK Integration
**Minimal Setup:**
- Deploy 3 simple agents (Data, Alert, Coordinator)
- Basic agent-to-agent communication
- Simple status reporting back to FastAPI

---

## Hackathon Timeline (48 hours)

### Day 1 (24 hours)
- **Hours 1-8**: Setup Google SDK agents + basic FastAPI endpoints
- **Hours 9-16**: Frontend investigation tab + WebSocket integration  
- **Hours 17-24**: Agent communication and basic workflow

### Day 2 (24 hours)
- **Hours 1-8**: Polish UI and add decision interface
- **Hours 9-16**: Testing and bug fixes
- **Hours 17-24**: Demo preparation and final touches

---

## Demo Flow (5 minutes)

1. **Show current system** (installation investigator)
2. **Click "Start Investigation"** - agents begin analyzing
3. **Watch real-time agent chat** - AI agents discussing findings
4. **Human decision point** - choose Report or Work Order
5. **Show generated outcome** - work order created for technician

---

## Success Criteria (Hackathon)

- ✅ AI agents can communicate and analyze data
- ✅ Real-time chat interface works
- ✅ Human can make decisions based on AI findings
- ✅ System integrates with existing work order flow
- ✅ Demo runs smoothly in 5 minutes

---

*Hackathon MVP - Keep it simple, make it work!*
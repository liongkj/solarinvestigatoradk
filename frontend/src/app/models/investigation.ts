/**
 * TypeScript models for Solar Investigation management
 * These models match the backend Pydantic models for API compatibility
 */

export enum InvestigationStatus {
    PENDING = 'pending',
    RUNNING = 'running',
    COMPLETED = 'completed',
    FAILED = 'failed',
    CANCELLED = 'cancelled'
}

export enum AgentMessageType {
    USER = 'user',
    AGENT = 'agent',
    SYSTEM = 'system',
    THINKING = 'thinking',
    TOOL_CALL = 'tool_call',
    TOOL_RESULT = 'tool_result'
}

export interface AgentMessage {
    id: string;
    investigation_id: string;
    message_type: AgentMessageType;
    content: string;
    metadata?: { [key: string]: any };
    timestamp: string; // ISO string from backend

    // UI State fields
    ui_summary?: string; // 10-word UI summary for display
    ui_state?: { [key: string]: any }; // UI-specific state data
    show_full_content?: boolean; // Whether to show full content by default
}

export interface InvestigationRequest {
    plant_id: string;
    start_date: string; // ISO date string (YYYY-MM-DD)
    end_date: string; // ISO date string (YYYY-MM-DD)
    additional_notes?: string;
    parent_id?: string; // ID of parent investigation if this is a retry
}

export interface Investigation {
    id: string;
    plant_id: string;
    plant_name?: string; // Will be populated from plant data
    start_date: string; // ISO date string
    end_date: string; // ISO date string
    additional_notes?: string;
    status: InvestigationStatus;
    session_id?: string;
    user_id: string;
    parent_id?: string; // ID of parent investigation if this is a retry
    created_at: string; // ISO string from backend
    updated_at: string; // ISO string from backend
    completed_at?: string;
    result?: { [key: string]: any };
    error_message?: string;
    agent_stats?: { // Rich ADK agent interaction statistics
        total_events: number;
        user_messages: number;
        agent_responses: number;
        thinking_steps: number;
        tool_calls: number;
        tools_used: string[];
        total_agents: string[];
        session_duration?: number;
        last_activity?: string;
        progress_steps: Array<{
            step_number: number;
            step_name: string;
            timestamp: string;
            completed: boolean;
        }>;
    };
}

export interface InvestigationResponse {
    investigation: Investigation;
    message: string;
}

export interface InvestigationListResponse {
    investigations: Investigation[];
    total: number;
    page: number;
    size: number;
}

export interface ChatHistoryResponse {
    investigation_id: string;
    messages: AgentMessage[];
    total_messages: number;
}

export interface DecisionRequest {
    decision: string;
    decision_type?: string;
    notes?: string;
}

export interface DecisionResponse {
    success: boolean;
    message: string;
    updated_investigation: Investigation;
}

export interface MessageRequest {
    content: string;
    message_type: AgentMessageType;
}

export interface HealthResponse {
    status: string;
    version: string;
    timestamp: string;
    database: {
        status: string;
        total_investigations: number;
    };
}

// Workorder related interfaces
export enum WorkorderStatus {
    PENDING = 'pending',
    IN_PROGRESS = 'in_progress',
    COMPLETED = 'completed',
    FAILED = 'failed'
}

export enum WorkorderType {
    MAINTENANCE = 'maintenance',
    INSPECTION = 'inspection',
    REPAIR = 'repair',
    ANALYSIS = 'analysis'
}

export interface WorkorderAgentRequest {
    todo_summary: string;
    priority?: string;
}

export interface WorkorderAgentResponse {
    workorder_id: string;
    investigation_id: string;
    todo_summary: string;
    agent_response: string;
    priority: string;
    status: WorkorderStatus;
    workorder_type: WorkorderType;
    created_at: string;
}

export interface Workorder {
    id: string;
    investigation_id: string;
    type: WorkorderType;
    description: string;
    agent_response?: string;
    priority: string;
    status: WorkorderStatus;
    created_at: string;
    updated_at: string;
    completed_at?: string;
}

// Legacy interface for backward compatibility with existing dashboard component
export interface LegacyInvestigation {
    id: string;
    title: string;
    status: 'running' | 'complete' | 'failed';
    agentChat: LegacyAgentMessage[];
    findings?: string;
    createdAt: Date;
    projectId?: string;
}

export interface LegacyAgentMessage {
    agentName: string;
    message: string;
    timestamp: Date;
}

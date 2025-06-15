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
}

export interface InvestigationRequest {
    plant_id: string;
    start_date: string; // ISO date string (YYYY-MM-DD)
    end_date: string; // ISO date string (YYYY-MM-DD)
    additional_notes?: string;
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
    created_at: string; // ISO string from backend
    updated_at: string; // ISO string from backend
    completed_at?: string;
    result?: { [key: string]: any };
    error_message?: string;
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
    additional_data?: { [key: string]: any };
}

export interface DecisionResponse {
    investigation_id: string;
    decision_accepted: boolean;
    message: string;
    next_steps?: string[];
}

export interface MessageRequest {
    content: string;
    message_type?: AgentMessageType;
}

export interface HealthResponse {
    status: string;
    timestamp: string;
    service: string;
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

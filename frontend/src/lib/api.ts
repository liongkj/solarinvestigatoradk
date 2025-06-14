/**
 * API client for the Solar Investigator backend
 */

// Types matching the backend models
export interface ProcessedEvent {
    title: string;
    data: string;
}

export interface Project {
    id: string;
    name: string;
    address: string;
    customer: string;
    status: 'planning' | 'investigation' | 'approved' | 'in-progress' | 'completed';
    createdAt: string;
    type: 'residential' | 'commercial' | 'industrial';
}

export interface Investigation {
    id: string;
    projectId: string;
    title: string;
    summary: string;
    findings: string[];
    recommendations: string[];
    status: 'completed' | 'in-progress' | 'failed';
    createdAt: string;
    processedEvents: ProcessedEvent[];
    aiResponse?: string;
}

export interface WorkOrder {
    id: string;
    projectId: string;
    title: string;
    description: string;
    tasks: string[];
    timeline: string;
    status: 'draft' | 'approved' | 'in-progress' | 'completed';
    createdAt: string;
}

export interface DashboardSummary {
    totalProjects: number;
    activeInvestigations: number;
    completedInvestigations: number;
    activeWorkOrders: number;
    completedWorkOrders: number;
}

// API configuration
const getApiUrl = () => {
    return import.meta.env.DEV
        ? "http://localhost:2024/dashboard/api"
        : "http://localhost:8123/dashboard/api";
};

class ApiError extends Error {
    constructor(public status: number, message: string) {
        super(message);
        this.name = 'ApiError';
    }
}

// Base fetch function with error handling
async function apiFetch<T>(endpoint: string): Promise<T> {
    const url = `${getApiUrl()}${endpoint}`;

    try {
        const response = await fetch(url);

        if (!response.ok) {
            throw new ApiError(response.status, `HTTP error! status: ${response.status}`);
        }

        return await response.json();
    } catch (error) {
        if (error instanceof ApiError) {
            throw error;
        }

        // Network or other errors
        throw new ApiError(0, `Network error: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
}

// API functions
export const api = {
    // Projects
    async getProjects(status?: string): Promise<Project[]> {
        const query = status ? `?status=${encodeURIComponent(status)}` : '';
        return apiFetch<Project[]>(`/projects${query}`);
    },

    async getProject(projectId: string): Promise<Project> {
        return apiFetch<Project>(`/projects/${encodeURIComponent(projectId)}`);
    },

    // Investigations
    async getInvestigations(projectId?: string, status?: string): Promise<Investigation[]> {
        const params = new URLSearchParams();
        if (projectId) params.append('project_id', projectId);
        if (status) params.append('status', status);
        const query = params.toString() ? `?${params.toString()}` : '';
        return apiFetch<Investigation[]>(`/investigations${query}`);
    },

    async getInvestigation(investigationId: string): Promise<Investigation> {
        return apiFetch<Investigation>(`/investigations/${encodeURIComponent(investigationId)}`);
    },

    // Work Orders
    async getWorkOrders(projectId?: string, status?: string): Promise<WorkOrder[]> {
        const params = new URLSearchParams();
        if (projectId) params.append('project_id', projectId);
        if (status) params.append('status', status);
        const query = params.toString() ? `?${params.toString()}` : '';
        return apiFetch<WorkOrder[]>(`/workorders${query}`);
    },

    async getWorkOrder(workOrderId: string): Promise<WorkOrder> {
        return apiFetch<WorkOrder>(`/workorders/${encodeURIComponent(workOrderId)}`);
    },

    // Dashboard
    async getDashboardSummary(): Promise<DashboardSummary> {
        return apiFetch<DashboardSummary>('/dashboard/summary');
    }
};

export { ApiError };

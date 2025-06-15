import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';

export interface Investigation {
    id: string;
    title: string;
    status: 'running' | 'complete' | 'failed';
    agentChat: AgentMessage[];
    findings?: string;
    createdAt: Date;
    projectId?: string;
}

export interface AgentMessage {
    agentName: string;
    message: string;
    timestamp: Date;
}

export interface Project {
    id: string;
    name: string;
    address: string;
    customer: string;
    status: string;
    createdAt: Date;
    type: string;
}

export interface WorkOrder {
    id: string;
    projectId: string;
    title: string;
    description: string;
    tasks: string[];
    timeline: string;
    status: string;
    createdAt: Date;
}

@Component({
    selector: 'app-dashboard',
    standalone: true,
    imports: [CommonModule],
    templateUrl: './dashboard.component.html',
    styleUrls: ['./dashboard.component.css']
})
export class DashboardComponent implements OnInit {
    activeTab: 'investigations' | 'workorders' | 'projects' = 'investigations';
    isLoading = false;
    error: string | null = null;

    // Data arrays
    investigations: Investigation[] = [];
    projects: Project[] = [];
    workOrders: WorkOrder[] = [];

    // Selected investigation for chat view
    selectedInvestigation: Investigation | null = null;

    constructor() { }

    ngOnInit(): void {
        this.loadDashboardData();
    }

    setActiveTab(tab: 'investigations' | 'workorders' | 'projects') {
        this.activeTab = tab;
    }

    async loadDashboardData() {
        this.isLoading = true;
        this.error = null;

        try {
            // TODO: Replace with actual API calls
            await this.loadInvestigations();
            await this.loadProjects();
            await this.loadWorkOrders();
        } catch (error) {
            this.error = 'Failed to load dashboard data';
            console.error('Error loading dashboard data:', error);
        } finally {
            this.isLoading = false;
        }
    }

    async loadInvestigations() {
        // TODO: implement API call
        // For now, return empty array to show empty state
        this.investigations = [];
    }

    async loadProjects() {
        // TODO: implement API call
        this.projects = [];
    }

    async loadWorkOrders() {
        // TODO: implement API call
        this.workOrders = [];
    }

    async startNewInvestigation() {
        this.isLoading = true;
        try {
            // TODO: implement API call to start investigation
            console.log('Starting new investigation...');
            // Create a mock investigation for now
            const newInvestigation: Investigation = {
                id: `inv_${Date.now()}`,
                title: `Solar Farm Investigation ${this.investigations.length + 1}`,
                status: 'running',
                agentChat: [{
                    agentName: 'System',
                    message: 'Investigation started...',
                    timestamp: new Date()
                }],
                createdAt: new Date()
            };

            this.investigations.unshift(newInvestigation);
            this.selectedInvestigation = newInvestigation;
        } catch (error) {
            this.error = 'Failed to start new investigation';
            console.error('Error starting investigation:', error);
        } finally {
            this.isLoading = false;
        }
    }

    selectInvestigation(investigation: Investigation) {
        this.selectedInvestigation = investigation;
    }

    refresh() {
        this.loadDashboardData();
    }

    getStatusColor(status: string): string {
        switch (status) {
            case 'running':
                return 'bg-primary text-white';
            case 'complete':
                return 'bg-success text-white';
            case 'failed':
                return 'bg-danger text-white';
            default:
                return 'bg-secondary text-white';
        }
    }

    formatDate(date: Date): string {
        return new Intl.DateTimeFormat('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        }).format(date);
    }
}

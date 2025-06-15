import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { NgbModal, NgbModalModule } from '@ng-bootstrap/ng-bootstrap';
import { interval, Subscription } from 'rxjs';
import { InvestigationService } from '../../services/investigation.service';
import {
    Investigation,
    InvestigationRequest,
    InvestigationStatus,
    AgentMessage,
    AgentMessageType,
    DecisionRequest
} from '../../models/investigation';

// Legacy interfaces for other tabs (to be updated later)
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
    imports: [CommonModule, FormsModule, NgbModalModule],
    templateUrl: './dashboard.component.html',
    styleUrls: ['./dashboard.component.css']
})
export class DashboardComponent implements OnInit, OnDestroy {
    activeTab: 'investigations' | 'workorders' | 'projects' = 'investigations';
    isLoading = false;
    error: string | null = null;

    // Data arrays
    investigations: Investigation[] = [];
    projects: Project[] = [];
    workOrders: WorkOrder[] = [];

    // Selected investigation for chat view
    selectedInvestigation: Investigation | null = null;
    chatMessages: AgentMessage[] = [];

    // New investigation form
    newInvestigationForm = {
        address: '',
        monthly_usage: 0,
        property_type: 'residential',
        budget_range: '',
        additional_notes: ''
    };

    // Auto-refresh subscription for chat updates
    private refreshSubscription: Subscription | null = null;

    constructor(
        private investigationService: InvestigationService,
        private modalService: NgbModal
    ) { }

    ngOnInit(): void {
        this.loadDashboardData();
        // Set up auto-refresh for selected investigation chat
        this.startChatRefresh();
    }

    ngOnDestroy(): void {
        this.stopChatRefresh();
    }

    setActiveTab(tab: 'investigations' | 'workorders' | 'projects') {
        this.activeTab = tab;
    }

    async loadDashboardData() {
        this.isLoading = true;
        this.error = null;

        try {
            await Promise.all([
                this.loadInvestigations(),
                this.loadProjects(),
                this.loadWorkOrders()
            ]);
        } catch (error) {
            this.error = 'Failed to load dashboard data';
            console.error('Error loading dashboard data:', error);
        } finally {
            this.isLoading = false;
        }
    }

    async loadInvestigations() {
        try {
            const response = await this.investigationService.getInvestigations(1, 50).toPromise();
            this.investigations = response?.investigations || [];
        } catch (error) {
            console.error('Error loading investigations:', error);
            throw error;
        }
    }

    async loadProjects() {
        // TODO: implement API call for projects
        this.projects = [];
    }

    async loadWorkOrders() {
        // TODO: implement API call for work orders
        this.workOrders = [];
    }

    async startNewInvestigation() {
        if (!this.newInvestigationForm.address || !this.newInvestigationForm.monthly_usage) {
            this.error = 'Please provide address and monthly usage';
            return;
        }

        this.isLoading = true;
        this.error = null;

        try {
            const request: InvestigationRequest = {
                address: this.newInvestigationForm.address,
                monthly_usage: this.newInvestigationForm.monthly_usage,
                property_type: this.newInvestigationForm.property_type,
                budget_range: this.newInvestigationForm.budget_range || undefined,
                additional_notes: this.newInvestigationForm.additional_notes || undefined
            };

            const response = await this.investigationService.startInvestigation(request).toPromise();
            if (response) {
                // Add to investigations list and select it
                this.investigations.unshift(response.investigation);
                this.selectedInvestigation = response.investigation;

                // Reset form
                this.newInvestigationForm = {
                    address: '',
                    monthly_usage: 0,
                    property_type: 'residential',
                    budget_range: '',
                    additional_notes: ''
                };

                // Load chat messages for the new investigation
                this.loadChatMessages();
            }
        } catch (error: any) {
            this.error = error.message || 'Failed to start new investigation';
            console.error('Error starting investigation:', error);
        } finally {
            this.isLoading = false;
        }
    }

    async selectInvestigation(investigation: Investigation) {
        this.selectedInvestigation = investigation;
        this.stopChatRefresh(); // Stop previous refresh
        await this.loadChatMessages();
        this.startChatRefresh(); // Start new refresh for selected investigation
    }

    async loadChatMessages() {
        if (!this.selectedInvestigation) return;

        try {
            const response = await this.investigationService.getChatHistory(this.selectedInvestigation.id).toPromise();
            this.chatMessages = response?.messages || [];
        } catch (error) {
            console.error('Error loading chat messages:', error);
        }
    }

    private startChatRefresh() {
        if (!this.selectedInvestigation) return;

        // Refresh chat every 3 seconds for real-time updates
        this.refreshSubscription = interval(3000).subscribe(() => {
            if (this.selectedInvestigation) {
                this.loadChatMessages();
                // Also refresh investigation status
                this.refreshInvestigationStatus();
            }
        });
    }

    public stopChatRefresh() {
        if (this.refreshSubscription) {
            this.refreshSubscription.unsubscribe();
            this.refreshSubscription = null;
        }
    }

    private async refreshInvestigationStatus() {
        if (!this.selectedInvestigation) return;

        try {
            const updated = await this.investigationService.getInvestigation(this.selectedInvestigation.id).toPromise();
            if (updated) {
                // Update in investigations list
                const index = this.investigations.findIndex(inv => inv.id === updated.id);
                if (index >= 0) {
                    this.investigations[index] = updated;
                }
                // Update selected investigation
                this.selectedInvestigation = updated;
            }
        } catch (error) {
            console.error('Error refreshing investigation status:', error);
        }
    }

    refresh() {
        this.loadDashboardData();
        if (this.selectedInvestigation) {
            this.loadChatMessages();
        }
    }

    getStatusColor(status: string): string {
        switch (status) {
            case InvestigationStatus.RUNNING:
                return 'bg-primary text-white';
            case InvestigationStatus.COMPLETED:
                return 'bg-success text-white';
            case InvestigationStatus.FAILED:
                return 'bg-danger text-white';
            case InvestigationStatus.PENDING:
                return 'bg-warning text-dark';
            case InvestigationStatus.CANCELLED:
                return 'bg-secondary text-white';
            default:
                return 'bg-secondary text-white';
        }
    }

    formatDate(dateString: string): string {
        const date = new Date(dateString);
        return new Intl.DateTimeFormat('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        }).format(date);
    }

    getInvestigationTitle(investigation: Investigation): string {
        return `${investigation.address} - ${investigation.property_type}`;
    }

    getMessageAuthor(message: AgentMessage): string {
        switch (message.message_type) {
            case AgentMessageType.SYSTEM:
                return 'System';
            case AgentMessageType.USER:
                return 'User';
            case AgentMessageType.AGENT:
                return message.metadata?.['agent_name'] || 'Agent';
            case AgentMessageType.TOOL_CALL:
                return 'Tool Call';
            case AgentMessageType.TOOL_RESULT:
                return 'Tool Result';
            default:
                return 'Unknown';
        }
    }

    isInvestigationActive(investigation: Investigation): boolean {
        return investigation.status === InvestigationStatus.RUNNING ||
            investigation.status === InvestigationStatus.PENDING;
    }

    async makeDecision(decision: string, decisionType: string = 'continue') {
        if (!this.selectedInvestigation) return;

        this.isLoading = true;
        this.error = null;

        try {
            const request: DecisionRequest = {
                decision: decision,
                decision_type: decisionType
            };

            const response = await this.investigationService.sendDecision(
                this.selectedInvestigation.id,
                request
            ).toPromise();

            if (response) {
                // Refresh the investigation and chat
                await this.refreshInvestigationStatus();
                await this.loadChatMessages();
            }
        } catch (error: any) {
            this.error = error.message || 'Failed to submit decision';
            console.error('Error making decision:', error);
        } finally {
            this.isLoading = false;
        }
    }

    openNewInvestigationModal(content: any) {
        this.modalService.open(content, { size: 'lg' });
    }
}

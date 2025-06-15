import { Component, OnInit, OnDestroy } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { CommonModule } from '@angular/common';
import { interval, Subscription, Subject } from 'rxjs';
import { takeUntil, switchMap, catchError, finalize } from 'rxjs/operators';
import { of } from 'rxjs';
import { InvestigationService } from '../../services/investigation.service';
import { Investigation, AgentMessage, InvestigationStatus, AgentMessageType } from '../../models/investigation';

interface ProgressStep {
    name: string;
    completed: boolean;
    timestamp: string | null;
}

@Component({
    selector: 'app-investigation-detail',
    standalone: true,
    imports: [CommonModule],
    templateUrl: './investigation-detail.component.html',
    styleUrls: ['./investigation-detail.component.css']
})
export class InvestigationDetailComponent implements OnInit, OnDestroy {
    investigation: Investigation | null = null;
    investigationId: string = '';
    isLoading = false;
    error: string | null = null;
    chatMessages: AgentMessage[] = [];

    // Auto-refresh subscription
    private refreshSubscription: Subscription | null = null;
    private destroy$ = new Subject<void>();

    // Progress tracking
    progressSteps: ProgressStep[] = [
        { name: 'Investigation Started', completed: false, timestamp: null },
        { name: 'Data Agent Analysis', completed: false, timestamp: null },
        { name: 'Alert Agent Review', completed: false, timestamp: null },
        { name: 'Coordinator Summary', completed: false, timestamp: null },
        { name: 'Investigation Complete', completed: false, timestamp: null }
    ];

    constructor(
        private route: ActivatedRoute,
        private router: Router,
        private investigationService: InvestigationService
    ) { }

    ngOnInit(): void {
        console.log('=== Investigation Detail Component Init ===');

        // Get investigation ID from route
        this.investigationId = this.route.snapshot.paramMap.get('id') || '';
        console.log('Investigation ID from route:', this.investigationId);

        if (!this.investigationId) {
            this.error = 'Invalid investigation ID';
            return;
        }

        this.loadInvestigationDetails();
        this.startAutoRefresh();
    }

    ngOnDestroy(): void {
        this.destroy$.next();
        this.destroy$.complete();
        this.stopAutoRefresh();
    }

    loadInvestigationDetails(): void {
        console.log('Loading investigation details for ID:', this.investigationId);
        this.isLoading = true;
        this.error = null;

        this.investigationService.getInvestigation(this.investigationId).pipe(
            takeUntil(this.destroy$),
            catchError(error => {
                console.error('Error loading investigation:', error);
                this.error = 'Failed to load investigation details';
                return of(null);
            }),
            finalize(() => {
                this.isLoading = false;
            })
        ).subscribe(investigation => {
            if (investigation) {
                console.log('Investigation loaded:', investigation);
                this.investigation = investigation;
                this.updateProgressSteps();
                this.loadChatMessages();
            }
        });
    }

    loadChatMessages(): void {
        if (!this.investigationId) return;

        this.investigationService.getChatHistory(this.investigationId).pipe(
            takeUntil(this.destroy$),
            catchError(error => {
                console.error('Error loading chat messages:', error);
                return of({ investigation_id: this.investigationId, messages: [], total_messages: 0 });
            })
        ).subscribe(response => {
            console.log('Chat history loaded:', response);
            this.chatMessages = response.messages || [];
        });
    }

    private startAutoRefresh(): void {
        console.log('Starting auto-refresh for investigation details...');

        this.refreshSubscription = interval(3000).pipe(
            takeUntil(this.destroy$),
            switchMap(() => {
                if (!this.investigationId) return of(null);

                return this.investigationService.getInvestigation(this.investigationId).pipe(
                    catchError(error => {
                        console.error('Auto-refresh error:', error);
                        return of(null);
                    })
                );
            })
        ).subscribe(investigation => {
            if (investigation) {
                this.investigation = investigation;
                this.updateProgressSteps();
                this.loadChatMessages();
            }
        });
    }

    private stopAutoRefresh(): void {
        if (this.refreshSubscription) {
            this.refreshSubscription.unsubscribe();
            this.refreshSubscription = null;
        }
    }

    private updateProgressSteps(): void {
        if (!this.investigation) return;

        // Reset progress
        this.progressSteps.forEach(step => step.completed = false);

        // Update based on investigation status and messages
        const status = this.investigation.status;
        const createdAt = this.investigation.created_at;

        // Step 1: Always completed if investigation exists
        this.progressSteps[0].completed = true;
        this.progressSteps[0].timestamp = createdAt;

        // Check message history for agent activity
        // Note: AgentMessage doesn't have agent_name, so we'll use content/metadata for detection
        const hasDataAgentMessages = this.chatMessages.some(msg =>
            msg.content?.toLowerCase().includes('data') ||
            msg.metadata?.['agent_name']?.toLowerCase().includes('data') ||
            msg.message_type === AgentMessageType.AGENT
        );

        const hasAlertAgentMessages = this.chatMessages.some(msg =>
            msg.content?.toLowerCase().includes('alert') ||
            msg.metadata?.['agent_name']?.toLowerCase().includes('alert') ||
            msg.message_type === AgentMessageType.AGENT
        );

        const hasCoordinatorMessages = this.chatMessages.some(msg =>
            msg.content?.toLowerCase().includes('coordinator') ||
            msg.metadata?.['agent_name']?.toLowerCase().includes('coordinator') ||
            msg.message_type === AgentMessageType.SYSTEM
        );

        if (hasDataAgentMessages) {
            this.progressSteps[1].completed = true;
            this.progressSteps[1].timestamp = this.getEarliestMessageTime('data');
        }

        if (hasAlertAgentMessages) {
            this.progressSteps[2].completed = true;
            this.progressSteps[2].timestamp = this.getEarliestMessageTime('alert');
        }

        if (hasCoordinatorMessages) {
            this.progressSteps[3].completed = true;
            this.progressSteps[3].timestamp = this.getEarliestMessageTime('coordinator');
        }

        // Final step based on status
        if (status === InvestigationStatus.COMPLETED || status === InvestigationStatus.FAILED) {
            this.progressSteps[4].completed = true;
            this.progressSteps[4].timestamp = this.investigation.completed_at || new Date().toISOString();
        }
    }

    private getEarliestMessageTime(agentType: string): string | null {
        const messages = this.chatMessages.filter(msg =>
            msg.content?.toLowerCase().includes(agentType) ||
            msg.metadata?.['agent_name']?.toLowerCase().includes(agentType)
        );

        if (messages.length === 0) return null;

        return messages.sort((a, b) =>
            new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
        )[0].timestamp;
    }

    // Helper methods
    getStatusBadgeClass(status: InvestigationStatus): string {
        switch (status) {
            case InvestigationStatus.PENDING:
                return 'bg-warning';
            case InvestigationStatus.RUNNING:
                return 'bg-primary';
            case InvestigationStatus.COMPLETED:
                return 'bg-success';
            case InvestigationStatus.FAILED:
                return 'bg-danger';
            default:
                return 'bg-secondary';
        }
    }

    getAgentBadgeClass(agentName: string): string {
        const name = agentName?.toLowerCase() || '';
        if (name.includes('data')) return 'bg-info';
        if (name.includes('alert')) return 'bg-warning';
        if (name.includes('coordinator')) return 'bg-success';
        return 'bg-secondary';
    }

    formatTimestamp(timestamp: string): string {
        return new Date(timestamp).toLocaleString();
    }

    goBack(): void {
        this.router.navigate(['/dashboard']);
    }

    // Agent findings by type
    getAgentFindings(agentType: string): AgentMessage[] {
        return this.chatMessages.filter(msg =>
            (msg.content?.toLowerCase().includes(agentType) ||
                msg.metadata?.['agent_name']?.toLowerCase().includes(agentType)) &&
            msg.message_type === AgentMessageType.AGENT
        );
    }

    getAllFindings(): AgentMessage[] {
        return this.chatMessages.filter(msg =>
            msg.message_type === AgentMessageType.AGENT || msg.message_type === AgentMessageType.TOOL_RESULT
        );
    }
}

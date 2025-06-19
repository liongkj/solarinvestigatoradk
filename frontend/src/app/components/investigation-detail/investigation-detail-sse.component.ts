import { Component, OnInit, OnDestroy } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { interval, Subscription, Subject, of } from 'rxjs';
import { takeUntil, switchMap, catchError, finalize } from 'rxjs/operators';
import { InvestigationService, SSEEvent } from '../../services/investigation.service';
import { Investigation, AgentMessage, InvestigationStatus, AgentMessageType } from '../../models/investigation';

interface ProgressStep {
    name: string;
    completed: boolean;
    timestamp: string | null;
}

@Component({
    selector: 'app-investigation-detail',
    standalone: true,
    imports: [CommonModule, FormsModule],
    templateUrl: './investigation-detail-sse.component.html',
    styleUrls: ['./investigation-detail.component.css']
})
export class InvestigationDetailComponent implements OnInit, OnDestroy {
    investigation: Investigation | null = null;
    investigationId: string = '';
    isLoading = false;
    error: string | null = null;
    chatMessages: AgentMessage[] = [];
    showAllThoughts = false;

    // Real-time updates via SSE
    realTimeEvents: SSEEvent[] = [];
    workorders: any[] = [];

    // Subscriptions
    private refreshSubscription: Subscription | null = null;
    private destroy$ = new Subject<void>();
    private statusRefreshInterval: any = null;
    public sseSubscription: Subscription | null = null;

    // Progress tracking
    progressSteps: ProgressStep[] = [
        { name: 'Investigation Started', completed: false, timestamp: null },
        { name: 'Data Agent Analysis', completed: false, timestamp: null },
        { name: 'Alert Agent Review', completed: false, timestamp: null },
        { name: 'Coordinator Summary', completed: false, timestamp: null },
        { name: 'Investigation Complete', completed: false, timestamp: null }
    ];

    // UI Summary support
    showUiSummaries = true;
    uiSummaryCache: Map<string, string> = new Map();

    constructor(
        private route: ActivatedRoute,
        private router: Router,
        private investigationService: InvestigationService
    ) { }

    ngOnInit(): void {
        this.investigationId = this.route.snapshot.paramMap.get('id') || '';

        if (!this.investigationId) {
            this.error = 'Invalid investigation ID';
            return;
        }

        this.loadInvestigationDetails();
        this.setupSSEStream();
        this.loadWorkorders();
    }

    ngOnDestroy(): void {
        this.destroy$.next();
        this.destroy$.complete();
        this.closeSSEStream();
        this.stopStatusRefresh();
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
            })).subscribe(investigation => {
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
                return of([]);
            })
        ).subscribe(response => {
            if (Array.isArray(response)) {
                this.chatMessages = response;
            } else {
                this.chatMessages = response.messages || [];
            }
        });
    }

    private updateProgressSteps(): void {
        if (!this.investigation) return;

        // Update based on investigation status
        this.updateProgressStepsFromAgentStats();

        if (!this.investigation.agent_stats || this.investigation.agent_stats.total_events === 0) {
            return;
        }

        const stats = this.investigation.agent_stats;
        const now = new Date().toISOString();

        // Mark steps as completed based on agent stats
        if (stats.total_events > 0) {
            this.progressSteps[0].completed = true;
            this.progressSteps[0].timestamp = now;
        }

        if (stats.total_events > 2) {
            this.progressSteps[1].completed = true;
            this.progressSteps[1].timestamp = now;
        }

        if (stats.total_events > 5) {
            this.progressSteps[2].completed = true;
            this.progressSteps[2].timestamp = now;
        }

        if (this.investigation.status === InvestigationStatus.COMPLETED) {
            this.progressSteps.forEach(step => {
                step.completed = true;
                if (!step.timestamp) step.timestamp = now;
            });
        }
    }

    private updateProgressStepsFromAgentStats(): void {
        if (!this.investigation?.agent_stats) return;

        const stats = this.investigation.agent_stats;
        const now = new Date().toISOString();

        // Use available stats properties
        if (stats.agent_responses > 0) {
            this.progressSteps[1].completed = true;
            this.progressSteps[1].timestamp = now;
        }

        if (stats.tool_calls > 0) {
            this.progressSteps[2].completed = true;
            this.progressSteps[2].timestamp = now;
        }

        if (stats.total_events > 5) {
            this.progressSteps[3].completed = true;
            this.progressSteps[3].timestamp = now;
        }
    }

    // SSE Stream setup (simplified real-time updates)
    private setupSSEStream(): void {
        if (this.investigationId) {
            this.connectSSEStream();
        }
    }

    private connectSSEStream(): void {
        if (!this.investigationId) return;

        console.log('Starting SSE stream for investigation:', this.investigationId);

        this.sseSubscription = this.investigationService.startInvestigationStream(this.investigationId)
            .pipe(takeUntil(this.destroy$))
            .subscribe({
                next: (event: SSEEvent) => {
                    console.log('SSE event received:', event);
                    this.handleSSEEvent(event);
                },
                error: (error) => {
                    console.error('SSE stream error:', error);
                    // Fallback to polling if SSE fails
                    this.startStatusRefresh();
                },
                complete: () => {
                    console.log('SSE stream completed');
                }
            });

        // Stop any existing polling since SSE handles real-time updates
        this.stopStatusRefresh();
        console.log('Stopped polling - using SSE for real-time updates');
    }

    private handleSSEEvent(event: SSEEvent): void {
        // Add to real-time events log
        this.realTimeEvents.unshift(event);

        // Keep only last 50 events
        if (this.realTimeEvents.length > 50) {
            this.realTimeEvents = this.realTimeEvents.slice(0, 50);
        }

        switch (event.type) {
            case 'message':
                if (event.message) {
                    // Add new message to chat
                    this.chatMessages.push({
                        id: event.message.id,
                        investigation_id: this.investigationId,
                        message_type: event.message.message_type,
                        content: event.message.content,
                        timestamp: event.message.timestamp,
                        metadata: {}
                    });
                }
                break;

            case 'ui_update':
                if (event.ui_summary) {
                    // Cache UI summary for display
                    this.uiSummaryCache.set(event.investigation_id, event.ui_summary);
                }
                break;

            case 'status_update':
                // Reload investigation details to get updated status
                this.loadInvestigationDetails();
                break;

            case 'workorder_status':
                // Reload workorders
                this.loadWorkorders();
                break;
        }
    }

    private closeSSEStream(): void {
        if (this.sseSubscription) {
            this.sseSubscription.unsubscribe();
            this.sseSubscription = null;
        }

        if (this.investigationId) {
            this.investigationService.stopInvestigationStream(this.investigationId);
        }
    }

    // Load workorders for this investigation
    loadWorkorders(): void {
        if (!this.investigationId) return;

        this.investigationService.getWorkorders(this.investigationId)
            .pipe(takeUntil(this.destroy$))
            .subscribe({
                next: (workorders) => {
                    this.workorders = workorders;
                },
                error: (error) => {
                    console.error('Error loading workorders:', error);
                }
            });
    }

    // Create manual workorder
    createManualWorkorder(): void {
        if (!this.investigationId) return;

        const workorderData = {
            type: 'manual',
            description: 'Manual workorder created by user',
            priority: 'medium'
        };

        this.investigationService.createWorkorder(this.investigationId, workorderData)
            .pipe(takeUntil(this.destroy$))
            .subscribe({
                next: (workorder) => {
                    console.log('Manual workorder created:', workorder);
                    this.loadWorkorders();
                },
                error: (error) => {
                    console.error('Error creating workorder:', error);
                }
            });
    }

    private stopStatusRefresh(): void {
        if (this.statusRefreshInterval) {
            clearInterval(this.statusRefreshInterval);
            this.statusRefreshInterval = null;
        }
        if (this.refreshSubscription) {
            this.refreshSubscription.unsubscribe();
            this.refreshSubscription = null;
        }
    }

    private startStatusRefresh(): void {
        this.stopStatusRefresh();

        // Only start polling if SSE is not connected
        if (!this.sseSubscription) {
            this.statusRefreshInterval = setInterval(() => {
                this.loadInvestigationDetails();
            }, 5000);
        }
    }

    // UI Helper methods
    isInProgress(): boolean {
        return this.investigation?.status === InvestigationStatus.RUNNING;
    }

    isCompleted(): boolean {
        return this.investigation?.status === InvestigationStatus.COMPLETED;
    }

    isFailed(): boolean {
        return this.investigation?.status === InvestigationStatus.FAILED;
    }

    toggleAllThoughts(): void {
        this.showAllThoughts = !this.showAllThoughts;
    }

    shouldShowMessage(message: AgentMessage): boolean {
        if (this.showAllThoughts) {
            return true;
        }
        return message.message_type !== AgentMessageType.THINKING;
    }

    getVisibleMessages(): AgentMessage[] {
        return this.chatMessages.filter(msg => this.shouldShowMessage(msg));
    }

    formatTimestamp(timestamp: string): string {
        return new Date(timestamp).toLocaleString();
    }

    getStatusClass(): string {
        if (!this.investigation) return '';

        switch (this.investigation.status) {
            case InvestigationStatus.PENDING:
                return 'status-pending';
            case InvestigationStatus.RUNNING:
                return 'status-in-progress';
            case InvestigationStatus.COMPLETED:
                return 'status-completed';
            case InvestigationStatus.FAILED:
                return 'status-failed';
            case InvestigationStatus.CANCELLED:
                return 'status-cancelled';
            default:
                return '';
        }
    }

    getMessageTypeClass(messageType: AgentMessageType): string {
        switch (messageType) {
            case AgentMessageType.AGENT:
                return 'message-agent';
            case AgentMessageType.USER:
                return 'message-user';
            case AgentMessageType.SYSTEM:
                return 'message-system';
            case AgentMessageType.THINKING:
                return 'message-thinking';
            default:
                return '';
        }
    }

    getProgressPercentage(): number {
        if (!this.progressSteps) return 0;
        const completed = this.progressSteps.filter(step => step.completed).length;
        return Math.round((completed / this.progressSteps.length) * 100);
    }

    getDisplayContent(message: AgentMessage): string {
        if (this.showUiSummaries && message.metadata?.['ui_summary']) {
            return message.metadata['ui_summary'];
        }
        return message.content;
    }

    hasUiSummary(message: AgentMessage): boolean {
        return !!(message.metadata?.['ui_summary']);
    }

    toggleContentDisplay(): void {
        this.showUiSummaries = !this.showUiSummaries;
    }
}

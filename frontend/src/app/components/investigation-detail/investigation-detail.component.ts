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
    templateUrl: './investigation-detail.component.html',
    styleUrls: ['./investigation-detail.component.css']
})
export class InvestigationDetailComponent implements OnInit, OnDestroy {
    investigation: Investigation | null = null;
    investigationId: string = '';
    isLoading = false;
    error: string | null = null;
    chatMessages: AgentMessage[] = [];
    showAllThoughts = false; // Toggle for detailed thinking messages

    // Real-time updates via SSE
    realTimeEvents: SSEEvent[] = [];
    workorders: any[] = [];

    // Auto-refresh subscription
    private refreshSubscription: Subscription | null = null;
    private destroy$ = new Subject<void>();
    private statusRefreshInterval: any = null;

    // SSE stream subscription
    private sseSubscription: Subscription | null = null;

    // Progress tracking
    progressSteps: ProgressStep[] = [
        { name: 'Investigation Started', completed: false, timestamp: null },
        { name: 'Data Agent Analysis', completed: false, timestamp: null },
        { name: 'Alert Agent Review', completed: false, timestamp: null },
        { name: 'Coordinator Summary', completed: false, timestamp: null },
        { name: 'Investigation Complete', completed: false, timestamp: null }
    ];

    // UI Summary support
    showUiSummaries = true; // Toggle between summary and full content
    uiSummaryCache: Map<string, string> = new Map(); // Cache for UI summaries

    // Streaming text support
    streamingText$ = this.investigationService.getStreamingText(this.investigationId);
    currentStreamingText = '';
    isStreaming = false;

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
        this.setupSSEStream();
        this.setupSSEStreamingEvents();
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

                    // SSE handles real-time updates, no need for polling
                    // this.startStatusRefresh();
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

    private updateProgressSteps(): void {
        if (!this.investigation) return;

        // First try to use rich ADK agent stats
        this.updateProgressStepsFromAgentStats();

        // If no agent stats available, fall back to message-based heuristics
        if (!this.investigation.agent_stats || this.investigation.agent_stats.total_events === 0) {
            // Reset progress
            this.progressSteps.forEach(step => step.completed = false);

            // Update based on investigation status and messages
            const status = this.investigation.status;
            const createdAt = this.investigation.created_at;

            // Step 1: Always completed if investigation exists
            this.progressSteps[0].completed = true;
            this.progressSteps[0].timestamp = createdAt;

            // Check message history for agent activity
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

    // Helper methods for thinking messages
    getVisibleMessages(): AgentMessage[] {
        if (this.showAllThoughts) {
            return this.chatMessages;
        }

        // Filter to show only major thinking messages and non-thinking messages
        return this.chatMessages.filter(msg => {
            if (msg.message_type !== AgentMessageType.THINKING) {
                return true; // Show all non-thinking messages
            }

            // For thinking messages, only show "major" level ones
            return msg.metadata?.['level'] === 'major';
        });
    }

    getThinkingBadgeClass(stepType: string): string {
        switch (stepType) {
            case 'handoff':
                return 'bg-primary';
            case 'decision':
                return 'bg-success';
            case 'tool_call':
                return 'bg-info';
            case 'escalation':
                return 'bg-warning';
            case 'completion':
                return 'bg-success';
            default:
                return 'bg-secondary';
        }
    }

    getThinkingIcon(stepType: string): string {
        switch (stepType) {
            case 'handoff':
                return 'fas fa-exchange-alt';
            case 'decision':
                return 'fas fa-lightbulb';
            case 'tool_call':
                return 'fas fa-cog';
            case 'escalation':
                return 'fas fa-exclamation-triangle';
            case 'completion':
                return 'fas fa-check-circle';
            case 'agent_processing':
                return 'fas fa-brain';
            case 'streaming':
                return 'fas fa-comments';
            default:
                return 'fas fa-comment-dots';
        }
    }

    toggleThoughts(): void {
        this.showAllThoughts = !this.showAllThoughts;
    }

    getDetailedThoughtsCount(): number {
        return this.chatMessages.filter(msg =>
            msg.message_type === AgentMessageType.THINKING &&
            msg.metadata?.['level'] === 'detailed'
        ).length;
    }

    hasExtraMetadata(metadata: any): boolean {
        return metadata && Object.keys(metadata).length > 1;
    }

    // Helper methods for agent stats
    getAgentStatsData() {
        return this.investigation?.agent_stats || {
            total_events: 0,
            user_messages: 0,
            agent_responses: 0,
            thinking_steps: 0,
            tool_calls: 0,
            tools_used: [],
            total_agents: [],
            progress_steps: []
        };
    }

    hasAgentActivity(): boolean {
        const stats = this.getAgentStatsData();
        return stats.total_events > 0 || this.chatMessages.length > 0;
    }

    getAgentActivitySummary(): string {
        const stats = this.getAgentStatsData();
        if (!this.hasAgentActivity()) {
            return 'No agent activity yet';
        }

        const parts = [];
        if (stats.agent_responses > 0) parts.push(`${stats.agent_responses} responses`);
        if (stats.thinking_steps > 0) parts.push(`${stats.thinking_steps} thinking steps`);
        if (stats.tool_calls > 0) parts.push(`${stats.tool_calls} tool calls`);
        if (stats.total_agents.length > 0) parts.push(`${stats.total_agents.length} agents active`);

        return parts.join(', ');
    }

    private updateProgressStepsFromAgentStats(): void {
        if (!this.investigation?.agent_stats) return;

        const stats = this.investigation.agent_stats;

        // Update progress based on rich ADK agent stats
        if (stats.progress_steps && stats.progress_steps.length > 0) {
            // Use ADK progress steps if available
            this.progressSteps = stats.progress_steps.map((step, index) => ({
                name: step.step_name,
                completed: step.completed,
                timestamp: step.timestamp
            }));
        } else {
            // Fallback to heuristic-based progress
            this.progressSteps[0].completed = true;
            this.progressSteps[0].timestamp = this.investigation.created_at;

            if (stats.agent_responses > 0) {
                this.progressSteps[1].completed = true;
                this.progressSteps[1].timestamp = stats.last_activity || null;
            }

            if (stats.tool_calls > 0) {
                this.progressSteps[2].completed = true;
                this.progressSteps[2].timestamp = stats.last_activity || null;
            }

            if (stats.total_agents.length > 1) {
                this.progressSteps[3].completed = true;
                this.progressSteps[3].timestamp = stats.last_activity || null;
            }

            if (this.investigation.status === InvestigationStatus.COMPLETED) {
                this.progressSteps[4].completed = true;
                this.progressSteps[4].timestamp = this.investigation.completed_at || null;
            }
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
                    this.handleSSEStreamingEvents(event); // Add streaming event handling
                },
                error: (error) => {
                    console.error('SSE stream error:', error);
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

    // Setup SSE for streaming events  
    private setupSSEStreamingEvents(): void {
        if (!this.investigationId) return;

        // Subscribe to streaming text accumulation
        this.streamingText$ = this.investigationService.getStreamingText(this.investigationId);
        this.streamingText$.pipe(takeUntil(this.destroy$)).subscribe(text => {
            this.currentStreamingText = text;
        });
    }

    // Setup SSE for streaming events  
    // Enhanced SSE event handling for streaming
    private handleSSEStreamingEvents(event: SSEEvent): void {
        switch (event.type) {
            case 'streaming_text_chunk':
                this.isStreaming = true;
                console.log('📝 Streaming text chunk:', event.content);
                break;

            case 'complete_text_message':
                this.isStreaming = false;
                console.log('✅ Complete text message received');
                break;

            case 'tool_call_request':
                console.log('🔧 Tool call request:', event.tool_calls);
                break;

            case 'tool_result':
                console.log('🔧 Tool result received');
                break;

            case 'streaming_error':
                console.error('❌ Streaming error:', event.error);
                this.isStreaming = false;
                break;

            default:
                console.log('📡 SSE Event:', event.type, event);
        }
    }

    private handleInvestigationUpdate(payload: any): void {
        console.log('Investigation update received:', payload);
        // Update investigation details
        this.investigation = { ...this.investigation, ...payload };
        this.updateProgressSteps();
    }

    private handleChatMessage(payload: any): void {
        console.log('Chat message received:', payload);
        // Add new message to chat history
        this.chatMessages.push(payload);
    } private handleUiSummaryUpdate(data: any): void {
        console.log('UI Summary update received via WebSocket:', data);
        if (data.ui_summary && data.investigation_id === this.investigationId) {
            // Find and update the most recent agent message directly
            for (let i = this.chatMessages.length - 1; i >= 0; i--) {
                const message = this.chatMessages[i];
                if (message.message_type === 'agent') {
                    message.ui_summary = data.ui_summary;
                    if (data.full_content) {
                        message.content = data.full_content;
                    }
                    console.log('Updated message with UI summary via WebSocket:', message);

                    // Trigger change detection
                    this.chatMessages = [...this.chatMessages];
                    break;
                }
            }
        }
    } private handleStatusUpdate(data: any): void {
        console.log('Status update received via WebSocket:', data);
        if (this.investigation && data.status && data.investigation_id === this.investigationId) {
            // Update status directly without making HTTP request
            this.investigation.status = data.status;
            this.updateProgressSteps();

            // Stop polling since WebSocket is working
            this.stopStatusRefresh();

            console.log('Investigation status updated via WebSocket to:', data.status);
        }
    } private handleNewMessage(data: any): void {
        console.log('New message received via WebSocket:', data);
        if (data && data.investigation_id === this.investigationId) {
            // Add the new message directly to chat without HTTP request
            this.chatMessages.push(data);
            this.updateProgressSteps();

            // Trigger change detection
            this.chatMessages = [...this.chatMessages];

            console.log('Added new message via WebSocket');
        } else if (data && !data.investigation_id) {
            // If it's a direct message object without investigation_id, add it
            this.chatMessages.push(data);
            this.updateProgressSteps();

            // Trigger change detection
            this.chatMessages = [...this.chatMessages];
        }
    }

    private closeWebSocket(): void {
        // WebSocket functionality removed - using SSE only
        /*
        if(this.pingInterval) {
            clearInterval(this.pingInterval);
            this.pingInterval = null;
        }
        if (this.websocket) {
            this.websocket.close();
            this.websocket = null;
        }
        */
    }

    toggleUiSummaryMode(): void {
        this.showUiSummaries = !this.showUiSummaries;
    }

    getDisplayContent(message: AgentMessage): string {
        if (this.showUiSummaries && message.ui_summary && message.message_type === 'agent') {
            return message.ui_summary;
        }
        return message.content;
    }

    shouldShowExpandButton(message: AgentMessage): boolean {
        return this.showUiSummaries && !!message.ui_summary && message.message_type === 'agent';
    }

    // Make Object available in template
    Object = Object;

    private startStatusRefresh(): void {
        // Only refresh if investigation is in progress (removed WebSocket condition - using SSE)
        if (this.investigation && (
            this.investigation.status === InvestigationStatus.PENDING ||
            this.investigation.status === InvestigationStatus.RUNNING
        )) {
            // Fallback to polling if SSE is not available
            console.log('Starting periodic status refresh as fallback');
            this.statusRefreshInterval = setInterval(() => {
                this.refreshInvestigationStatus();
            }, 10000); // Reduced frequency to 10 seconds as fallback
        } else {
            console.log('Using SSE for real-time updates, no polling needed');
        }
    }

    private refreshInvestigationStatus(): void {
        if (!this.investigationId) return;        // Only refresh if still in progress (removed WebSocket condition - using SSE)
        if (this.investigation && (
            this.investigation.status === InvestigationStatus.PENDING ||
            this.investigation.status === InvestigationStatus.RUNNING
        )) {
            console.log('Polling for investigation status (SSE fallback)...');
            this.investigationService.getInvestigation(this.investigationId).pipe(
                takeUntil(this.destroy$),
                catchError(error => {
                    console.error('Error refreshing investigation status:', error);
                    return of(null);
                })
            ).subscribe(investigation => {
                if (investigation) {
                    const oldStatus = this.investigation?.status;
                    this.investigation = investigation;
                    this.updateProgressSteps();

                    // If status changed to completed/failed, stop refreshing and reload chat
                    if (oldStatus !== investigation.status && (
                        investigation.status === InvestigationStatus.COMPLETED ||
                        investigation.status === InvestigationStatus.FAILED
                    )) {
                        this.stopStatusRefresh();
                        this.loadChatMessages();
                    }
                }
            });
        } else {
            // Stop refreshing if investigation is no longer in progress or WebSocket is working
            this.stopStatusRefresh();
        }
    }

    private stopStatusRefresh(): void {
        if (this.statusRefreshInterval) {
            clearInterval(this.statusRefreshInterval);
            this.statusRefreshInterval = null;
        }
    }

    // Helper methods for UI state
    isInvestigationInProgress(): boolean {
        return this.investigation && (
            this.investigation.status === InvestigationStatus.PENDING ||
            this.investigation.status === InvestigationStatus.RUNNING
        ) || false;
    }

    getStatusMessage(): string {
        if (!this.investigation) return 'Loading investigation...';

        switch (this.investigation.status) {
            case InvestigationStatus.PENDING:
                return 'Investigation queued and waiting to start...';
            case InvestigationStatus.RUNNING:
                return 'Investigation in progress - agents are analyzing...';
            case InvestigationStatus.COMPLETED:
                return 'Investigation completed successfully';
            case InvestigationStatus.FAILED:
                return 'Investigation failed - please check details';
            default:
                return `Investigation status: ${this.investigation.status}`;
        }
    }

    shouldShowLoadingIndicator(): boolean {
        return this.isInvestigationInProgress() || this.isLoading;
    }
}

import { Component, OnInit, OnDestroy } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { interval, Subscription, Subject, of } from 'rxjs';
import { takeUntil, switchMap, catchError, finalize } from 'rxjs/operators';
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

    // UI Summary support
    showUiSummaries = true; // Toggle between summary and full content
    uiSummaryCache: Map<string, string> = new Map(); // Cache for UI summaries

    // WebSocket connection for real-time updates
    private websocket: WebSocket | null = null;

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
        this.setupWebSocket();
    }

    ngOnDestroy(): void {
        this.destroy$.next();
        this.destroy$.complete();
        this.closeWebSocket();
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

    // WebSocket setup
    private setupWebSocket(): void {
        if (this.investigationId) {
            this.connectWebSocket();
        }
    }

    private connectWebSocket(): void {
        if (!this.investigationId) return;

        const wsUrl = `ws://localhost:8000/ws/investigations/${this.investigationId}`;
        this.websocket = new WebSocket(wsUrl);

        this.websocket.onopen = () => {
            console.log('WebSocket connected for investigation:', this.investigationId);
        };

        this.websocket.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);
                this.handleWebSocketMessage(message);
            } catch (error) {
                console.error('Error parsing WebSocket message:', error);
            }
        };

        this.websocket.onclose = () => {
            console.log('WebSocket connection closed');
            // Attempt to reconnect after 3 seconds
            setTimeout(() => {
                if (!this.destroy$.closed) {
                    this.connectWebSocket();
                }
            }, 3000);
        };

        this.websocket.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
    }

    private subscribeToInvestigationUpdates(): void {
        if (!this.websocket || !this.investigationId) return;

        const payload = {
            action: 'subscribe',
            investigationId: this.investigationId
        };

        this.websocket.send(JSON.stringify(payload));
    }

    private handleWebSocketMessage(data: string): void {
        // Handle incoming WebSocket messages
        const message = JSON.parse(data);

        switch (message.type) {
            case 'investigation_update':
                this.handleInvestigationUpdate(message.payload);
                break;
            case 'chat_message':
                this.handleChatMessage(message.payload);
                break;
            case 'ui_summary_update':
                this.handleUiSummaryUpdate(message.data);
                break;
            case 'investigation_status':
                this.handleStatusUpdate(message.data);
                break;
            case 'new_message':
                this.handleNewMessage(message.data);
                break;
            default:
                console.warn('Unknown message type:', message.type);
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
    }

    private handleUiSummaryUpdate(data: any): void {
        console.log('UI Summary update received:', data);
        if (data.ui_summary && data.investigation_id === this.investigationId) {
            // Find the most recent agent message to update with UI summary
            for (let i = this.chatMessages.length - 1; i >= 0; i--) {
                const message = this.chatMessages[i];
                if (message.message_type === 'agent') {
                    message.ui_summary = data.ui_summary;
                    // Also update full content if provided
                    if (data.full_content) {
                        message.content = data.full_content;
                    }
                    console.log('Updated message with UI summary:', message);

                    // Trigger change detection
                    this.chatMessages = [...this.chatMessages];
                    break;
                }
            }
        }
    }

    private handleStatusUpdate(data: any): void {
        console.log('Status update received:', data);
        if (this.investigation && data.status) {
            this.investigation.status = data.status;
            this.updateProgressSteps();
        }
    }

    private handleNewMessage(data: any): void {
        console.log('New message received:', data);
        if (data.message && data.investigation_id === this.investigationId) {
            this.chatMessages.push(data.message);
            // Update progress steps when new messages arrive
            this.updateProgressSteps();
        }
    }

    private closeWebSocket(): void {
        if (this.websocket) {
            this.websocket.close();
            this.websocket = null;
        }
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
}

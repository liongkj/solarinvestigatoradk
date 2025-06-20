import { Component, OnInit, OnDestroy, ChangeDetectorRef, NgZone, ChangeDetectionStrategy } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { interval, Subscription, Subject, of, BehaviorSubject, Observable } from 'rxjs';
import { takeUntil, switchMap, catchError, finalize, tap, observeOn, map, shareReplay } from 'rxjs/operators';
import { asapScheduler } from 'rxjs';
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
    imports: [CommonModule, FormsModule, RouterLink],
    templateUrl: './investigation-detail-sse.component.html',
    styleUrls: ['./investigation-detail.component.css'],
    changeDetection: ChangeDetectionStrategy.OnPush
})
export class InvestigationDetailComponent implements OnInit, OnDestroy {
    investigation: Investigation | null = null;
    investigationId: string = '';
    isLoading = false;
    error: string | null = null;
    showAllThoughts = false;

    // Private BehaviorSubjects for internal state management
    private realTimeEventsSubject = new BehaviorSubject<SSEEvent[]>([]);
    private chatMessagesSubject = new BehaviorSubject<AgentMessage[]>([]);
    private workordersSubject = new BehaviorSubject<any[]>([]);

    // Public observables for template consumption - use asObservable() to prevent external modification
    public readonly realTimeEvents$ = this.realTimeEventsSubject.asObservable().pipe(
        tap(events => console.log('realTimeEvents$ emitting:', events.length, 'events')),
        shareReplay(1)
    );

    public readonly chatMessages$ = this.chatMessagesSubject.asObservable().pipe(
        tap(messages => console.log('chatMessages$ emitting:', messages.length, 'messages')),
        shareReplay(1)
    );

    public readonly workorders$ = this.workordersSubject.asObservable().pipe(
        tap(workorders => console.log('workorders$ emitting:', workorders.length, 'workorders')),
        shareReplay(1)
    );

    // Computed observables
    public readonly visibleMessages$ = this.chatMessages$.pipe(
        map(messages => {
            console.log('Computing visibleMessages, total messages:', messages.length);
            const filtered = messages.filter(msg => this.shouldShowMessage(msg));
            console.log('Filtered messages:', filtered.length);
            return filtered;
        }),
        tap(visible => console.log('visibleMessages$ emitting:', visible.length, 'visible messages')),
        shareReplay(1)
    );

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
        private investigationService: InvestigationService,
        private cdr: ChangeDetectorRef,
        private ngZone: NgZone
    ) { }

    ngOnInit(): void {
        this.investigationId = this.route.snapshot.paramMap.get('id') || '';

        if (!this.investigationId) {
            this.error = 'Invalid investigation ID';
            return;
        }

        // Debug: Subscribe to our observables to see if they're emitting
        this.realTimeEvents$.pipe(takeUntil(this.destroy$)).subscribe(events => {
            console.log('🔥 realTimeEvents$ observable emitted to subscriber:', events.length, 'events');
        });

        this.chatMessages$.pipe(takeUntil(this.destroy$)).subscribe(messages => {
            console.log('💬 chatMessages$ observable emitted to subscriber:', messages.length, 'messages');
        });

        this.visibleMessages$.pipe(takeUntil(this.destroy$)).subscribe(messages => {
            console.log('👁️ visibleMessages$ observable emitted to subscriber:', messages.length, 'visible messages');
        });

        this.workorders$.pipe(takeUntil(this.destroy$)).subscribe(workorders => {
            console.log('📋 workorders$ observable emitted to subscriber:', workorders.length, 'workorders');
        });

        this.loadInvestigationDetails();
        this.setupSSEStream();
        this.loadWorkorders();
    }

    ngOnDestroy(): void {
        this.destroy$.next();
        this.destroy$.complete();
        this.closeSSEStream();
        this.stopStatusRefresh();

        // Clean up reactive streams
        this.realTimeEventsSubject.complete();
        this.chatMessagesSubject.complete();
        this.workordersSubject.complete();
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
            })).subscribe(response => {
                let messages: AgentMessage[] = [];
                if (Array.isArray(response)) {
                    messages = response;
                } else {
                    messages = response.messages || [];
                }

                console.log('Initial chat messages loaded:', messages.length);
                this.chatMessagesSubject.next(messages);
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
            .pipe(
                takeUntil(this.destroy$),
                observeOn(asapScheduler), // Ensure updates happen in Angular zone
                tap((event: SSEEvent) => {
                    console.log('SSE event received:', event);
                })
            )
            .subscribe({
                next: (event: SSEEvent) => {
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
        // Ensure we're in Angular's zone for proper change detection
        this.ngZone.run(() => {
            console.log('🔥 SSE Event received in Angular zone:', event);

            // Add to real-time events log using reactive stream
            const currentEvents = this.realTimeEventsSubject.value;
            const newEvents = [event, ...currentEvents.slice(0, 49)];
            this.realTimeEventsSubject.next(newEvents);

            console.log('📊 Updated realTimeEventsSubject:', newEvents.length, 'events');
            console.log('📊 Current BehaviorSubject value:', this.realTimeEventsSubject.value.length);

            switch (event.type) {
                case 'connected':
                    console.log('✅ SSE stream connected:', event.message);
                    break;

                case 'investigation_started':
                    console.log('🚀 Investigation processing started:', event.message);
                    break;

                case 'message':
                    if (event.message) {
                        // Add new message to chat using reactive stream
                        const currentMessages = this.chatMessagesSubject.value;
                        const newMessages = [...currentMessages, {
                            id: event.message.id,
                            investigation_id: this.investigationId,
                            message_type: event.message.message_type,
                            content: event.message.content,
                            timestamp: event.message.timestamp,
                            metadata: {}
                        }];
                        this.chatMessagesSubject.next(newMessages);
                        console.log('💬 Updated chatMessagesSubject:', newMessages.length, 'messages');
                    }
                    break;

                case 'ui_update':
                    if (event.ui_summary) {
                        // Cache UI summary for display
                        this.uiSummaryCache.set(event.investigation_id, event.ui_summary);
                    }
                    break;

                case 'status_update':
                    console.log('📈 Status update received:', event.status);
                    // Update status directly without reloading the entire investigation
                    if (this.investigation && event.status) {
                        this.investigation.status = event.status as InvestigationStatus;
                        this.updateProgressSteps();
                    }
                    break;

                case 'completion':
                    console.log('🏁 Investigation completed:', event.status, event.result);
                    // Update status and reload only if not already completed
                    if (this.investigation && event.status) {
                        this.investigation.status = event.status as InvestigationStatus;
                        this.updateProgressSteps();
                        // Only reload if we need fresh data (e.g., final results)
                        if (event.status === 'completed') {
                            this.loadInvestigationDetailsSilently();
                        }
                    }
                    break;

                case 'status':
                    console.log('📊 Investigation status event:', event.status);
                    // Update status directly if different
                    if (this.investigation && event.status && event.status !== this.investigation.status) {
                        this.investigation.status = event.status as InvestigationStatus;
                        this.updateProgressSteps();
                    }
                    break;

                case 'workorder_status':
                    console.log('📋 Workorder status event:', event.status, event.message);
                    // Reload workorders to show updated status
                    this.loadWorkorders();
                    break;

                case 'heartbeat':
                    console.log('💓 SSE heartbeat received');
                    break;

                case 'error':
                    console.error('❌ SSE error event:', event.error);
                    this.error = event.error || 'Unknown error occurred';
                    break;

                default:
                    console.log('❓ Unknown SSE event type:', event.type, event);
                    break;
            }

            // Manually trigger change detection with OnPush strategy
            this.cdr.markForCheck();
        });
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
                    this.workordersSubject.next(workorders);
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

    formatTimestamp(timestamp: string): string {
        return new Date(timestamp).toLocaleString();
    }

    // Debug methods to help track UI updates
    getCurrentTime(): string {
        return new Date().toLocaleTimeString();
    }

    debugObservableState(): void {
        console.log('🔍 Debug Observable State:');
        console.log('realTimeEvents count:', this.realTimeEventsSubject.value.length);
        console.log('chatMessages count:', this.chatMessagesSubject.value.length);
        console.log('workorders count:', this.workordersSubject.value.length);
        console.log('SSE subscription active:', !!this.sseSubscription);
    }

    // Test method to simulate SSE events for debugging
    simulateSSEEvent(): void {
        const testEvent: SSEEvent = {
            type: 'message',
            investigation_id: this.investigationId,
            timestamp: new Date().toISOString(),
            message: {
                id: 'test-' + Date.now(),
                message_type: 'agent_response',
                content: 'This is a test message to verify UI updates - ' + new Date().toLocaleTimeString(),
                timestamp: new Date().toISOString()
            }
        };

        console.log('🧪 Simulating SSE event:', testEvent);
        this.handleSSEEvent(testEvent);
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

    loadInvestigationDetailsSilently(): void {
        // Load investigation details without showing loading spinner
        this.investigationService.getInvestigation(this.investigationId).pipe(
            takeUntil(this.destroy$),
            catchError(error => {
                console.error('Error loading investigation details silently:', error);
                return of(null);
            })
        ).subscribe(investigation => {
            if (investigation) {
                console.log('Investigation updated silently:', investigation);
                this.investigation = investigation;
                this.updateProgressSteps();
            }
        });
    }
}

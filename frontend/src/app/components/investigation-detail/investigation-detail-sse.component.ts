import { Component, OnInit, OnDestroy, ChangeDetectorRef, NgZone, ChangeDetectionStrategy, ViewChild, ElementRef } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { interval, Subscription, Subject, of, BehaviorSubject, Observable } from 'rxjs';
import { takeUntil, switchMap, catchError, finalize, tap, observeOn, map, shareReplay } from 'rxjs/operators';
import { asapScheduler } from 'rxjs';
import { InvestigationService, SSEEvent } from '../../services/investigation.service';
import { Investigation, AgentMessage, InvestigationStatus, AgentMessageType, MessageRequest } from '../../models/investigation';

/**
 * InvestigationDetailComponent - Real-time investigation view with SSE streaming
 * 
 * TIMESTAMP HANDLING STRATEGY:
 * - All timestamps should originate from the backend for consistency and proper ordering
 * - Frontend-generated timestamps are only used as fallbacks when backend timestamps are unavailable
 * - SSE events provide authoritative timestamps that should be preserved
 * - Message ordering is handled by backend timestamps + sequence numbers for reliability
 * - After refresh, sequence numbers are assigned with large gaps (1000, 2000, 3000...) to avoid conflicts
 * - New SSE messages get higher sequence numbers to maintain chronological order
 */

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

    // Private BehaviorSubjects for internal state management
    private realTimeEventsSubject = new BehaviorSubject<SSEEvent[]>([]);
    private chatMessagesSubject = new BehaviorSubject<AgentMessage[]>([]);
    private workordersSubject = new BehaviorSubject<any[]>([]);
    private streamingTextSubject = new BehaviorSubject<string>('');
    private isStreamingSubject = new BehaviorSubject<boolean>(false);

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

    // Streaming observables for ChatGPT-style display
    public readonly streamingText$ = this.streamingTextSubject.asObservable().pipe(
        shareReplay(1)
    );

    public readonly isStreaming$ = this.isStreamingSubject.asObservable().pipe(
        shareReplay(1)
    );

    // Computed observables
    public readonly visibleMessages$ = this.chatMessages$.pipe(
        // map(messages => {
        //     console.log('Computing visibleMessages, total messages:', messages.length);
        //     // const filtered = messages.filter(msg => this.shouldShowMessage(msg));

        //     // Sort by backend timestamp primarily, sequence number as secondary
        //     // This ensures reliable ordering based on authoritative backend timestamps
        //     const sorted = filtered.sort((a, b) => {
        //         // Primary sort: backend timestamp (authoritative)
        //         const timeA = new Date(a.timestamp).getTime();
        //         const timeB = new Date(b.timestamp).getTime();

        //         if (timeA !== timeB) {
        //             console.log(`🔍 Sorting by timestamp: ${a.message_type}(${timeA}) vs ${b.message_type}(${timeB}) = ${timeA - timeB}`);
        //             return timeA - timeB; // Ascending order (oldest first)
        //         }

        //         // Secondary sort: sequence number for messages with identical timestamps
        //         const seqA = a.metadata?.['sequence'] || 0;
        //         const seqB = b.metadata?.['sequence'] || 0;
        //         console.log(`🔍 Sorting by sequence (same timestamp): ${a.message_type}(seq:${seqA}) vs ${b.message_type}(seq:${seqB}) = ${seqA - seqB}`);
        //         return seqA - seqB; // Ascending order (earliest sequence first)
        //     });

        //     console.log('Filtered and sorted messages by backend timestamp:', sorted.length);
        //     return sorted;
        // }),
        // tap(visible => console.log('visibleMessages$ emitting:', visible.length, 'visible messages')),
        shareReplay(1)
    );

    // Subscriptions
    private refreshSubscription: Subscription | null = null;
    private destroy$ = new Subject<void>();

    // Chat input properties
    public chatInput: string = '';
    public isSendingMessage: boolean = false;

    private statusRefreshInterval: any = null;
    public sseSubscription: Subscription | null = null;

    // Auto-scroll support for ChatGPT-like behavior
    @ViewChild('messagesContainer', { static: false }) messagesContainer?: ElementRef;

    // Progress tracking
    progressSteps: ProgressStep[] = [
        { name: 'Investigation Started', completed: true, timestamp: null },
        { name: 'Planning', completed: false, timestamp: null },
        { name: 'Evidence Collection', completed: false, timestamp: null },
        { name: 'Analyzing', completed: false, timestamp: null },
        { name: 'Investigation Complete', completed: false, timestamp: null }
    ];

    // UI Summary support
    showUiSummaries = false;
    uiSummaryCache: Map<string, string> = new Map();

    // Streaming text support
    currentStreamingText = '';
    isStreaming = false;

    // Message sequence counter for reliable ordering
    private messageSequenceCounter = 0;

    // Streaming timestamp from backend
    public streamingStartTimestamp: string | null = null;

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
        this.streamingTextSubject.complete();
        this.isStreamingSubject.complete();
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

                // IMPORTANT: Sort by backend timestamp only, don't assign new sequence numbers
                // Backend timestamps are authoritative and should preserve original order
                const sortedMessages = messages.sort((a, b) => {
                    const timeA = new Date(a.timestamp).getTime();
                    const timeB = new Date(b.timestamp).getTime();
                    return timeA - timeB;
                });

                // Set sequence counter to start after existing messages to avoid conflicts
                // This ensures new SSE messages don't interfere with loaded message order
                this.messageSequenceCounter = sortedMessages.length * 1000; // Use large gaps to avoid conflicts

                sortedMessages.forEach((message, index) => {
                    if (!message.metadata) {
                        message.metadata = {};
                    }
                    // Preserve original sequence if available, otherwise assign based on timestamp order
                    if (!message.metadata['sequence']) {
                        message.metadata['sequence'] = (index + 1) * 1000; // Use 1000, 2000, 3000... for loaded messages
                    }
                });

                console.log('Initial chat messages loaded with preserved timestamps:', {
                    count: messages.length,
                    sequenceCounterStart: this.messageSequenceCounter,
                    firstTimestamp: sortedMessages[0]?.timestamp,
                    lastTimestamp: sortedMessages[sortedMessages.length - 1]?.timestamp
                });
                this.chatMessagesSubject.next(sortedMessages);
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
        // Use investigation update time or current time as fallback
        const timestamp = this.investigation.updated_at || new Date().toISOString();

        // Mark steps as completed based on agent stats
        if (stats.total_events > 0) {
            this.progressSteps[0].completed = true;
            this.progressSteps[0].timestamp = timestamp;
        }

        if (stats.total_events > 2) {
            this.progressSteps[1].completed = true;
            this.progressSteps[1].timestamp = timestamp;
        }

        if (stats.total_events > 5) {
            this.progressSteps[2].completed = true;
            this.progressSteps[2].timestamp = timestamp;
        }

        if (this.investigation.status === InvestigationStatus.COMPLETED) {
            this.progressSteps.forEach(step => {
                step.completed = true;
                if (!step.timestamp) step.timestamp = timestamp;
            });
        }
    }

    private updateProgressStepsFromAgentStats(): void {
        if (!this.investigation?.agent_stats) return;

        const stats = this.investigation.agent_stats;
        // Use investigation update time or current time as fallback
        const timestamp = this.investigation.updated_at || new Date().toISOString();

        // Use available stats properties
        if (stats.agent_responses > 0) {
            this.progressSteps[1].completed = true;
            this.progressSteps[1].timestamp = timestamp;
        }

        if (stats.tool_calls > 0) {
            this.progressSteps[2].completed = true;
            this.progressSteps[2].timestamp = timestamp;
        }

        if (stats.total_events > 5) {
            this.progressSteps[3].completed = true;
            this.progressSteps[3].timestamp = timestamp;
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
                        const newMessage = {
                            id: event.message.id,
                            investigation_id: this.investigationId,
                            message_type: event.message.message_type,
                            content: event.message.content,
                            timestamp: event.message.timestamp, // Use backend timestamp directly
                            metadata: {
                                sequence: ++this.messageSequenceCounter // Assign sequence number for reliable ordering
                            }
                        };

                        console.log(`🔍 Adding SSE message: ${newMessage.message_type} with backend timestamp: ${newMessage.timestamp}, sequence: ${newMessage.metadata.sequence}`);

                        const newMessages = [...currentMessages, newMessage];
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

                case 'investigation_deleted':
                    console.log('🗑️ Investigation deleted:', event.message);
                    // Navigate back to dashboard since this investigation no longer exists
                    this.router.navigate(['/']);
                    break;

                case 'heartbeat':
                    console.log('💓 SSE heartbeat received');
                    break;

                case 'streaming_text_chunk':
                    console.log('📝 Processing streaming_text_chunk event:', {
                        hasContent: !!event.content,
                        hasFullContent: !!event.full_content
                    });

                    // ChatGPT-style streaming: start streaming on first chunk
                    this.isStreamingSubject.next(true);
                    this.isStreaming = true; // Keep for template compatibility

                    // If this is the first chunk, reset the text and capture timestamp
                    if (event.chunk_info && event.chunk_info.chunk_index === 1) {
                        this.currentStreamingText = '';
                        this.streamingTextSubject.next('');
                        // Capture the timestamp from the first streaming chunk
                        this.streamingStartTimestamp = event.timestamp;
                    }

                    // Update streaming text - ChatGPT style incremental display
                    if (event.full_content) {
                        this.currentStreamingText = event.full_content;
                        this.streamingTextSubject.next(event.full_content);
                    } else if (event.content) {
                        this.currentStreamingText = (this.currentStreamingText || '') + event.content;
                        this.streamingTextSubject.next(this.currentStreamingText);
                    }

                    // Auto-scroll during streaming for ChatGPT-like behavior
                    this.scrollToBottom();

                    console.log('📝 Streaming text updated:', {
                        content: event.content?.substring(0, 20) + '...',
                        fullLength: this.currentStreamingText.length
                    });

                    // Trigger change detection for real-time updates
                    this.cdr.detectChanges();
                    break;

                case 'complete_text_message':
                    console.log('✅ Processing complete_text_message event');

                    // ChatGPT-style completion: stop streaming and add final message
                    this.isStreamingSubject.next(false);
                    this.isStreaming = false; // Keep for template compatibility

                    if (event.content) {
                        this.currentStreamingText = event.content;
                        this.streamingTextSubject.next(event.content);

                        // Add the complete message to chat history as normal message
                        const completedMessage: AgentMessage = {
                            id: event.message?.id || `agent-${Date.now()}`,
                            investigation_id: this.investigationId,
                            message_type: AgentMessageType.AGENT,
                            content: event.content,
                            timestamp: event.timestamp, // Use backend timestamp directly - no fallback to current time
                            metadata: {
                                sequence: ++this.messageSequenceCounter // Assign sequence number for reliable ordering
                            }
                        };

                        const currentMessages = this.chatMessagesSubject.value;
                        this.chatMessagesSubject.next([...currentMessages, completedMessage]);

                        // Auto-scroll to show the new complete message
                        this.scrollToBottom();

                        // Clear streaming text and timestamp after adding to chat
                        setTimeout(() => {
                            this.currentStreamingText = '';
                            this.streamingTextSubject.next('');
                            this.streamingStartTimestamp = null; // Clear the streaming timestamp
                        }, 100); // Small delay to allow smooth transition
                    }

                    console.log('✅ Streaming completed and message added to chat');
                    this.cdr.detectChanges();
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

    // toggleAllThoughts(): void {
    //     this.showAllThoughts = !this.showAllThoughts;
    // }

    // shouldShowMessage(message: AgentMessage): boolean {
    //     if (this.showAllThoughts) {
    //         return true;
    //     }
    //     return message.message_type !== AgentMessageType.THINKING;
    // }

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



    setContentView(showSummaries: boolean): void {
        this.showUiSummaries = showSummaries;
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

    // Send chat message
    sendChatMessage(): void {
        if (!this.chatInput.trim() || this.isSendingMessage) {
            return;
        }

        const messageContent = this.chatInput.trim();
        this.isSendingMessage = true;

        // Clear input first
        this.chatInput = '';

        // IMPORTANT: Send message to backend first to get authoritative timestamp
        // This ensures proper message ordering and consistency across clients
        const messageRequest = {
            content: messageContent,
            message_type: AgentMessageType.USER
        };

        this.investigationService.sendMessage(this.investigationId, messageRequest).pipe(
            takeUntil(this.destroy$),
            finalize(() => {
                this.isSendingMessage = false;
            }),
            catchError((error: any) => {
                console.error('Error sending message:', error);
                // Add error message to chat with backend timestamp if available
                const errorMessage: AgentMessage = {
                    id: `error-${Date.now()}`,
                    investigation_id: this.investigationId,
                    message_type: AgentMessageType.SYSTEM,
                    content: 'Error sending message. Please try again.',
                    timestamp: error?.timestamp || new Date().toISOString(), // Use backend timestamp if available, fallback only for errors
                    metadata: {
                        sequence: ++this.messageSequenceCounter
                    }
                };
                const currentMessages = this.chatMessagesSubject.value;
                this.chatMessagesSubject.next([...currentMessages, errorMessage]);
                return of(null);
            })
        ).subscribe((response: any) => {
            console.log('Message sent successfully:', response);

            // Add user message to chat using backend response timestamp if available
            const userMessage: AgentMessage = {
                id: response?.id || `user-${Date.now()}`,
                investigation_id: this.investigationId,
                message_type: AgentMessageType.USER,
                content: messageContent,
                timestamp: response?.timestamp || new Date().toISOString(), // Use backend timestamp when available, fallback for user messages only
                metadata: {
                    sequence: ++this.messageSequenceCounter
                }
            };

            console.log(`🔍 Adding user message with backend timestamp: ${userMessage.timestamp}, sequence: ${userMessage.metadata?.['sequence']}`);

            // Add to messages
            const currentMessages = this.chatMessagesSubject.value;
            this.chatMessagesSubject.next([...currentMessages, userMessage]);

            // Auto-scroll to bottom after adding user message
            this.scrollToBottom();

            // The response should trigger the SSE stream for the agent's reply
        });
    }

    // Auto-scroll to bottom for ChatGPT-like behavior
    private scrollToBottom(): void {
        try {
            setTimeout(() => {
                if (this.messagesContainer) {
                    const element = this.messagesContainer.nativeElement;
                    element.scrollTop = element.scrollHeight;
                }
            }, 100); // Small delay to allow DOM updates
        } catch (err) {
            console.log('Error scrolling to bottom:', err);
        }
    }
}

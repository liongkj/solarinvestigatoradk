import { Component, OnInit, OnDestroy, ChangeDetectorRef, NgZone, ChangeDetectionStrategy, ViewChild, ElementRef } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { interval, Subscription, Subject, of, BehaviorSubject, Observable, combineLatest } from 'rxjs';
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

// Interface for parsed structured summary
interface ParsedSummary {
    mainTheme: string;
    actionTaken: string;
    actionType: string;
    description: string;
    nextSteps?: string;
    keyEvents: string[];
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

    // Track current activity from backend progress updates (using BehaviorSubject to maintain state)
    private currentActivitySubject = new BehaviorSubject<string>('Initializing...');
    public readonly currentActivity$ = this.currentActivitySubject.asObservable();

    // Chat message filtering - make reactive
    private showAllThoughtsSubject = new BehaviorSubject<boolean>(false);
    public readonly showAllThoughts$ = this.showAllThoughtsSubject.asObservable();

    // Tab management for investigation views - using reactive streams
    private activeTabSubject = new BehaviorSubject<'messages' | 'summary'>('summary');
    public readonly activeTab$ = this.activeTabSubject.asObservable();

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
    public readonly visibleMessages$ = combineLatest([
        this.chatMessages$,
        this.showAllThoughts$,
        this.activeTab$
    ]).pipe(
        map(([messages, showAllThoughts, activeTab]: [AgentMessage[], boolean, 'messages' | 'summary' | 'all']) => {
            console.log('Computing visibleMessages, total messages:', messages.length, 'showAllThoughts:', showAllThoughts, 'activeTab:', activeTab);

            // For summary tab, create AgentMessage objects from investigation.ui_summary array
            if (activeTab === 'summary') {
                const summaryMessages: AgentMessage[] = [];

                if (this.investigation?.ui_summary && Array.isArray(this.investigation.ui_summary)) {
                    this.investigation.ui_summary.forEach((summaryEntry, index) => {
                        // Handle both parsed objects and raw strings
                        let summary, fullContent, timestamp;

                        if (typeof summaryEntry === 'object' && summaryEntry !== null) {
                            summary = summaryEntry.summary || JSON.stringify(summaryEntry);
                            fullContent = summaryEntry.full_content || summaryEntry.summary;
                            timestamp = summaryEntry.timestamp || new Date().toISOString();
                        } else if (typeof summaryEntry === 'string') {
                            summary = summaryEntry;
                            fullContent = summaryEntry;
                            timestamp = new Date().toISOString();
                        } else {
                            console.warn('Unknown summary entry format:', summaryEntry);
                            return; // Skip this entry
                        }

                        const summaryMessage: AgentMessage = {
                            id: `summary-${index}`,
                            investigation_id: this.investigationId,
                            message_type: AgentMessageType.SYSTEM,
                            content: summary,
                            timestamp: timestamp,
                            metadata: {
                                sequence: index,
                                is_investigation_summary: true, // This triggers the special Investigation Summary UI
                                ui_summary: summary, // Store as string for the parseUiSummary method
                                full_content: fullContent,
                                display_mode: 'summary_only'
                            }
                        };

                        summaryMessages.push(summaryMessage);
                    });
                }

                console.log(`🔍 Summary tab - created ${summaryMessages.length} summary messages from investigation.ui_summary`);
                return summaryMessages.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());
            }

            // Add investigation summary message if available and we're in the right tab
            let allMessages = [...messages];

            // Debug: Log all current messages
            console.log('🔍 All messages before filtering:', allMessages.map(m => ({
                id: m.id,
                type: m.message_type,
                hasUiSummary: !!m.metadata?.['ui_summary'],
                isInvestigationSummary: !!m.metadata?.['is_investigation_summary']
            })));

            // Add investigation summary as first message if available (only for 'all' tab now)
            // if (activeTab === 'all') {
            //     const summaryMessage = this.createInvestigationSummaryMessage();
            //     if (summaryMessage) {
            //         allMessages = [summaryMessage, ...allMessages];
            //     }
            // }

            // // For 'all' tab, combine messages from both 'messages' and 'summary' tabs
            // if (activeTab === 'all') {
            //     // Get regular messages (same as messages tab)
            //     const regularMessages = [...allMessages];

            //     // Get summary messages (same as summary tab logic)
            //     const summaryMessages: AgentMessage[] = [];
            //     if (this.investigation?.ui_summary && Array.isArray(this.investigation.ui_summary)) {
            //         this.investigation.ui_summary.forEach((summaryEntry, index) => {
            //             // Handle both parsed objects and raw strings (same logic as Summary tab)
            //             let summary, fullContent, timestamp;

            //             if (typeof summaryEntry === 'object' && summaryEntry !== null) {
            //                 summary = summaryEntry.summary || JSON.stringify(summaryEntry);
            //                 fullContent = summaryEntry.full_content || summaryEntry.summary;
            //                 timestamp = summaryEntry.timestamp || new Date().toISOString();
            //             } else if (typeof summaryEntry === 'string') {
            //                 summary = summaryEntry;
            //                 fullContent = summaryEntry;
            //                 timestamp = new Date().toISOString();
            //             } else {
            //                 console.warn('Unknown summary entry format:', summaryEntry);
            //                 return; // Skip this entry
            //             }

            //             const summaryMessage: AgentMessage = {
            //                 id: `all-summary-${index}`,
            //                 investigation_id: this.investigationId,
            //                 message_type: AgentMessageType.SYSTEM,
            //                 content: summary,
            //                 timestamp: timestamp,
            //                 metadata: {
            //                     sequence: index,
            //                     is_investigation_summary: true, // This triggers the summary card UI
            //                     ui_summary: summary,
            //                     full_content: fullContent,
            //                     display_mode: 'summary_only'
            //                 }
            //             };

            //             summaryMessages.push(summaryMessage);
            //         });
            //     }

            //     // Combine and sort all messages by timestamp
            //     allMessages = [...regularMessages, ...summaryMessages];
            //     console.log(`🔍 All tab - combined ${regularMessages.length} regular messages + ${summaryMessages.length} summary messages`);
            // }

            // Filter messages based on showAllThoughts setting and active tab
            const filtered = allMessages.filter((msg: AgentMessage) => {
                // Tab filtering (summary tab handled above with early return)
                if (activeTab === 'messages' && msg.metadata?.['is_investigation_summary']) {
                    return false;
                }

                // Thoughts filtering
                if (showAllThoughts) {
                    return true;
                }
                return msg.message_type !== AgentMessageType.THINKING;
            }).map(msg => {
                // Modify display behavior based on active tab (summary tab handled above with early return)
                if (activeTab === 'messages') {
                    // Force full content display for messages tab
                    return {
                        ...msg,
                        metadata: {
                            ...msg.metadata,
                            display_mode: 'full_content'
                        }
                    };
                }
                return msg;
            });

            // Sort by backend timestamp primarily, sequence number as secondary
            // This ensures reliable ordering based on authoritative backend timestamps
            const sorted = filtered.sort((a: AgentMessage, b: AgentMessage) => {
                // For 'all' tab, sort purely by timestamp to achieve proper interleaving
                // For other tabs, keep investigation summary first as before
                if (activeTab !== 'all') {
                    // Special handling: investigation summary always first (for messages and summary tabs)
                    if (a.metadata?.['is_investigation_summary'] && !b.metadata?.['is_investigation_summary']) {
                        return -1;
                    }
                    if (!a.metadata?.['is_investigation_summary'] && b.metadata?.['is_investigation_summary']) {
                        return 1;
                    }
                }

                // Primary sort: backend timestamp (authoritative)
                const timeA = new Date(a.timestamp).getTime();
                const timeB = new Date(b.timestamp).getTime();

                if (timeA !== timeB) {
                    console.log(`🔍 Sorting by timestamp: ${a.message_type}(${timeA}) vs ${b.message_type}(${timeB}) = ${timeA - timeB}`);
                    return timeA - timeB; // Ascending order (oldest first)
                }

                // Secondary sort: sequence number for messages with identical timestamps
                const seqA = a.metadata?.['sequence'] || 0;
                const seqB = b.metadata?.['sequence'] || 0;
                console.log(`🔍 Sorting by sequence (same timestamp): ${a.message_type}(seq:${seqA}) vs ${b.message_type}(seq:${seqB}) = ${seqA - seqB}`);
                return seqA - seqB; // Ascending order (earliest sequence first)
            });

            console.log('Filtered and sorted messages by backend timestamp for tab:', activeTab, '- count:', sorted.length);
            return sorted;
        }),
        tap((visible: AgentMessage[]) => console.log('visibleMessages$ emitting:', visible.length, 'visible messages')),
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

    // Progress tracking - Dynamic steps based on actual agent activity
    progressSteps: ProgressStep[] = [
        { name: 'Investigation Started', completed: false, timestamp: null },
        // { name: 'Agent Analysis', completed: false, timestamp: null },
        // { name: 'Tool Execution', completed: false, timestamp: null },
        // { name: 'Data Processing', completed: false, timestamp: null },
        // { name: 'Investigation Complete', completed: false, timestamp: null }
    ];

    // Track progress step history for dynamic updates
    private agentActivities: Set<string> = new Set();
    private toolActivities: Set<string> = new Set();

    // UI Summary support
    showUiSummaries = false;
    uiSummaryCache: Map<string, string> = new Map();
    // Cache for storing latest UI summary to attach to the next agent message
    private latestUiSummary: string | null = null;
    private latestUiSummaryTimestamp: string | null = null;

    // Keep activeTab for template binding compatibility
    get activeTab(): 'messages' | 'summary' {
        return this.activeTabSubject.value;
    }

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

        this.visibleMessages$.pipe(takeUntil(this.destroy$)).subscribe((messages: AgentMessage[]) => {
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
        this.currentActivitySubject.complete();
        this.showAllThoughtsSubject.complete();
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
                    this.initializeProgressSteps();
                    this.updateProgressSteps();
                    this.loadChatMessages();

                    // Trigger recomputation of visible messages to include investigation summary
                    setTimeout(() => {
                        this.chatMessagesSubject.next(this.chatMessagesSubject.value);
                    }, 100);
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
                console.log('🔥 Setting chatMessagesSubject.next with', sortedMessages.length, 'messages');
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

    private initializeProgressSteps(): void {
        if (this.investigation) {
            // Mark investigation as started when investigation is loaded
            this.progressSteps[0].completed = true;
            this.progressSteps[0].timestamp = this.investigation.created_at;

            // Mark completion if investigation is completed
            if (this.investigation.status === 'completed') {
                this.progressSteps[4].completed = true;
                this.progressSteps[4].timestamp = this.investigation.completed_at || this.investigation.updated_at;
            }
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

    private updateDynamicProgressSteps(currentActivity: string): void {
        console.log('🔄 Updating progress steps for activity:', currentActivity);
        const timestamp = new Date().toISOString();

        // Mark investigation as started
        if (!this.progressSteps[0].completed) {
            this.progressSteps[0].completed = true;
            this.progressSteps[0].timestamp = timestamp;
            console.log('✅ Marked investigation as started');
        }

        // Track agent activities - match backend patterns
        if (currentActivity.includes('Agent') && (currentActivity.includes('analyzing') || currentActivity.includes('processing') || currentActivity.includes('working'))) {
            console.log('🤖 Agent activity detected:', currentActivity);
            this.agentActivities.add(currentActivity);
            if (!this.progressSteps[1].completed) {
                this.progressSteps[1].completed = true;
                this.progressSteps[1].timestamp = timestamp;
                this.progressSteps[1].name = `Agent Analysis (${this.agentActivities.size} agents active)`;
                console.log('✅ Marked agent analysis as completed');
            } else {
                this.progressSteps[1].name = `Agent Analysis (${this.agentActivities.size} agents active)`;
            }
        }

        // Track tool activities - match backend patterns
        if (currentActivity.includes('Using') || (currentActivity.includes('Agent') && currentActivity.includes('calling tools'))) {
            console.log('🔧 Tool activity detected:', currentActivity);
            this.toolActivities.add(currentActivity);
            if (!this.progressSteps[2].completed) {
                this.progressSteps[2].completed = true;
                this.progressSteps[2].timestamp = timestamp;
                this.progressSteps[2].name = `Tool Execution (${this.toolActivities.size} tools used)`;
                console.log('✅ Marked tool execution as completed');
            } else {
                this.progressSteps[2].name = `Tool Execution (${this.toolActivities.size} tools used)`;
            }
        }

        // Mark data processing when we have both agents and tools working
        if (this.agentActivities.size > 0 && this.toolActivities.size > 0) {
            if (!this.progressSteps[3].completed) {
                this.progressSteps[3].completed = true;
                this.progressSteps[3].timestamp = timestamp;
                console.log('✅ Marked data processing as completed (agents + tools active)');
            }
        }

        // Investigation completion is handled by formal status updates
        if (this.investigation?.status === 'completed') {
            this.progressSteps[4].completed = true;
            this.progressSteps[4].timestamp = this.investigation.completed_at || timestamp;
            console.log('✅ Marked investigation as completed');
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
                        // Cache UI summary for display (for messages) - keep as string since it's per-message
                        this.uiSummaryCache.set(event.investigation_id, event.ui_summary);

                        // Store the latest UI summary to attach to the next agent message
                        this.latestUiSummary = event.ui_summary;
                        this.latestUiSummaryTimestamp = event.timestamp;

                        console.log('🔄 Stored latest UI summary for next agent message:', event.ui_summary);

                        // Update investigation summary if this is an investigation-level summary
                        if (this.investigation && event.investigation_id === this.investigationId) {
                            console.log('🔄 Updating investigation UI summary via SSE:', event.ui_summary);

                            // Initialize ui_summary as array if it doesn't exist
                            if (!this.investigation.ui_summary) {
                                this.investigation.ui_summary = [];
                            }

                            // Append new summary to the list (event.ui_summary is a string from SSE)
                            this.investigation.ui_summary.push({
                                summary: event.ui_summary, // This is a string
                                full_content: event.full_content || event.ui_summary,
                                timestamp: new Date().toISOString()
                            });

                            // Trigger recomputation of visible messages to include updated summary
                            this.chatMessagesSubject.next(this.chatMessagesSubject.value);

                            this.cdr.markForCheck(); // Trigger change detection
                        }
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

                case 'progress_update':
                    console.log('🔄 Progress update received:', event.current_activity);
                    // Update current activity display using BehaviorSubject
                    if (event.current_activity) {
                        this.currentActivitySubject.next(event.current_activity);
                        this.updateDynamicProgressSteps(event.current_activity);
                    }
                    // Update formal status if provided
                    if (this.investigation && event.formal_status) {
                        this.investigation.status = event.formal_status as InvestigationStatus;
                        this.updateProgressSteps();
                    }
                    this.cdr.markForCheck(); // Trigger change detection
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
                                sequence: ++this.messageSequenceCounter, // Assign sequence number for reliable ordering
                                // Attach the latest UI summary if available
                                ui_summary: this.latestUiSummary || undefined
                            }
                        };

                        // Clear the latest UI summary after attaching it
                        if (this.latestUiSummary) {
                            console.log('✅ Attached UI summary to agent message:', this.latestUiSummary);
                            this.latestUiSummary = null;
                            this.latestUiSummaryTimestamp = null;
                        }

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

    // Chat message filtering
    toggleAllThoughts(): void {
        const currentValue = this.showAllThoughtsSubject.value;
        this.showAllThoughtsSubject.next(!currentValue);
    }

    shouldShowMessage(message: AgentMessage): boolean {
        const showAllThoughts = this.showAllThoughtsSubject.value;
        if (showAllThoughts) {
            return true;
        }
        return message.message_type !== AgentMessageType.THINKING;
    }

    formatTimestamp(timestamp: string): string {
        return new Date(timestamp).toLocaleString();
    }

    // Tab management methods
    isTabActive(tab: 'messages' | 'summary'): boolean {
        return this.activeTab === tab;
    }

    setActiveTab(tab: 'messages' | 'summary'): void {
        this.activeTabSubject.next(tab);
    }

    getTabMessageCount(tab: 'messages' | 'summary'): number {
        const messages = this.chatMessagesSubject.value;

        switch (tab) {
            case 'summary':
                return messages.filter(msg => msg.metadata?.['is_investigation_summary']).length;
            case 'messages':
                return messages.filter(msg => !msg.metadata?.['is_investigation_summary']).length;
            default:
                return 0;
        }
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

    // Investigation summary helpers
    hasInvestigationSummary(): boolean {
        return !!(this.investigation?.ui_summary && this.investigation.ui_summary.length > 0);
    }

    shouldShowInvestigationSummaryPlaceholder(): boolean {
        return this.showUiSummaries &&
            this.investigation?.status === 'running' &&
            !this.hasInvestigationSummary();
    }

    getInvestigationSummary(): string | null {
        // Return the latest summary from the list
        if (this.investigation?.ui_summary && this.investigation.ui_summary.length > 0) {
            return this.investigation.ui_summary[this.investigation.ui_summary.length - 1].summary;
        }
        return null;
    }

    // Get parsed investigation summary
    getParsedInvestigationSummary(): ParsedSummary | null {
        const summary = this.getInvestigationSummary();
        return summary ? this.parseUiSummary(summary) : null;
    }

    // Parse structured summary from JSON string
    parseUiSummary(uiSummary: string): ParsedSummary | null {
        try {
            const parsed = JSON.parse(uiSummary);
            return {
                mainTheme: parsed.main_theme || 'Investigation Analysis',
                actionTaken: parsed.action_taken || 'Analysis completed',
                actionType: parsed.action_type || 'analysis',
                description: parsed.description_first_party || parsed.description || 'Processing completed',
                nextSteps: parsed.next_steps,
                keyEvents: parsed.description_events || []
            };
        } catch (error) {
            console.warn('Failed to parse UI summary:', error);
            return null;
        }
    }

    // Get action type icon
    getActionTypeIcon(actionType: string): string {
        const iconMap: { [key: string]: string } = {
            'analysis': 'fas fa-chart-line',
            'investigation': 'fas fa-search',
            'data_processing': 'fas fa-database',
            'reporting': 'fas fa-file-alt',
            'monitoring': 'fas fa-eye',
            'diagnosis': 'fas fa-stethoscope',
            'optimization': 'fas fa-cogs',
            'maintenance': 'fas fa-tools',
            'planning': 'fas fa-calendar-alt'
        };
        return iconMap[actionType] || 'fas fa-info-circle';
    }

    // Get action type color class
    getActionTypeColor(actionType: string): string {
        const colorMap: { [key: string]: string } = {
            'analysis': 'text-primary',
            'investigation': 'text-warning',
            'data_processing': 'text-info',
            'reporting': 'text-success',
            'monitoring': 'text-secondary',
            'diagnosis': 'text-danger',
            'optimization': 'text-purple',
            'maintenance': 'text-dark',
            'planning': 'text-indigo'
        };
        return colorMap[actionType] || 'text-muted';
    }

    // Check if message has structured summary
    hasStructuredSummary(message: AgentMessage): boolean {
        return !!(message.metadata?.['ui_summary'] && this.showUiSummaries);
    }

    // Create investigation summary message for chat history
    createInvestigationSummaryMessage(): AgentMessage | null {
        if (!this.investigation?.ui_summary || this.investigation.ui_summary.length === 0) return null;

        // Use the latest summary for the investigation message
        const latestSummary = this.investigation.ui_summary[this.investigation.ui_summary.length - 1];

        return {
            id: `investigation-summary-${this.investigation.id}`,
            investigation_id: this.investigationId,
            message_type: AgentMessageType.SYSTEM,
            content: latestSummary.summary,
            timestamp: this.investigation.updated_at,
            metadata: {
                sequence: -1, // Special sequence to ensure it appears first
                is_investigation_summary: true,
                summary_type: 'investigation_overview'
            },
            ui_summary: [{
                summary: latestSummary.summary,
                full_content: latestSummary.full_content,
                timestamp: latestSummary.timestamp
            }],
            ui_state: { is_summary: true },
            show_full_content: false
        };
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

    // Get parsed UI summary for agent messages
    getParsedMessageSummary(message: AgentMessage): ParsedSummary | null {
        const summary = message.metadata?.['ui_summary'];
        return summary ? this.parseUiSummary(summary) : null;
    }

    // Check if agent message has structured summary
    hasStructuredMessageSummary(message: AgentMessage): boolean {
        // Don't show structured summary if we're in full content mode
        if (message.metadata?.['display_mode'] === 'full_content') {
            return false;
        }

        // Always show structured summary if we're in summary mode
        if (message.metadata?.['display_mode'] === 'summary_only') {
            return !!(message.metadata?.['ui_summary']);
        }

        // Default behavior for other cases
        return this.showUiSummaries &&
            message.message_type === 'agent' &&
            !!(message.metadata?.['ui_summary']) &&
            !!this.getParsedMessageSummary(message);
    }
}

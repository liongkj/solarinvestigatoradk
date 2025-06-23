import { Injectable, NgZone } from '@angular/core';
import { HttpClient, HttpParams, HttpErrorResponse } from '@angular/common/http';
import { Observable, throwError, Subject, BehaviorSubject } from 'rxjs';
import { catchError, map } from 'rxjs/operators';
import { environment } from '../../environments/environment';
import {
    Investigation,
    InvestigationRequest,
    InvestigationResponse,
    InvestigationListResponse,
    ChatHistoryResponse,
    DecisionRequest,
    DecisionResponse,
    MessageRequest,
    HealthResponse,
    AgentMessage
} from '../models/investigation';

// SSE Event types
export interface SSEEvent {
    type: 'connected' | 'investigation_started' | 'message' | 'ui_update' | 'status_update' | 'progress_update' | 'completion' | 'workorder_status' | 'investigation_deleted' | 'heartbeat' | 'error' | 'status' |
    'streaming_text_chunk' | 'complete_text_message' | 'tool_call_request' | 'tool_result' | 'other_content' | 'state_artifact_update' | 'control_signal' | 'streaming_error';
    investigation_id: string;
    timestamp: string;
    event_id?: string;
    author?: string;
    content?: string;
    full_content?: string;  // Full accumulated content for streaming
    partial?: boolean;
    turn_complete?: boolean;
    tool_calls?: string[];
    tool_responses?: number;
    content_type?: string;
    has_state_delta?: boolean;
    has_artifact_delta?: boolean;
    message?: any;
    ui_summary?: string; // Keep as string for SSE events (individual summaries)
    status?: string;
    result?: string;
    error?: string;
    current_activity?: string;  // New field for descriptive activity status
    formal_status?: string;     // New field for formal investigation status
    chunk_info?: {  // Information about debounced chunks
        chunk_index: number;
        total_chunks: number;
        chunk_size: number;
    };
}

@Injectable({
    providedIn: 'root'
})
export class InvestigationService {
    private readonly baseUrl = `${environment.apiUrl}/investigations/`;

    // SSE event streams by investigation ID
    private sseStreams: Map<string, EventSource> = new Map();
    private eventSubjects: Map<string, Subject<SSEEvent>> = new Map();

    // Streaming text accumulator
    private streamingTextAccumulator: Map<string, BehaviorSubject<string>> = new Map();

    constructor(private http: HttpClient, private ngZone: NgZone) { }

    /**
     * Get list of all investigations with pagination
     */
    getInvestigations(page: number = 1, size: number = 10): Observable<InvestigationListResponse> {
        // Convert page/size to limit/offset for backend
        const offset = (page - 1) * size;
        const params = new HttpParams()
            .set('limit', size.toString())
            .set('offset', offset.toString());

        return this.http.get<Investigation[]>(this.baseUrl, { params })
            .pipe(
                map(investigations => ({
                    investigations: investigations,
                    total: investigations.length,
                    page: page,
                    size: size
                } as InvestigationListResponse)),
                catchError(this.handleError)
            );
    }

    /**
     * Start a new investigation
     */
    startInvestigation(request: InvestigationRequest): Observable<InvestigationResponse> {
        return this.http.post<InvestigationResponse>(this.baseUrl, request)
            .pipe(
                catchError(this.handleError)
            );
    }

    /**
     * Get specific investigation by ID
     */
    getInvestigation(id: string): Observable<Investigation> {
        return this.http.get<Investigation>(`${this.baseUrl}${id}`)
            .pipe(
                catchError(this.handleError)
            );
    }

    /**
     * Get chat history for an investigation
     */
    getChatHistory(id: string): Observable<ChatHistoryResponse> {
        return this.http.get<ChatHistoryResponse>(`${this.baseUrl}${id}/chat`)
            .pipe(
                catchError(this.handleError)
            );
    }

    /**
     * Send a decision for an investigation
     */
    sendDecision(id: string, decision: DecisionRequest): Observable<DecisionResponse> {
        return this.http.post<DecisionResponse>(`${this.baseUrl}${id}/decide`, decision)
            .pipe(
                catchError(this.handleError)
            );
    }

    /**
     * Send a message to the investigation agent
     */
    sendMessage(id: string, message: MessageRequest): Observable<AgentMessage> {
        return this.http.post<AgentMessage>(`${this.baseUrl}${id}/message`, message)
            .pipe(
                catchError(this.handleError)
            );
    }

    /**
     * Retry a failed investigation
     */
    retryInvestigation(id: string): Observable<InvestigationResponse> {
        return this.http.post<InvestigationResponse>(`${this.baseUrl}${id}/retry`, {})
            .pipe(
                catchError(this.handleError)
            );
    }

    /**
     * Delete an investigation by ID
     */
    deleteInvestigation(id: string): Observable<{ success: boolean, message: string }> {
        return this.http.delete<{ success: boolean, message: string }>(`${this.baseUrl}${id}`)
            .pipe(
                catchError(this.handleError)
            );
    }

    /**
     * Get service health status
     */
    getHealthStatus(): Observable<HealthResponse> {
        return this.http.get<HealthResponse>(`${this.baseUrl}health/service`)
            .pipe(
                catchError(this.handleError)
            );
    }

    /**
     * Handle HTTP errors
     */
    private handleError(error: HttpErrorResponse): Observable<never> {
        let errorMessage = 'An unknown error occurred';

        if (error.error instanceof ErrorEvent) {
            // Client-side or network error
            errorMessage = `Network error: ${error.error.message}`;
        } else {
            // Backend returned an unsuccessful response code
            if (error.status === 0) {
                errorMessage = 'Unable to connect to server. Please check if the backend is running.';
            } else if (error.status >= 400 && error.status < 500) {
                errorMessage = error.error?.detail || `Client error: ${error.status}`;
            } else if (error.status >= 500) {
                errorMessage = error.error?.detail || `Server error: ${error.status}`;
            } else {
                errorMessage = `HTTP error: ${error.status} - ${error.statusText}`;
            }
        }

        console.error('InvestigationService error:', error);
        return throwError(() => new Error(errorMessage));
    }

    /**
     * Get Server-Sent Events stream for an investigation
     */
    getSSEStream(investigationId: string): Observable<SSEEvent> {
        // Check if stream already exists
        if (this.eventSubjects.has(investigationId)) {
            return this.eventSubjects.get(investigationId)!.asObservable();
        }

        // Create a new Subject for the investigation ID
        const subject = new Subject<SSEEvent>();
        this.eventSubjects.set(investigationId, subject);

        // Create a new EventSource for the investigation ID
        const eventSource = new EventSource(`${this.baseUrl}${investigationId}/events`);

        eventSource.onmessage = (event) => {
            const data: SSEEvent = JSON.parse(event.data);
            subject.next(data);
        };

        eventSource.onerror = (error) => {
            console.error('SSE error:', error);
            subject.complete();
            this.eventSubjects.delete(investigationId);
        };

        // Store the EventSource instance
        this.sseStreams.set(investigationId, eventSource);

        return subject.asObservable();
    }

    /**
     * Start SSE stream for investigation updates
     */
    startInvestigationStream(investigationId: string): Observable<SSEEvent> {
        // Check if stream already exists
        if (this.eventSubjects.has(investigationId)) {
            return this.eventSubjects.get(investigationId)!.asObservable();
        }

        // Create new event subject
        const eventSubject = new Subject<SSEEvent>();
        this.eventSubjects.set(investigationId, eventSubject);

        // Create SSE connection
        const eventSource = new EventSource(`${this.baseUrl}${investigationId}/stream`);
        this.sseStreams.set(investigationId, eventSource);

        // Handle SSE events - ensure they run inside Angular's zone
        eventSource.onmessage = (event) => {
            this.ngZone.run(() => {
                try {
                    const data: SSEEvent = JSON.parse(event.data);
                    console.log('🌐 SSE Event parsed in service (in zone):', data);

                    // Process streaming events for text accumulation
                    this.processStreamingEvent(data);

                    eventSubject.next(data);
                } catch (error) {
                    console.error('Error parsing SSE event:', error);
                }
            });
        };

        eventSource.onerror = (error) => {
            this.ngZone.run(() => {
                console.error('SSE connection error:', error);
                eventSubject.error(error);
                this.stopInvestigationStream(investigationId);
            });
        };

        return eventSubject.asObservable();
    }

    /**
     * Stop SSE stream for investigation
     */
    stopInvestigationStream(investigationId: string): void {
        // Close EventSource
        const eventSource = this.sseStreams.get(investigationId);
        if (eventSource) {
            eventSource.close();
            this.sseStreams.delete(investigationId);
        }

        // Complete and remove subject
        const eventSubject = this.eventSubjects.get(investigationId);
        if (eventSubject) {
            eventSubject.complete();
            this.eventSubjects.delete(investigationId);
        }

        // Reset streaming text accumulator
        this.resetStreamingText(investigationId);
    }

    /**
     * Stop all SSE streams (cleanup)
     */
    stopAllStreams(): void {
        for (const investigationId of this.sseStreams.keys()) {
            this.stopInvestigationStream(investigationId);
        }
    }

    /**
     * Create workorder manually
     */
    createWorkorder(investigationId: string, workorderData: any): Observable<any> {
        return this.http.post(`${this.baseUrl}${investigationId}/workorders`, workorderData)
            .pipe(catchError(this.handleError));
    }

    /**
     * Get workorders for investigation
     */
    getWorkorders(investigationId: string): Observable<any[]> {
        return this.http.get<any[]>(`${this.baseUrl}${investigationId}/workorders`)
            .pipe(catchError(this.handleError));
    }

    /**
     * Get streaming text accumulator for an investigation
     */
    getStreamingText(investigationId: string): Observable<string> {
        if (!this.streamingTextAccumulator.has(investigationId)) {
            this.streamingTextAccumulator.set(investigationId, new BehaviorSubject<string>(''));
        }
        return this.streamingTextAccumulator.get(investigationId)!.asObservable();
    }

    /**
     * Reset streaming text accumulator for an investigation
     */
    resetStreamingText(investigationId: string): void {
        if (this.streamingTextAccumulator.has(investigationId)) {
            this.streamingTextAccumulator.get(investigationId)!.next('');
        }
    }

    /**
     * Process streaming events and accumulate text chunks
     */
    private processStreamingEvent(event: SSEEvent): void {
        if (event.type === 'streaming_text_chunk' && event.content) {
            // Initialize accumulator if not exists
            if (!this.streamingTextAccumulator.has(event.investigation_id)) {
                this.streamingTextAccumulator.set(event.investigation_id, new BehaviorSubject<string>(''));
            }

            // Use the full_content from backend (which handles proper accumulation)
            const textToUse = event.full_content ||
                (this.streamingTextAccumulator.get(event.investigation_id)!.getValue() + event.content);

            this.streamingTextAccumulator.get(event.investigation_id)!.next(textToUse);

            console.log('📝 Streaming chunk processed:', {
                chunk: event.content?.substring(0, 20) + '...',
                chunkSize: event.content?.length || 0,
                fullLength: textToUse.length,
                chunkInfo: event.chunk_info ?
                    `${event.chunk_info.chunk_index}/${event.chunk_info.total_chunks}` : 'N/A'
            });

        } else if (event.type === 'complete_text_message' && !event.partial) {
            // Final complete message - set the final content
            if (!this.streamingTextAccumulator.has(event.investigation_id)) {
                this.streamingTextAccumulator.set(event.investigation_id, new BehaviorSubject<string>(''));
            }

            if (event.content) {
                this.streamingTextAccumulator.get(event.investigation_id)!.next(event.content);
                console.log('✅ Complete message set:', {
                    contentLength: event.content.length,
                    preview: event.content.substring(0, 100) + '...'
                });
            }
        }
    }
}

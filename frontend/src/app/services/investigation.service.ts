import { Injectable } from '@angular/core';
import { HttpClient, HttpParams, HttpErrorResponse } from '@angular/common/http';
import { Observable, throwError, Subject, BehaviorSubject } from 'rxjs';
import { catchError, map } from 'rxjs/operators';
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
    type: 'message' | 'ui_update' | 'status_update' | 'workorder_status';
    investigation_id: string;
    timestamp: string;
    message?: any;
    ui_summary?: string;
    full_content?: string;
    status?: string;
}

@Injectable({
    providedIn: 'root'
})
export class InvestigationService {
    private readonly baseUrl = 'http://localhost:8000/api/investigations/';

    // SSE event streams by investigation ID
    private sseStreams: Map<string, EventSource> = new Map();
    private eventSubjects: Map<string, Subject<SSEEvent>> = new Map();

    constructor(private http: HttpClient) { }

    /**
     * Get list of all investigations with pagination
     */
    getInvestigations(page: number = 1, size: number = 10): Observable<InvestigationListResponse> {
        const params = new HttpParams()
            .set('page', page.toString())
            .set('size', size.toString());

        return this.http.get<InvestigationListResponse>(this.baseUrl, { params })
            .pipe(
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

        // Handle SSE events
        eventSource.onmessage = (event) => {
            try {
                const data: SSEEvent = JSON.parse(event.data);
                eventSubject.next(data);
            } catch (error) {
                console.error('Error parsing SSE event:', error);
            }
        };

        eventSource.onerror = (error) => {
            console.error('SSE connection error:', error);
            eventSubject.error(error);
            this.stopInvestigationStream(investigationId);
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
}

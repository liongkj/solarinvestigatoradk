import { Injectable } from '@angular/core';
import { HttpClient, HttpParams, HttpErrorResponse } from '@angular/common/http';
import { Observable, throwError } from 'rxjs';
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

@Injectable({
    providedIn: 'root'
})
export class InvestigationService {
    private readonly baseUrl = 'http://localhost:8000/api/investigations/';

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
}

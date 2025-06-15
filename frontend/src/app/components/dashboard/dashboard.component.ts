import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { NgbModal, NgbModalModule, NgbDate, NgbCalendar, NgbDateParserFormatter, NgbDatepickerModule } from '@ng-bootstrap/ng-bootstrap';
import { interval, Subscription, forkJoin, combineLatest, BehaviorSubject } from 'rxjs';
import { takeUntil, switchMap, tap, catchError, finalize, take } from 'rxjs/operators';
import { Subject, of } from 'rxjs';
import { InvestigationService } from '../../services/investigation.service';
import { PlantService } from '../../services/plant.service';
import { Plant } from '../../models/plant';
import {
    Investigation,
    InvestigationRequest,
    InvestigationStatus,
    AgentMessage,
    AgentMessageType,
    DecisionRequest
} from '../../models/investigation';

// Legacy interfaces for other tabs (to be updated later)
export interface Project {
    id: string;
    name: string;
    address: string;
    customer: string;
    status: string;
    createdAt: Date;
    type: string;
}

export interface WorkOrder {
    id: string;
    projectId: string;
    title: string;
    description: string;
    tasks: string[];
    timeline: string;
    status: string;
    createdAt: Date;
}

@Component({
    selector: 'app-dashboard',
    standalone: true,
    imports: [CommonModule, FormsModule, NgbModalModule, NgbDatepickerModule],
    templateUrl: './dashboard.component.html',
    styleUrls: ['./dashboard.component.css']
})
export class DashboardComponent implements OnInit, OnDestroy {
    activeTab: 'investigations' | 'workorders' | 'projects' = 'investigations';
    isLoading = false;
    error: string | null = null;

    // Data arrays
    investigations: Investigation[] = [];
    projects: Project[] = [];
    workOrders: WorkOrder[] = [];
    plants$: BehaviorSubject<Plant[]> = new BehaviorSubject<Plant[]>([]);
    plants: Plant[] = [];
    modalPlants: Plant[] = []; // Dedicated plants array for modal
    // Selected investigation for chat view
    selectedInvestigation: Investigation | null = null;
    chatMessages: AgentMessage[] = [];

    // New investigation form
    newInvestigationForm = {
        plant_id: '',
        start_date: null as NgbDate | null,
        end_date: null as NgbDate | null,
        additional_notes: ''
    };

    // Auto-refresh subscription for chat updates
    private refreshSubscription: Subscription | null = null;
    private destroy$ = new Subject<void>();

    constructor(
        private investigationService: InvestigationService,
        private plantService: PlantService,
        private modalService: NgbModal,
        private calendar: NgbCalendar,
        private formatter: NgbDateParserFormatter,
        private router: Router
    ) {
        // this.loadPlants();
    }

    ngOnInit(): void {
        console.log('=== Dashboard ngOnInit started ===');
        this.loadDashboardData();
        // Set up auto-refresh for selected investigation chat
        this.startChatRefresh();

        console.log('Loading plants in ngOnInit...');
        this.plantService.getPlants().subscribe({
            next: (plants) => {
                console.log('Plants loaded in ngOnInit:', plants);
                console.log('Plants count:', plants?.length || 0);
                this.plants$.next(plants);
                this.plants = plants;
                this.modalPlants = plants;
            },
            error: (error) => {
                console.error('Error loading plants in ngOnInit:', error);
                this.error = 'Failed to load plants';
            }
        });
    }

    ngOnDestroy(): void {
        this.destroy$.next();
        this.destroy$.complete();
        this.stopChatRefresh();
    }

    setActiveTab(tab: 'investigations' | 'workorders' | 'projects') {
        this.activeTab = tab;
    }

    loadDashboardData() {
        this.isLoading = true;
        this.error = null;

        forkJoin({
            investigations: this.loadInvestigations(),
            projects: this.loadProjects(),
            workOrders: this.loadWorkOrders()
        }).pipe(
            takeUntil(this.destroy$),
            catchError(error => {
                this.error = 'Failed to load dashboard data';
                console.error('Error loading dashboard data:', error);
                return of(null);
            }),
            finalize(() => {
                this.isLoading = false;
            })
        ).subscribe();
    }

    private loadInvestigations() {
        return this.investigationService.getInvestigations(1, 50).pipe(
            tap(response => {
                this.investigations = response?.investigations || [];
            }),
            catchError(error => {
                console.error('Error loading investigations:', error);
                throw error;
            })
        );
    }
    trackByInvestigationId(index: number, investigation: Investigation): any {
        return investigation.id;
    }

    private loadProjects() {
        // TODO: implement API call for projects
        this.projects = [];
        return of([]);
    }

    private loadWorkOrders() {
        // TODO: implement API call for work orders
        this.workOrders = [];
        return of([]);
    }

    startNewInvestigation() {
        if (!this.newInvestigationForm.plant_id || !this.newInvestigationForm.start_date || !this.newInvestigationForm.end_date) {
            this.error = 'Please select a plant and date range';
            return;
        }

        // Validate date range (max 5 days)
        const daysDiff = this.calculateDaysBetween(this.newInvestigationForm.start_date, this.newInvestigationForm.end_date);
        if (daysDiff > 5) {
            this.error = 'Date range cannot exceed 5 days';
            return;
        }

        if (daysDiff < 0) {
            this.error = 'End date must be after start date';
            return;
        }

        this.isLoading = true;
        this.error = null;

        const request: InvestigationRequest = {
            plant_id: this.newInvestigationForm.plant_id,
            start_date: this.formatDateToISO(this.newInvestigationForm.start_date),
            end_date: this.formatDateToISO(this.newInvestigationForm.end_date),
            additional_notes: this.newInvestigationForm.additional_notes || undefined
        };

        this.investigationService.startInvestigation(request).pipe(
            takeUntil(this.destroy$),
            tap(response => {
                if (response) {
                    // Add plant name to investigation for display
                    const plant = this.plants.find(p => p.plant_id === response.investigation.plant_id);
                    if (plant) {
                        response.investigation.plant_name = plant.plant_name;
                    }

                    // Add to investigations list and select it
                    this.investigations.unshift(response.investigation);
                    this.selectedInvestigation = response.investigation;

                    // Reset form
                    this.newInvestigationForm = {
                        plant_id: '',
                        start_date: null,
                        end_date: null,
                        additional_notes: ''
                    };

                    // Load chat messages for the new investigation
                    this.loadChatMessages();
                }
            }),
            catchError(error => {
                this.error = error.message || 'Failed to start new investigation';
                console.error('Error starting investigation:', error);
                return of(null);
            }),
            finalize(() => {
                this.isLoading = false;
            })
        ).subscribe();
    }

    selectInvestigation(investigation: Investigation) {
        console.log('=== selectInvestigation called ===');
        console.log('Investigation object:', investigation);
        console.log('Investigation ID:', investigation.id);

        if (!investigation || !investigation.id) {
            console.error('Invalid investigation object or missing ID');
            return;
        }

        try {
            console.log('Attempting navigation to:', `/investigation/${investigation.id}`);
            this.router.navigate(['/investigation', investigation.id]).then(
                (success) => {
                    console.log('Navigation successful:', success);
                },
                (error) => {
                    console.error('Navigation failed:', error);
                }
            );
        } catch (error) {
            console.error('Error during navigation:', error);
        }
    }

    private loadChatMessages() {
        if (!this.selectedInvestigation) return;

        this.investigationService.getChatHistory(this.selectedInvestigation.id).pipe(
            takeUntil(this.destroy$),
            tap(response => {
                this.chatMessages = response?.messages || [];
            }),
            catchError(error => {
                console.error('Error loading chat messages:', error);
                return of(null);
            })
        ).subscribe();
    }

    private startChatRefresh() {
        if (!this.selectedInvestigation) return;

        // Refresh chat every 3 seconds for real-time updates
        this.refreshSubscription = interval(3000).pipe(
            takeUntil(this.destroy$),
            switchMap(() => {
                if (this.selectedInvestigation) {
                    return forkJoin({
                        chat: this.investigationService.getChatHistory(this.selectedInvestigation.id),
                        investigation: this.investigationService.getInvestigation(this.selectedInvestigation.id)
                    });
                }
                return of(null);
            })
        ).subscribe({
            next: (result) => {
                if (result) {
                    // Update chat messages
                    this.chatMessages = result.chat?.messages || [];

                    // Update investigation status
                    if (result.investigation) {
                        const index = this.investigations.findIndex(inv => inv.id === result.investigation!.id);
                        if (index >= 0) {
                            this.investigations[index] = result.investigation;
                        }
                        this.selectedInvestigation = result.investigation;
                    }
                }
            },
            error: (error) => {
                console.error('Error in chat refresh:', error);
            }
        });
    }

    public stopChatRefresh() {
        if (this.refreshSubscription) {
            this.refreshSubscription.unsubscribe();
            this.refreshSubscription = null;
        }
    }

    refresh() {
        this.loadDashboardData();
        if (this.selectedInvestigation) {
            this.loadChatMessages();
        }
    }

    getStatusColor(status: string): string {
        switch (status) {
            case InvestigationStatus.RUNNING:
                return 'bg-primary text-white';
            case InvestigationStatus.COMPLETED:
                return 'bg-success text-white';
            case InvestigationStatus.FAILED:
                return 'bg-danger text-white';
            case InvestigationStatus.PENDING:
                return 'bg-warning text-dark';
            case InvestigationStatus.CANCELLED:
                return 'bg-secondary text-white';
            default:
                return 'bg-secondary text-white';
        }
    }

    formatDate(dateString: string): string {
        const date = new Date(dateString);
        return new Intl.DateTimeFormat('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        }).format(date);
    }

    getInvestigationTitle(investigation: Investigation): string {
        const plantName = investigation.plant_name || `Plant ${investigation.plant_id.substring(0, 8)}`;
        const dateRange = `${this.formatDateToDisplay(investigation.start_date)} - ${this.formatDateToDisplay(investigation.end_date)}`;
        return `${plantName} (${dateRange})`;
    }

    getMessageAuthor(message: AgentMessage): string {
        switch (message.message_type) {
            case AgentMessageType.SYSTEM:
                return 'System';
            case AgentMessageType.USER:
                return 'User';
            case AgentMessageType.AGENT:
                return message.metadata?.['agent_name'] || 'Agent';
            case AgentMessageType.TOOL_CALL:
                return 'Tool Call';
            case AgentMessageType.TOOL_RESULT:
                return 'Tool Result';
            default:
                return 'Unknown';
        }
    }

    isInvestigationActive(investigation: Investigation): boolean {
        return investigation.status === InvestigationStatus.RUNNING ||
            investigation.status === InvestigationStatus.PENDING;
    }

    makeDecision(decision: string, decisionType: string = 'continue') {
        if (!this.selectedInvestigation) return;

        this.isLoading = true;
        this.error = null;

        const request: DecisionRequest = {
            decision: decision,
            decision_type: decisionType
        };

        this.investigationService.sendDecision(
            this.selectedInvestigation.id,
            request
        ).pipe(
            takeUntil(this.destroy$),
            switchMap(response => {
                if (response) {
                    // Refresh the investigation and chat
                    return forkJoin({
                        investigation: this.investigationService.getInvestigation(this.selectedInvestigation!.id),
                        chat: this.investigationService.getChatHistory(this.selectedInvestigation!.id)
                    });
                }
                return of(null);
            }),
            tap(result => {
                if (result) {
                    // Update investigation status
                    if (result.investigation) {
                        const index = this.investigations.findIndex(inv => inv.id === result.investigation!.id);
                        if (index >= 0) {
                            this.investigations[index] = result.investigation;
                        }
                        this.selectedInvestigation = result.investigation;
                    }
                    // Update chat messages
                    this.chatMessages = result.chat?.messages || [];
                }
            }),
            catchError(error => {
                this.error = error.message || 'Failed to submit decision';
                console.error('Error making decision:', error);
                return of(null);
            }),
            finalize(() => {
                this.isLoading = false;
            })
        ).subscribe();
    }

    openNewInvestigationModal(content: any) {
        console.log('=== Opening new investigation modal ===');
        console.log('Current plants array length:', this.plants.length);
        console.log('Current modalPlants array length:', this.modalPlants.length);

        // Ensure plants are loaded before opening modal
        if (this.plants.length === 0) {
            console.log('Plants array is empty, loading plants...');
            this.plantService.getPlants().subscribe({
                next: (plants) => {
                    console.log('Plants loaded for modal:', plants);
                    console.log('Plants count from API:', plants?.length || 0);
                    this.plants$.next(plants);
                    this.plants = plants;
                    this.modalPlants = plants;
                    console.log('modalPlants after assignment:', this.modalPlants);
                    console.log('Opening modal now...');

                    // Open modal - ng-template will use component's plants array
                    this.modalService.open(content, { size: 'lg' });
                },
                error: (error) => {
                    console.error('Error loading plants for modal:', error);
                    this.error = 'Failed to load plants';
                    // Still open modal even if plants fail to load
                    console.log('Opening modal despite error...');
                    this.modalService.open(content, { size: 'lg' });
                }
            });
        } else {
            console.log('Using existing plants:', this.plants);
            this.modalPlants = this.plants;
            console.log('modalPlants after assignment (existing):', this.modalPlants);
            console.log('Opening modal with existing plants...');
            // Open modal - ng-template will use component's plants array
            this.modalService.open(content, { size: 'lg' });
        }
    }

    // Plant management methods
    // private loadPlants() {
    //     this.plants$ = this.plantService.getPlants().pipe(
    //         take(1),
    //         tap(plants => {
    //             this.plants$.next(plants);
    //         }),
    //         catchError(error => {
    //             console.error('Error loading plants:', error);
    //             this.error = 'Failed to load plants';
    //             return of([]);
    //         })
    //     ).subscribe();
    // }

    // Date helper methods
    calculateDaysBetween(startDate: NgbDate, endDate: NgbDate): number {
        const start = new Date(startDate.year, startDate.month - 1, startDate.day);
        const end = new Date(endDate.year, endDate.month - 1, endDate.day);
        const diffTime = end.getTime() - start.getTime();
        return Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    }

    formatDateToISO(date: NgbDate): string {
        const month = date.month.toString().padStart(2, '0');
        const day = date.day.toString().padStart(2, '0');
        return `${date.year}-${month}-${day}`; // YYYY-MM-DD format
    }

    formatDateToDisplay(dateStr: string): string {
        const date = new Date(dateStr);
        return date.toLocaleDateString('en-GB'); // dd/mm/yyyy format
    }

    onDateChange() {
        // Auto-validate date range when dates change
        if (this.newInvestigationForm.start_date && this.newInvestigationForm.end_date) {
            const daysDiff = this.calculateDaysBetween(
                this.newInvestigationForm.start_date,
                this.newInvestigationForm.end_date
            );

            if (daysDiff > 5) {
                this.error = 'Date range cannot exceed 5 days';
            } else if (daysDiff < 0) {
                this.error = 'End date must be after start date';
            } else {
                this.error = null;
            }
        }
    }
}

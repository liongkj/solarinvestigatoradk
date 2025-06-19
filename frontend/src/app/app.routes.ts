import { Routes } from '@angular/router';
import { DashboardComponent } from './components/dashboard/dashboard.component';
import { InvestigationDetailComponent } from './components/investigation-detail/investigation-detail-sse.component';

export const routes: Routes = [
    { path: '', component: DashboardComponent },
    { path: 'dashboard', component: DashboardComponent },
    { path: 'investigation/:id', component: InvestigationDetailComponent },
    { path: '**', redirectTo: '' }
];

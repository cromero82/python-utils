import { Routes } from '@angular/router';
import { DashboardComponent } from './pages/dashboard/dashboard.component';
import { TranscriberComponent } from './pages/transcriber/transcriber.component';

export const routes: Routes = [
  { path: '', component: DashboardComponent },
  { path: 'transcriber', component: TranscriberComponent },
];

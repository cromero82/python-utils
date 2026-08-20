import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { ApiService, App } from '../../services/api.service';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule],
  template: `
    <h2 style="margin-bottom: 16px;">Apps Disponibles</h2>
    <div *ngFor="let app of apps" class="card" (click)="openApp(app.id)">
      <h3>{{ app.name }}</h3>
      <p style="color: #666; margin-top: 8px;">{{ app.description }}</p>
    </div>
  `,
})
export class DashboardComponent implements OnInit {
  apps: App[] = [];

  constructor(private api: ApiService, private router: Router) {}

  ngOnInit() {
    this.api.getApps().subscribe((res) => {
      this.apps = res.apps;
    });
  }

  openApp(id: string) {
    if (id === 'mov-transcriber') {
      this.router.navigate(['/transcriber']);
    }
  }
}

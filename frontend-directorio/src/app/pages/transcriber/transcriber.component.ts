import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../services/api.service';

@Component({
  selector: 'app-transcriber',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div style="margin-bottom: 16px;">
      <a href="/" style="color: #1976d2; text-decoration: none;">← Volver al directorio</a>
    </div>

    <div class="card">
      <h2 style="margin-bottom: 16px;">Transcriptor de Video</h2>

      <div style="margin-bottom: 16px;">
        <label style="display: block; margin-bottom: 8px; font-weight: 500;">Archivo .mov</label>
        <input type="file" accept=".mov,.mp4,.avi,.mkv" (change)="onFileSelected($event)"
          style="padding: 8px; border: 1px solid #ddd; border-radius: 6px; width: 100%;" />
      </div>

      <div style="display: flex; gap: 16px; margin-bottom: 16px;">
        <div style="flex: 1;">
          <label style="display: block; margin-bottom: 8px; font-weight: 500;">Modelo</label>
          <select [(ngModel)]="selectedModel"
            style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 6px;">
            <option value="tiny">Tiny (rapido)</option>
            <option value="base">Base (balance)</option>
            <option value="small">Small (preciso)</option>
            <option value="medium">Medium (muy preciso)</option>
          </select>
        </div>
        <div style="flex: 1;">
          <label style="display: block; margin-bottom: 8px; font-weight: 500;">Idioma</label>
          <select [(ngModel)]="selectedLanguage"
            style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 6px;">
            <option value="es">Espanol</option>
            <option value="en">Ingles</option>
            <option value="auto">Auto-detectar</option>
          </select>
        </div>
      </div>

      <button class="btn btn-primary" (click)="startTranscription()" [disabled]="!selectedFile || isProcessing">
        {{ isProcessing ? 'Procesando...' : 'Transcribir' }}
      </button>
    </div>

    <div class="card" *ngIf="taskId">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
        <h3>Progreso</h3>
        <span class="status-badge" [ngClass]="'status-' + status">{{ status | uppercase }}</span>
      </div>
      <p style="color: #666; margin-bottom: 8px;">{{ selectedFile?.name }} · {{ selectedModel }} · {{ selectedLanguage }}</p>
      <div class="progress-bar">
        <div class="progress-fill" [style.width.%]="progress"></div>
      </div>
      <p style="text-align: right; color: #666; font-size: 14px;">{{ progress }}%</p>
      <p *ngIf="status === 'processing' && statusMessage" style="color: #666; margin-top: 8px; font-size: 14px;">
        {{ statusMessage }}
      </p>
      <p *ngIf="status === 'error' && errorMessage" style="color: #c62828; margin-top: 8px; font-size: 14px;">
        {{ errorMessage }}
      </p>
    </div>

    <div class="card" *ngIf="transcriptionText">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
        <h3>Resultado</h3>
        <button class="btn btn-secondary" (click)="copyToClipboard()">Copiar al portapapeles</button>
      </div>
      <textarea [(ngModel)]="transcriptionText" readonly></textarea>
      <p *ngIf="copied" style="color: #2e7d32; margin-top: 8px; font-size: 14px;">Copiado!</p>
    </div>
  `,
})
export class TranscriberComponent {
  selectedFile: File | null = null;
  selectedModel = 'base';
  selectedLanguage = 'en';
  isProcessing = false;
  taskId: string | null = null;
  status = '';
  progress = 0;
  statusMessage = '';
  errorMessage = '';
  transcriptionText = '';
  copied = false;

  constructor(private api: ApiService) {}

  onFileSelected(event: Event) {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      this.selectedFile = input.files[0];
    }
  }

  startTranscription() {
    if (!this.selectedFile) return;

    this.isProcessing = true;
    this.transcriptionText = '';
    this.copied = false;
    this.status = 'processing';
    this.progress = 0;
    this.statusMessage = '';
    this.errorMessage = '';

    this.api.startTranscription(this.selectedFile, this.selectedModel, this.selectedLanguage).subscribe({
      next: (res) => {
        this.taskId = res.task_id;
        this.pollStatus();
      },
      error: (err) => {
        this.isProcessing = false;
        this.status = 'error';
        this.errorMessage = err?.error?.detail || err?.message || 'No se pudo iniciar la transcripción';
      },
    });
  }

  pollStatus() {
    if (!this.taskId) return;

    const interval = setInterval(() => {
      this.api.getTranscriptionStatus(this.taskId!).subscribe({
        next: (res) => {
          this.status = res.status;
          this.progress = res.progress;
          this.statusMessage = res.message || '';
          this.errorMessage = res.error || '';

          if (res.status === 'completed') {
            clearInterval(interval);
            this.transcriptionText = res.result || '';
            this.isProcessing = false;
          } else if (res.status === 'error') {
            clearInterval(interval);
            this.isProcessing = false;
          }
        },
        error: () => {
          clearInterval(interval);
          this.isProcessing = false;
          this.status = 'error';
          this.errorMessage = 'Se perdió la conexión con el servidor o la tarea ya no existe.';
        },
      });
    }, 500);
  }

  copyToClipboard() {
    navigator.clipboard.writeText(this.transcriptionText).then(() => {
      this.copied = true;
      setTimeout(() => (this.copied = false), 2000);
    });
  }
}

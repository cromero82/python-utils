import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface App {
  id: string;
  name: string;
  description: string;
  icon: string;
}

export interface TaskStatus {
  id: string;
  status: string;
  progress: number;
  filename: string;
  result: string | null;
  error: string | null;
}

@Injectable({
  providedIn: 'root',
})
export class ApiService {
  private apiUrl = 'http://localhost:8080/api';

  constructor(private http: HttpClient) {}

  getApps(): Observable<{ apps: App[] }> {
    return this.http.get<{ apps: App[] }>(`${this.apiUrl}/apps`);
  }

  startTranscription(file: File, model: string, language: string): Observable<{ task_id: string }> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('model', model);
    formData.append('language', language);
    return this.http.post<{ task_id: string }>(`${this.apiUrl}/transcribe`, formData);
  }

  getTranscriptionStatus(taskId: string): Observable<TaskStatus> {
    return this.http.get<TaskStatus>(`${this.apiUrl}/transcribe/${taskId}/status`);
  }

  getTranscriptionResult(taskId: string): Observable<{ status: string; text: string | null }> {
    return this.http.get<{ status: string; text: string | null }>(`${this.apiUrl}/transcribe/${taskId}/result`);
  }
}

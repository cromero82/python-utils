import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet],
  template: `
    <div class="container">
      <div class="header">
        <h1>Directorio de Apps</h1>
      </div>
      <router-outlet></router-outlet>
    </div>
  `,
})
export class AppComponent {}

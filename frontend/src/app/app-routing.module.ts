import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';

import { AppComponent } from './app.component';
import { IndexComponent } from './components/index/index.component';
import { ConstructorComponent } from './components/constructor/constructor.component';
import { DeconstructorComponent } from './components/deconstructor/deconstructor.component';
import { DemonstratorComponent } from './components/demonstrator/demonstrator.component';
import { MapComponent } from './components/map/map.component';

const routes: Routes = [
  { path: '', component: IndexComponent },
  { path: 'constructor', component: ConstructorComponent },
  { path: 'deconstructor', component: DeconstructorComponent },
  { path: 'demonstrator', component: DemonstratorComponent },
  { path: 'map', component: MapComponent },
  { path: '**', redirectTo: '' }
];

export default routes;

@NgModule({
  imports: [RouterModule.forRoot(routes)],
  exports: [RouterModule]
})
export class AppRoutingModule { }




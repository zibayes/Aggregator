import { BrowserModule } from '@angular/platform-browser';
import { NgModule } from '@angular/core';
import { HttpClientModule } from '@angular/common/http';

import { AngularAPI } from './angular-api.service';
import { AppComponent } from './app.component';
import { IndexComponent } from './components/index/index.component';
import { ConstructorComponent } from './components/constructor/constructor.component';
import { DeconstructorComponent } from './components/deconstructor/deconstructor.component';
import { DemonstratorComponent } from './components/demonstrator/demonstrator.component';
import { MapComponent } from './components/map/map.component';
import { AppRoutingModule } from './app-routing.module';

@NgModule({
  declarations: [
    AppComponent,
	IndexComponent,
	ConstructorComponent,
	DeconstructorComponent,
	DemonstratorComponent,
	MapComponent
  ],
  imports: [
    BrowserModule,
    HttpClientModule,
	AppRoutingModule
  ],
  providers: [AngularAPI],
  bootstrap: [AppComponent]
})
export class AppModule { }
import { Component, OnInit } from '@angular/core';
import { AngularAPI } from './angular-api.service';
import { Item } from './item';
import {NgFor} from "@angular/common";
import { RouterModule } from '@angular/router';
import { HttpClientModule } from '@angular/common/http';

@Component({
    selector: 'app-root',
	standalone: true,
	imports: [RouterModule, NgFor, HttpClientModule],
    templateUrl: "./index.html",
    styles: []
})
export class AppComponent implements OnInit {
	title = 'Archeaology arggregator';
  items: Item[] = [];

  constructor(private angularAPI: AngularAPI) {}

  ngOnInit() {
    this.angularAPI.getItems().subscribe((data) => {
      this.items = data;
    });
  }
}

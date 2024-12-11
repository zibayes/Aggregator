import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { Item } from './item';

@Injectable({
  providedIn: 'root'
})
export class AngularAPI {
  private apiUrl = 'http://127.0.0.1:8000/api/items/';  // Укажите URL вашего API

  constructor(private http: HttpClient) { }

  getItems(): Observable<Item[]> {
	return this.http.get<Item[]>(this.apiUrl);
  }
}
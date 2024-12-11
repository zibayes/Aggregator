import { TestBed } from '@angular/core/testing';

import { AngularApiService } from './angular-api.service';

describe('AngularApiService', () => {
  let service: AngularApiService;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(AngularApiService);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });
});

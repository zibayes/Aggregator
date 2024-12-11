import { ComponentFixture, TestBed } from '@angular/core/testing';

import { DeconstructorComponent } from './deconstructor.component';

describe('DeconstructorComponent', () => {
  let component: DeconstructorComponent;
  let fixture: ComponentFixture<DeconstructorComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [DeconstructorComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(DeconstructorComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});

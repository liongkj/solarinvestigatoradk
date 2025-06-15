import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { tap, catchError, map } from 'rxjs/operators';
import { Plant } from '../models/plant';

// Interface for the API response
interface PlantsResponse {
    plants: Plant[];
    total: number;
}

@Injectable({
    providedIn: 'root'
})
export class PlantService {
    private readonly baseUrl = 'http://localhost:8000/api/plants/';

    constructor(private http: HttpClient) { }

    /**
     * Get list of all plants
     * TODO: implement this when backend endpoint is ready
     */
    getPlants(): Observable<Plant[]> {
        console.log('=== PlantService.getPlants() called ===');
        console.log('Making HTTP GET request to:', this.baseUrl);

        return this.http.get<PlantsResponse>(this.baseUrl).pipe(
            tap((response: PlantsResponse) => {
                console.log('Response received from API:', response);
                console.log('Plants array from response:', response.plants);
                console.log('Plants count:', response.plants?.length || 0);
                console.log('First plant (if any):', response.plants?.[0]);
            }),
            map((response: PlantsResponse) => {
                console.log('Extracting plants array from response...');
                return response.plants || [];
            }),
            catchError((error: any) => {
                console.error('HTTP error in getPlants:', error);
                console.error('Error status:', error.status);
                console.error('Error message:', error.message);
                throw error;
            })
        );

        const dummyPlants: Plant[] = [
            {
                plant_id: '550e8400-e29b-41d4-a716-446655440001',
                plant_name: 'Solar Farm Alpha',
                type: 'FiT'
            },
            {
                plant_id: '550e8400-e29b-41d4-a716-446655440002',
                plant_name: 'Residential Complex Beta',
                type: 'Zero Export'
            },
            {
                plant_id: '550e8400-e29b-41d4-a716-446655440003',
                plant_name: 'Commercial Building Gamma',
                type: 'FiT'
            },
            {
                plant_id: '550e8400-e29b-41d4-a716-446655440004',
                plant_name: 'Industrial Plant Delta',
                type: 'Zero Export'
            },
            {
                plant_id: '550e8400-e29b-41d4-a716-446655440005',
                plant_name: 'Rooftop Installation Epsilon',
                type: 'FiT'
            }
        ];

        return of(dummyPlants);
    }

    /**
     * Get plant by ID
     * TODO: implement this when backend endpoint is ready
     */
    getPlantById(plantId: string): Observable<Plant | null> {
        // For now, search in dummy data
        // Later this will be: return this.http.get<Plant>(`${this.baseUrl}${plantId}`);

        return new Observable(observer => {
            this.getPlants().subscribe(plants => {
                const plant = plants.find(p => p.plant_id === plantId) || null;
                observer.next(plant);
                observer.complete();
            });
        });
    }

    /**
     * Search plants by name or type
     */
    searchPlants(query: string): Observable<Plant[]> {
        return new Observable(observer => {
            this.getPlants().subscribe(plants => {
                const filtered = plants.filter(plant =>
                    plant.plant_name.toLowerCase().includes(query.toLowerCase()) ||
                    plant.type.toLowerCase().includes(query.toLowerCase())
                );
                observer.next(filtered);
                observer.complete();
            });
        });
    }
}

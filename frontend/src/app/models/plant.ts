export interface Plant {
    plant_id: string; // UUID
    plant_name: string;
    type: 'FiT' | 'Zero Export'; // Feed-in Tariff or Zero Export
}

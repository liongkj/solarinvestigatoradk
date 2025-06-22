export const environment = {
    production: true,
    backendUrl: (globalThis as any).env?.['BACKEND_URL'] || 'http://localhost:8000',
    apiUrl: (globalThis as any).env?.['API_URL'] || 'http://localhost:8000/api'
};

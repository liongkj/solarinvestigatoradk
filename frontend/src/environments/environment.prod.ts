// Declare window.env to avoid TypeScript errors
declare let window: any;

export const environment = {
    production: true,
    backendUrl: (window as any)?.env?.['BACKEND_URL'] || 'http://localhost:8000',
    apiUrl: (window as any)?.env?.['API_URL'] || 'http://localhost:8000/api',
};

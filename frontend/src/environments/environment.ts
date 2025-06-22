// Declare window.env to avoid TypeScript errors
declare let window: any;

export const environment = {
    backendUrl: (window as any)?.env?.['BACKEND_URL'] || 'http://localhost:8000',
    apiUrl: (window as any)?.env?.['API_URL'] || 'http://localhost:8000/api',
};

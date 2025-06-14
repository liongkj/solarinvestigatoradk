/**
 * Custom hook for managing dashboard data
 */
import { useState, useEffect, useCallback } from 'react';
import { api, Project, Investigation, WorkOrder, DashboardSummary, ApiError } from '@/lib/api';

interface DashboardData {
    projects: Project[];
    investigations: Investigation[];
    workOrders: WorkOrder[];
    summary: DashboardSummary | null;
}

interface DashboardState extends DashboardData {
    isLoading: boolean;
    error: string | null;
    refresh: () => Promise<void>;
}

const initialData: DashboardData = {
    projects: [],
    investigations: [],
    workOrders: [],
    summary: null,
};

export function useDashboardData(): DashboardState {
    const [data, setData] = useState<DashboardData>(initialData);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const fetchData = useCallback(async () => {
        try {
            setIsLoading(true);
            setError(null);

            // Fetch all data in parallel
            const [projects, investigations, workOrders, summary] = await Promise.all([
                api.getProjects(),
                api.getInvestigations(),
                api.getWorkOrders(),
                api.getDashboardSummary(),
            ]);

            setData({
                projects,
                investigations,
                workOrders,
                summary,
            });
        } catch (err) {
            const errorMessage = err instanceof ApiError
                ? `API Error (${err.status}): ${err.message}`
                : err instanceof Error
                    ? err.message
                    : 'An unknown error occurred';

            setError(errorMessage);
            console.error('Failed to fetch dashboard data:', err);
        } finally {
            setIsLoading(false);
        }
    }, []);

    const refresh = useCallback(async () => {
        await fetchData();
    }, [fetchData]);

    // Initial data fetch
    useEffect(() => {
        fetchData();
    }, [fetchData]);

    return {
        ...data,
        isLoading,
        error,
        refresh,
    };
}

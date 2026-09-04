import React, { useEffect, useState } from 'react';
import { SecureAPI } from '../lib/secureApi';

interface RevenueData {
    property_id: string;
    total_revenue: number;
    currency: string;
    reservations_count: number;
}

interface RevenueSummaryProps {
    propertyId?: string;
    debugTenant?: string; 
    showRaw?: boolean;
}

export const RevenueSummary: React.FC<RevenueSummaryProps> = ({ propertyId = 'prop-001', debugTenant, showRaw }) => {
    const [data, setData] = useState<RevenueData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    const activeTenant = debugTenant || 'candidate';

    useEffect(() => {
        console.log(`DEBUG RevenueSummary: fetching revenue - propertyId=${propertyId}, activeTenant=${activeTenant}`);
        const fetchRevenue = async () => {
            setLoading(true);
            try {
                // Use SecureAPI to handle authentication automatically
                // We pass the simulatedTenant option which SecureAPI will attach as a header
                const response = await SecureAPI.getDashboardSummary(propertyId, {
                    simulatedTenant: activeTenant,
                    timestamp: Date.now()
                });
                console.log(`DEBUG RevenueSummary: response received for propertyId=${propertyId}`, response);
                setData(response);
            } catch (err) {
                setError('Failed to load revenue data');
                console.error(err);
            } finally {
                setLoading(false);
            }
        };

        fetchRevenue();
    }, [propertyId, activeTenant]);

    if (loading) {
        return (
            <div className="p-6 bg-white border border-gray-200 shadow-sm rounded-xl">
                <div className="space-y-4 animate-pulse">
                    <div className="w-1/4 h-4 bg-gray-100 rounded"></div>
                    <div className="w-1/2 h-8 bg-gray-100 rounded"></div>
                    <div className="flex gap-4 pt-4">
                        <div className="flex-1 h-12 bg-gray-100 rounded"></div>
                        <div className="flex-1 h-12 bg-gray-100 rounded"></div>
                    </div>
                </div>
            </div>
        );
    }

    if (error) return <div className="p-4 text-red-500 rounded-lg bg-red-50">{error}</div>;
    if (!data) return null;

    const displayTotal = Math.round(data.total_revenue * 100) / 100;

    return (
        <div className="overflow-hidden transition-shadow duration-300 bg-white border border-gray-200 shadow-sm rounded-xl hover:shadow-md">
            {showRaw && (
                <div className="p-3 overflow-auto font-mono text-xs border-b border-gray-100 bg-gray-50 max-h-32">
                    <strong className="block mb-1 text-gray-500 uppercase tracking-wider text-[10px]">Raw API Response</strong>
                    <pre className="text-gray-700">{JSON.stringify(data, null, 2)}</pre>
                </div>
            )}

            <div className="p-6">
                <div className="flex items-center justify-between mb-6">
                    <div>
                        <h2 className="text-sm font-medium tracking-wide text-gray-500 uppercase">Total Revenue</h2>
                        <div className="flex items-baseline gap-2 mt-1">
                            <span className="text-3xl font-bold tracking-tight text-gray-900">
                                {data.currency} {displayTotal.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                            </span>
                            {/* Fake trend indicator for premium feel */}
                            <span className="inline-flex items-baseline px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800 md:mt-2 lg:mt-0">
                                <svg className="-ml-1 mr-0.5 h-3 w-3 flex-shrink-0 self-center text-green-500" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
                                    <path fillRule="evenodd" d="M5.293 9.707a1 1 0 010-1.414l4-4a1 1 0 011.414 0l4 4a1 1 0 01-1.414 1.414L11 7.414V15a1 1 0 11-2 0V7.414L6.707 9.707a1 1 0 01-1.414 0z" clipRule="evenodd" />
                                </svg>
                                12%
                            </span>
                        </div>
                    </div>
                </div>

                <div className="grid grid-cols-2 gap-4 pt-4 border-t border-gray-100">
                    <div>
                        <p className="text-xs font-medium tracking-wider text-gray-500 uppercase">Property ID</p>
                        <p className="mt-1 font-mono text-sm font-semibold text-gray-700">{data.property_id}</p>
                    </div>
                    <div>
                        <p className="text-xs font-medium tracking-wider text-gray-500 uppercase">Reservations</p>
                        <p className="mt-1 text-sm font-semibold text-gray-700">{data.reservations_count} <span className="font-normal text-gray-400">bookings</span></p>
                    </div>
                </div>

                {/* Precision Warning Area */}
                <div className="h-6 mt-4">
                    {Math.abs(data.total_revenue - displayTotal) > 0.000001 && showRaw && (
                        <div className="flex items-center px-2 py-1 text-xs rounded text-amber-600 bg-amber-50">
                            <svg className="h-4 w-4 mr-1.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                            </svg>
                            Precision Mismatch Detected
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { useSearch } from '@tanstack/react-router';

/**
 * Results page.  Displays basic statistics for a Phase 1 or Phase 2
 * output directory.  The directory is passed as a search parameter
 * ``dir`` via the router.  In a future update this component could be
 * extended to show paginated tables of papers using TanStack Table.
 */
const Results: React.FC = () => {
  // Read the ``dir`` query parameter from the router
  const search = useSearch({ from: '/results' }) as { dir?: string };
  const phaseDir = search?.dir;

  // Fetch stats for the specified directory
  const { data, isLoading, error } = useQuery(
    ['resultsStats', phaseDir],
    async () => {
      if (!phaseDir) throw new Error('No phase directory specified');
      const res = await fetch(`/api/results/${encodeURIComponent(phaseDir)}/stats`);
      if (!res.ok) throw new Error('Failed to fetch stats');
      return res.json();
    },
    { enabled: Boolean(phaseDir) },
  );

  if (!phaseDir) {
    return <p className="text-gray-600">No results directory specified.</p>;
  }

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Results for {phaseDir}</h2>
      {isLoading && <p>Loading statistics…</p>}
      {error && <p className="text-red-600">Error loading statistics.</p>}
      {data && !data.error && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Object.entries(data).map(([key, value]) => (
            <div key={key} className="p-4 bg-white shadow rounded-lg">
              <div className="text-sm text-gray-500 capitalize">{key.replace('_', ' ')}</div>
              <div className="text-xl font-bold text-gray-800">{String(value)}</div>
            </div>
          ))}
        </div>
      )}
      {data && data.error && (
        <p className="text-gray-600">{data.error}</p>
      )}
    </div>
  );
};

export default Results;
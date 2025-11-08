import React from 'react';

/**
 * Dashboard page for the React UI.  This page provides a high‑level
 * overview of the pipeline’s status.  It will eventually fetch
 * statistics from the server (e.g. number of cached queries, active
 * jobs, completed searches), but currently it displays placeholder
 * values until a dedicated API endpoint is implemented.
 */
const Dashboard: React.FC = () => {
  // Placeholder stats; in a future update these should be replaced
  // with values fetched via React Query from an API endpoint such as
  // ``/api/dashboard/stats``.  The old UI displayed cached queries,
  // active jobs, phase1 runs and phase2 runs on the dashboard.
  const stats = {
    cachedQueries: 0,
    activeJobs: 0,
    phase1Runs: 0,
    phase2Runs: 0,
  };

  const cards = [
    { label: 'Cached Queries', value: stats.cachedQueries, color: 'bg-green-100', icon: '🗄️' },
    { label: 'Active Jobs', value: stats.activeJobs, color: 'bg-blue-100', icon: '⚙️' },
    { label: 'Phase 1 Runs', value: stats.phase1Runs, color: 'bg-purple-100', icon: '🔍' },
    { label: 'Phase 2 Runs', value: stats.phase2Runs, color: 'bg-yellow-100', icon: '📊' },
  ];

  return (
    <div className="space-y-8">
      <div className="bg-white shadow rounded-lg p-6">
        <h2 className="text-2xl font-bold mb-2">Systematic Review Pipeline</h2>
        <p className="text-gray-600">Automated literature search and analysis across multiple academic databases.</p>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        {cards.map((card) => (
          <div key={card.label} className={`p-4 rounded-lg shadow flex items-center ${card.color}`}>
            <div className="mr-4 text-3xl">{card.icon}</div>
            <div>
              <div className="text-sm text-gray-500">{card.label}</div>
              <div className="text-2xl font-bold text-gray-800">{card.value}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default Dashboard;
import React, { useState, useEffect } from 'react';
import { useNavigate } from '@tanstack/react-router';

/**
 * Search page for the React UI.  Allows the user to submit a
 * multi‑database query and displays progress while the background job
 * executes.  Once the job completes, the user is redirected to the
 * results page for the new phase 1 directory.
 */
const Search: React.FC = () => {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [databases, setDatabases] = useState<string[]>(['openalex']);
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [limit, setLimit] = useState<number | ''>('');
  const [jobId, setJobId] = useState<string | null>(null);
  const [progress, setProgress] = useState<number>(0);
  const [total, setTotal] = useState<number | null>(null);
  const [outputDir, setOutputDir] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Poll job status when jobId is set
  useEffect(() => {
    if (!jobId) return;
    let interval: number;
    const poll = async () => {
      try {
        const res = await fetch(`/api/jobs/${jobId}`);
        if (res.ok) {
          const data = await res.json();
          setProgress(data.progress ?? 0);
          setTotal(data.total ?? null);
          if (data.status === 'completed') {
            setOutputDir(data.output_dir);
            clearInterval(interval);
          }
          if (data.status === 'failed') {
            clearInterval(interval);
            setError(data.error || 'Search failed.');
          }
        }
      } catch (err) {
        console.error(err);
      }
    };
    poll();
    interval = window.setInterval(poll, 2000);
    return () => clearInterval(interval);
  }, [jobId]);

  // Redirect to results when outputDir is set
  useEffect(() => {
    if (outputDir) {
      // Navigate to results page with phaseDir param
      navigate({ to: '/results', search: { dir: outputDir } });
    }
  }, [outputDir, navigate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setProgress(0);
    setTotal(null);
    try {
      const payload = {
        query,
        databases,
        start_date: startDate || new Date('1900-01-01').toISOString().split('T')[0],
        end_date: endDate || new Date().toISOString().split('T')[0],
        limit: limit || null,
      };
      const res = await fetch('/api/search/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        throw new Error(`Error: ${res.status}`);
      }
      const data = await res.json();
      setJobId(data.job_id);
    } catch (err: any) {
      setError(err.message);
    }
  };

  const toggleDatabase = (value: string) => {
    setDatabases((prev) =>
      prev.includes(value)
        ? prev.filter((db) => db !== value)
        : [...prev, value],
    );
  };

  return (
    <div className="max-w-xl mx-auto space-y-6">
      <h2 className="text-2xl font-bold">Search Academic Papers</h2>
      <p className="text-gray-600">Configure your search across multiple academic databases.</p>
      <form onSubmit={handleSubmit} className="space-y-4 bg-white shadow rounded-lg p-6">
        {error && <div className="text-red-600 mb-2">{error}</div>}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Search Query</label>
          <input
            type="text"
            required
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
            placeholder="e.g. machine learning fairness"
          />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Start Date</label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">End Date</label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Databases</label>
          <div className="flex flex-wrap gap-2">
            {['openalex', 'semantic_scholar', 'crossref', 'arxiv'].map((db) => (
              <label key={db} className="flex items-center space-x-2 text-sm">
                <input
                  type="checkbox"
                  checked={databases.includes(db)}
                  onChange={() => toggleDatabase(db)}
                  className="text-blue-600"
                />
                <span className="capitalize">{db.replace('_', ' ')}</span>
              </label>
            ))}
          </div>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Limit (per database)</label>
          <input
            type="number"
            min={1}
            value={limit}
            onChange={(e) => setLimit(e.target.value === '' ? '' : parseInt(e.target.value, 10))}
            className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
            placeholder="e.g. 100"
          />
        </div>
        <button
          type="submit"
          disabled={!!jobId}
          className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white py-3 rounded-lg font-semibold"
        >
          {jobId ? 'Running…' : '🔎 Start Search'}
        </button>
      </form>
      {jobId && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <h3 className="text-lg font-semibold text-gray-800 mb-2">Search Progress</h3>
          <div className="text-gray-700">Processed {progress} papers{total ? ` / ${total}` : ''}</div>
          <div className="relative h-4 mt-2 bg-gray-200 rounded-full overflow-hidden">
            <div
              className="bg-blue-600 h-full rounded-full transition-all"
              style={{ width: total && total > 0 ? `${(progress / total) * 100}%` : '0%' }}
            />
          </div>
        </div>
      )}
    </div>
  );
};

export default Search;
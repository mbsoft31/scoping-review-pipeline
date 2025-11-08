import React, { useState, useEffect } from 'react';
import { useNavigate } from '@tanstack/react-router';

/**
 * Analysis page.  Allows a user to kick off Phase 2 (deduplication
 * and citation enrichment) by specifying the path to a Phase 1
 * directory.  Displays the analysis phase as it runs and
 * redirects to the results page when complete.
 */
const Analyze: React.FC = () => {
  const navigate = useNavigate();
  const [phase1Dir, setPhase1Dir] = useState('');
  const [citationMax, setCitationMax] = useState(200);
  const [refsPerPaper, setRefsPerPaper] = useState(100);
  const [jobId, setJobId] = useState<string | null>(null);
  const [phase, setPhase] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [outputDir, setOutputDir] = useState<string | null>(null);

  useEffect(() => {
    if (!jobId) return;
    let interval: number;
    const poll = async () => {
      try {
        const res = await fetch(`/api/jobs/${jobId}`);
        if (res.ok) {
          const data = await res.json();
          setPhase(String(data.phase || ''));
          if (data.status === 'completed') {
            setOutputDir(data.output_dir);
            clearInterval(interval);
          }
          if (data.status === 'failed') {
            clearInterval(interval);
            setError(data.error || 'Analysis failed.');
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

  useEffect(() => {
    if (outputDir) {
      navigate({ to: '/results', search: { dir: outputDir } });
    }
  }, [outputDir, navigate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      const payload = {
        phase1_dir: phase1Dir,
        citation_max_papers: citationMax,
        refs_per_paper: refsPerPaper,
      };
      const res = await fetch('/api/analyze/start', {
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

  return (
    <div className="max-w-xl mx-auto space-y-6">
      <h2 className="text-2xl font-bold">Phase 2 Analysis</h2>
      <p className="text-gray-600">
        Enter the path to the Phase 1 directory (e.g. <code>output/phase1_20240101_120000</code>) and
        configure citation enrichment.  The analysis will perform deduplication,
        citation enrichment and influence scoring.
      </p>
      <form onSubmit={handleSubmit} className="space-y-4 bg-white shadow rounded-lg p-6">
        {error && <div className="text-red-600 mb-2">{error}</div>}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Phase 1 Directory</label>
          <input
            type="text"
            required
            value={phase1Dir}
            onChange={(e) => setPhase1Dir(e.target.value)}
            className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
            placeholder="output/phase1_20240101_120000"
          />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Max papers for citation
              enrichment</label>
            <input
              type="number"
              min={10}
              value={citationMax}
              onChange={(e) => setCitationMax(parseInt(e.target.value, 10))}
              className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">References per paper</label>
            <input
              type="number"
              min={10}
              value={refsPerPaper}
              onChange={(e) => setRefsPerPaper(parseInt(e.target.value, 10))}
              className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>
        <button
          type="submit"
          disabled={!!jobId}
          className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white py-3 rounded-lg font-semibold"
        >
          {jobId ? 'Analyzing…' : '⚙️ Start Analysis'}
        </button>
      </form>
      {jobId && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <h3 className="text-lg font-semibold text-gray-800 mb-2">Analysis Progress</h3>
          <div className="text-gray-700 capitalize">Current phase: {phase || 'initializing'}</div>
        </div>
      )}
    </div>
  );
};

export default Analyze;
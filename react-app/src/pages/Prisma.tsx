import React, { useState, useEffect } from 'react';

/**
 * PRISMA diagram page.  This page allows users to generate a PRISMA flow
 * diagram summarising the record identification and screening process.
 * Users provide the Phase 1 directory and optionally screening and
 * deduplication directories.  The backend computes the counts and
 * produces a diagram.  When complete, the diagram and counts are
 * displayed.
 */
const Prisma: React.FC = () => {
  const [phase1Dir, setPhase1Dir] = useState('');
  const [screeningDir, setScreeningDir] = useState('');
  const [dedupDir, setDedupDir] = useState('');
  const [jobId, setJobId] = useState<string | null>(null);
  const [counts, setCounts] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);

  // Poll job status for PRISMA job
  useEffect(() => {
    if (!jobId) return;
    let interval: number;
    const poll = async () => {
      try {
        const res = await fetch(`/api/jobs/${jobId}`);
        if (res.ok) {
          const data = await res.json();
          if (data.status === 'completed') {
            clearInterval(interval);
            setCounts(data.counts || null);
          } else if (data.status === 'failed') {
            clearInterval(interval);
            setError(data.error || 'PRISMA generation failed.');
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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!phase1Dir) {
      setError('Please specify the Phase 1 directory.');
      return;
    }
    setError(null);
    setGenerating(true);
    try {
      const payload = {
        phase1_dir: phase1Dir,
        screening_dir: screeningDir || null,
        dedup_dir: dedupDir || null,
      };
      const res = await fetch('/api/prisma/start', {
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
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="max-w-xl mx-auto space-y-6">
      <h2 className="text-2xl font-bold">PRISMA Diagram</h2>
      <p className="text-gray-600">
        Generate a PRISMA flow diagram summarising the study selection process.  Provide
        the Phase 1 search directory and optionally the screening and deduplication
        directories.  The resulting diagram and counts will be shown upon completion.
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
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Screening Directory (optional)</label>
          <input
            type="text"
            value={screeningDir}
            onChange={(e) => setScreeningDir(e.target.value)}
            className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
            placeholder="output/phase1.5_20240101_120000"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Deduplication Directory (optional)</label>
          <input
            type="text"
            value={dedupDir}
            onChange={(e) => setDedupDir(e.target.value)}
            className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
            placeholder="output/phase2_20240101_120000"
          />
        </div>
        <button
          type="submit"
          disabled={generating || !!jobId}
          className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white py-3 rounded-lg font-semibold"
        >
          {jobId ? 'Generating…' : '📊 Generate PRISMA Diagram'}
        </button>
      </form>
      {jobId && !counts && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <h3 className="text-lg font-semibold text-gray-800 mb-2">PRISMA Progress</h3>
          <p className="text-gray-700">Computing counts…</p>
        </div>
      )}
      {counts && (
        <div className="space-y-6">
          <div className="bg-white shadow rounded-lg p-6">
            <h3 className="text-lg font-semibold mb-2">PRISMA Counts</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
              {Object.entries(counts).map(([key, value]) => (
                <div key={key} className="flex justify-between">
                  <span className="capitalize text-gray-600">{key.replace(/_/g, ' ')}</span>
                  <span className="font-medium text-gray-800">{String(value)}</span>
                </div>
              ))}
            </div>
          </div>
          <div className="bg-white shadow rounded-lg p-6">
            <h3 className="text-lg font-semibold mb-4">PRISMA Diagram</h3>
            <img
              src={`/api/prisma/${jobId}/image`}
              alt="PRISMA Diagram"
              className="w-full object-contain"
            />
          </div>
        </div>
      )}
    </div>
  );
};

export default Prisma;
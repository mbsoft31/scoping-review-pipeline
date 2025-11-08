import React, { useState, useEffect } from 'react';
import { useNavigate } from '@tanstack/react-router';

/**
 * Quality assessment page.  Allows users to run automated risk‑of‑bias
 * assessments on an extracted data directory using various tools
 * (ROB 2, ROBINS‑I, Newcastle–Ottawa).  The assessment job is
 * polled for progress and the user is redirected to the results
 * directory once complete.
 */
const Quality: React.FC = () => {
  const navigate = useNavigate();
  const [phaseDir, setPhaseDir] = useState('');
  const [tool, setTool] = useState('rob2');
  const [jobId, setJobId] = useState<string | null>(null);
  const [phase, setPhase] = useState<string>('');
  const [progress, setProgress] = useState<number>(0);
  const [total, setTotal] = useState<number | null>(null);
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
          setProgress(data.progress ?? 0);
          setTotal(data.total ?? null);
          if (data.status === 'completed') {
            setOutputDir(data.output_dir);
            clearInterval(interval);
          }
          if (data.status === 'failed') {
            clearInterval(interval);
            setError(data.error || 'Quality assessment failed.');
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
        phase_dir: phaseDir,
        tool,
      };
      const res = await fetch('/api/quality/start', {
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
      <h2 className="text-2xl font-bold">Quality Assessment</h2>
      <p className="text-gray-600">
        Select the directory containing extracted data and choose a
        risk‑of‑bias tool to run an automated assessment.  This will
        generate a new Phase 1.8 directory with assessment results.
      </p>
      <form onSubmit={handleSubmit} className="space-y-4 bg-white shadow rounded-lg p-6">
        {error && <div className="text-red-600 mb-2">{error}</div>}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Extracted Data Directory</label>
          <input
            type="text"
            required
            value={phaseDir}
            onChange={(e) => setPhaseDir(e.target.value)}
            className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
            placeholder="output/phase1.7_20240101_120000"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Assessment Tool</label>
          <select
            value={tool}
            onChange={(e) => setTool(e.target.value)}
            className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
          >
            <option value="rob2">RoB 2 (randomized trials)</option>
            <option value="robins_i">ROBINS‑I (non‑randomized studies)</option>
            <option value="newcastle_ottawa">Newcastle–Ottawa (cohort/case control)</option>
          </select>
        </div>
        <button
          type="submit"
          disabled={!!jobId}
          className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white py-3 rounded-lg font-semibold"
        >
          {jobId ? 'Assessing…' : '🎯 Start Assessment'}
        </button>
      </form>
      {jobId && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <h3 className="text-lg font-semibold text-gray-800 mb-2">Assessment Progress</h3>
          <div className="text-gray-700 capitalize">Phase: {phase || 'initializing'}</div>
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

export default Quality;
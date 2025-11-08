import React, { useState, useEffect } from 'react';
import { useNavigate } from '@tanstack/react-router';

/**
 * Meta‑analysis page.  Allows users to upload a CSV of effect sizes
 * and configure pooling parameters.  The form posts the file and
 * settings to the backend and polls the job status until the
 * analysis completes.  When complete, it displays summary statistics
 * (pooled effect, heterogeneity, publication bias) and renders the
 * generated forest plot.
 */
const Meta: React.FC = () => {
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [method, setMethod] = useState('random');
  const [effectCol, setEffectCol] = useState('effect');
  const [seCol, setSeCol] = useState('se');
  const [studyCol, setStudyCol] = useState('study_id');
  const [jobId, setJobId] = useState<string | null>(null);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Poll job status when a job ID is present
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
            setResult(data.result || null);
          } else if (data.status === 'failed') {
            clearInterval(interval);
            setError(data.error || 'Meta‑analysis failed.');
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

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setFile(e.target.files[0]);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setError('Please select a CSV file.');
      return;
    }
    setError(null);
    setLoading(true);
    try {
      const fd = new FormData();
      fd.append('method', method);
      fd.append('effect_col', effectCol);
      fd.append('se_col', seCol);
      fd.append('study_col', studyCol);
      fd.append('file', file);
      const res = await fetch('/api/meta/start', {
        method: 'POST',
        body: fd,
      });
      if (!res.ok) {
        throw new Error(`Error: ${res.status}`);
      }
      const data = await res.json();
      setJobId(data.job_id);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <h2 className="text-2xl font-bold">Meta‑Analysis</h2>
      <p className="text-gray-600">
        Upload a CSV file containing per‑study effect sizes and standard errors.  Configure the
        pooling method and column names, then run a meta‑analysis.  Upon completion the pooled
        estimate, heterogeneity statistics and a forest plot will be displayed.
      </p>
      <form onSubmit={handleSubmit} className="space-y-4 bg-white shadow rounded-lg p-6">
        {error && <div className="text-red-600 mb-2">{error}</div>}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">CSV File</label>
          <input
            type="file"
            accept=".csv"
            onChange={handleFileChange}
            className="w-full"
          />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Method</label>
            <select
              value={method}
              onChange={(e) => setMethod(e.target.value)}
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
            >
              <option value="fixed">Fixed‑Effect</option>
              <option value="random">Random‑Effects</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Effect Column</label>
            <input
              type="text"
              value={effectCol}
              onChange={(e) => setEffectCol(e.target.value)}
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">SE Column</label>
            <input
              type="text"
              value={seCol}
              onChange={(e) => setSeCol(e.target.value)}
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Study ID Column</label>
            <input
              type="text"
              value={studyCol}
              onChange={(e) => setStudyCol(e.target.value)}
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>
        <button
          type="submit"
          disabled={loading || !!jobId}
          className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white py-3 rounded-lg font-semibold"
        >
          {jobId ? 'Running…' : '📈 Run Meta‑Analysis'}
        </button>
      </form>
      {jobId && !result && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <h3 className="text-lg font-semibold text-gray-800 mb-2">Meta‑Analysis Progress</h3>
          <p className="text-gray-700">Processing…</p>
        </div>
      )}
      {result && (
        <div className="space-y-6">
          <div className="bg-white shadow rounded-lg p-6">
            <h3 className="text-lg font-semibold mb-2">Summary Statistics</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
              <div>
                <div className="text-gray-500">Pooled Effect</div>
                <div className="font-medium text-gray-800">
                  {result.pooled?.pooled_effect?.toFixed(3)} ({result.pooled?.ci_lower?.toFixed(3)} to {result.pooled?.ci_upper?.toFixed(3)})
                </div>
              </div>
              <div>
                <div className="text-gray-500">Heterogeneity (I²)</div>
                <div className="font-medium text-gray-800">
                  {result.heterogeneity?.I_squared?.toFixed(1)}%
                </div>
              </div>
              <div>
                <div className="text-gray-500">Q Statistic p‑value</div>
                <div className="font-medium text-gray-800">
                  {result.heterogeneity?.Q_pvalue?.toExponential(2)}
                </div>
              </div>
              <div>
                <div className="text-gray-500">Publication Bias</div>
                <div className="font-medium text-gray-800">
                  {result.bias?.interpretation || 'N/A'}
                </div>
              </div>
              <div>
                <div className="text-gray-500">Number of Studies</div>
                <div className="font-medium text-gray-800">{result.n_studies}</div>
              </div>
            </div>
          </div>
          <div className="bg-white shadow rounded-lg p-6">
            <h3 className="text-lg font-semibold mb-4">Forest Plot</h3>
            <img
              src={`/api/meta/${jobId}/plot`}
              alt="Forest Plot"
              className="w-full object-contain"
            />
          </div>
        </div>
      )}
    </div>
  );
};

export default Meta;
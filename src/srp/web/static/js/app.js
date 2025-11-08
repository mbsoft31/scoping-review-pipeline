/**
 * Global JavaScript functions for the SRP web dashboard.
 *
 * This file defines Alpine.js components used across the web
 * templates.  Components are returned as plain objects which
 * Alpine will initialise at runtime.  Functions mirror the
 * examples provided in the project documentation, but are
 * simplified for clarity.
 */

/* Dashboard component used on the home page to display simple
 * statistics.  In a real deployment, you might fetch these
 * values from an API endpoint.  For now we initialise them
 * statically to zero. */
function dashboard() {
  return {
    stats: {
      active_jobs: 0,
      cached_queries: 0,
      phase1_runs: 0,
      phase2_runs: 0,
    },
    async init() {
      // Fetch cached query count and active jobs from the API
      try {
        const queries = await fetch('/api/cache/queries').then(r => r.json());
        this.stats.cached_queries = queries.length;
      } catch (err) {
        console.error('Failed to load cached queries', err);
      }
    },
  };
}

/* Results browser component.  This takes the list of phase
 * directories from the server-side context and provides
 * methods for viewing papers and exporting BibTeX. */
function resultsApp() {
  return {
    activeTab: 'phase1',
    phase1Dirs: [],
    phase2Dirs: [],
    showPapersModal: false,
    currentPath: null,
    init() {
      // Phase directory arrays are injected by the template
    },
    viewPapers(path) {
      this.currentPath = path;
      this.showPapersModal = true;
      // Defer HTMX attribute updates until next tick
      setTimeout(() => {
        const container = document.getElementById('papers-container');
        container.setAttribute('hx-get', `/api/results/${path}/papers?page=1`);
        if (window.htmx) {
          window.htmx.process(container);
          window.htmx.trigger(container, 'load');
        }
      }, 100);
    },
    viewSeminalPapers(path) {
      window.location.href = `/results/${path}/seminal`;
    },
    viewNetwork(path) {
      window.location.href = `/results/${path}/network`;
    },
    async exportBibtex(path, topN = null) {
      try {
        const url = `/api/export/${path}/bibtex` + (topN ? `?top_n=${topN}` : '');
        const response = await fetch(url, { method: 'POST' });
        const data = await response.json();
        alert(`BibTeX exported to: ${data.path}`);
      } catch (error) {
        alert('Export failed: ' + error.message);
      }
    },
  };
}

/* Analyse component used on the Phase 2 page.  This provides
 * reactive form handling and progress polling. */
function analyzeApp() {
  return {
    form: {
      phase1_dir: '',
      citation_max_papers: 200,
      refs_per_paper: 100,
      fuzzy_threshold: 0.85,
      skip_citations: false,
    },
    loading: false,
    jobId: null,
    currentPhase: null,
    submitAnalysis: async function () {
      this.loading = true;
      try {
        const response = await fetch('/api/analyze/start', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(this.form),
        });
        const data = await response.json();
        this.jobId = data.job_id;
        this.pollProgress();
        if (window.htmx) {
          window.htmx.process(document.body);
        }
      } catch (error) {
        alert('Error starting analysis: ' + error.message);
      } finally {
        this.loading = false;
      }
    },
    pollProgress() {
      const interval = setInterval(async () => {
        try {
          const response = await fetch(`/api/jobs/${this.jobId}`);
          const job = await response.json();
          this.currentPhase = job.phase;
          if (job.status === 'completed' || job.status === 'failed') {
            clearInterval(interval);
          }
        } catch (error) {
          console.error('Polling error:', error);
        }
      }, 2000);
    },
    phaseComplete(phase) {
      const phases = ['loading', 'deduplicating', 'fetching_citations', 'computing_influence'];
      const currentIndex = phases.indexOf(this.currentPhase);
      const checkIndex = phases.indexOf(phase);
      return currentIndex > checkIndex;
    },
  };
}
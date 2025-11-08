/**
 * Data extraction component for the SRP web UI.
 *
 * Presents options for selecting a phase directory and extraction
 * targets, starts an extraction job via the API and polls for
 * progress using HTMX.  Fields mirror those defined in the
 * legacy JavaScript implementation.
 */
export function extractionApp() {
  return {
    config: {
      use_open_access: true,
      use_unpaywall: true,
      unpaywall_email: '',
      extract_sample_size: true,
      extract_outcomes: true,
      extract_statistics: true,
      extract_methods: true,
    },
    loading: false,
    phaseDir: '',
    jobId: null as string | null,
    async startExtraction() {
      this.loading = true;
      try {
        const payload = {
          phase_dir: this.phaseDir,
          use_open_access: this.config.use_open_access,
          use_unpaywall: this.config.use_unpaywall,
          unpaywall_email: this.config.unpaywall_email,
          extract_sample_size: this.config.extract_sample_size,
          extract_outcomes: this.config.extract_outcomes,
          extract_statistics: this.config.extract_statistics,
          extract_methods: this.config.extract_methods,
        };
        const response = await fetch('/api/extraction/start', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        const data = await response.json();
        this.jobId = data.job_id;
        // Trigger HTMX processing
        const htmx: any = (window as any).htmx;
        if (htmx) {
          htmx.process(document.body);
        }
      } catch (err: any) {
        alert('Extraction failed: ' + err.message);
      } finally {
        this.loading = false;
      }
    },
  };
}
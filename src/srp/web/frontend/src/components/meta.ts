/**
 * Meta‑analysis component for the SRP web UI.
 *
 * Allows users to upload effect size data, configure column names
 * and pooling method, and triggers a meta‑analysis job via the API.
 * Progress and results (including heterogeneity and publication bias)
 * are polled from the backend.  This module ports the logic from
 * ``meta.html`` into a TypeScript Alpine.js component.
 */
export function metaApp() {
  return {
    form: {
      method: 'random',
      effect_col: 'effect',
      se_col: 'se',
      study_col: 'study_id',
    } as Record<string, string>,
    file: null as File | null,
    loading: false,
    jobId: null as string | null,
    result: null as any,
    handleFile(event: Event) {
      const target = event.target as HTMLInputElement;
      if (target?.files && target.files.length > 0) {
        this.file = target.files[0];
      }
    },
    async startMeta() {
      // Trigger a meta‑analysis job by uploading the CSV and parameters.
      if (!this.file) return;
      this.loading = true;
      try {
        const fd = new FormData();
        fd.append('method', this.form.method);
        fd.append('effect_col', this.form.effect_col);
        fd.append('se_col', this.form.se_col);
        fd.append('study_col', this.form.study_col);
        fd.append('file', this.file);
        const resp = await fetch('/api/meta/start', {
          method: 'POST',
          body: fd,
        });
        const data = await resp.json();
        this.jobId = data.job_id;
        this.pollProgress();
        // Trigger HTMX to update progress placeholders
        const htmx: any = (window as any).htmx;
        if (htmx) {
          htmx.process(document.body);
        }
      } catch (err: any) {
        alert('Meta‑analysis failed: ' + err.message);
      } finally {
        this.loading = false;
      }
    },
    pollProgress() {
      // Poll job status every two seconds until completion or failure.
      const interval = setInterval(async () => {
        if (!this.jobId) return;
        try {
          const res = await fetch(`/api/jobs/${this.jobId}`);
          const job = await res.json();
          if (job.status === 'completed') {
            clearInterval(interval);
            this.result = job.result;
          } else if (job.status === 'failed') {
            clearInterval(interval);
            alert('Meta‑analysis failed: ' + job.error);
          }
        } catch (err: any) {
          console.error('Error polling meta job:', err);
        }
      }, 2000);
    },
  };
}
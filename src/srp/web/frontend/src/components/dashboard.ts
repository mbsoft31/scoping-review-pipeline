/**
 * Dashboard component for the SRP web UI.
 *
 * Returns an Alpine.js component that exposes a `stats` object
 * and an asynchronous `init` function.  When initialised, the
 * component fetches cached query information from the backend and
 * updates the statistics accordingly.
 */
export function dashboard() {
  return {
    stats: {
      active_jobs: 0,
      cached_queries: 0,
      phase1_runs: 0,
      phase2_runs: 0,
    },
    async init() {
      try {
        const queries: unknown = await fetch('/api/cache/queries').then((r) => r.json());
        // If the response is an array, update the cached query count
        if (Array.isArray(queries)) {
          this.stats.cached_queries = queries.length;
        }
      } catch (err) {
        console.error('Failed to load cached queries', err);
      }
    },
  };
}
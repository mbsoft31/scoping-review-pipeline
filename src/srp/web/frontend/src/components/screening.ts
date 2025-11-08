/**
 * Screening configuration component for the SRP web UI.
 *
 * Provides reactive data structures for configuring screening criteria
 * and thresholds.  Saves configuration to localStorage and triggers
 * screening jobs via the backend API.
 */
export function screeningApp() {
  return {
    activeTab: 'config' as string,
    loading: false,
    jobId: null as string | null,
    config: {
      phase1_dir: '',
      mode: 'auto',
      auto_threshold: 0.75,
      maybe_threshold: 0.5,
      model: 'all-MiniLM-L6-v2',
      inclusion_criteria: [] as any[],
      exclusion_criteria: [] as any[],
      vocabulary: {
        domain: '',
        concepts: [] as string[],
      },
    },
    vocabularyConcepts: '' as string,
    init() {
      const saved = localStorage.getItem('screening_config');
      if (saved) {
        const parsed = JSON.parse(saved);
        this.config = parsed;
        this.vocabularyConcepts = (parsed.vocabulary.concepts || []).join('\n');
      }
    },
    addCriterion(type: string) {
      const criterion = {
        criterion_id: `${type}_${Date.now()}`,
        name: '',
        description: '',
        criterion_type: type,
        keywords: [] as string[],
        semantic_query: '',
        weight: 1.0,
        is_mandatory: false,
      };
      if (type === 'inclusion') {
        this.config.inclusion_criteria.push(criterion);
      } else {
        this.config.exclusion_criteria.push(criterion);
      }
    },
    updateVocabularyConcepts() {
      this.config.vocabulary.concepts = this.vocabularyConcepts
        .split('\n')
        .map((s: string) => s.trim())
        .filter((s: string) => s.length > 0);
    },
    loadTemplate(template: string) {
      if (template === 'ml_fairness') {
        this.config.inclusion_criteria = [
          {
            criterion_id: 'inc_ml_fairness',
            name: 'Machine Learning Fairness',
            description: 'Addresses fairness, bias, or equity in ML systems',
            semantic_query: 'This paper discusses fairness, bias, or discrimination in machine learning',
            weight: 1.0,
            is_mandatory: true,
          },
          {
            criterion_id: 'inc_empirical',
            name: 'Empirical Study',
            description: 'Includes experiments or case studies',
            semantic_query: 'This paper presents empirical evaluation or experiments',
            weight: 0.8,
            is_mandatory: false,
          },
        ];
        this.config.exclusion_criteria = [
          {
            criterion_id: 'exc_workshop',
            name: 'Workshop Paper',
            description: 'Workshop or poster paper',
            semantic_query: 'This is a workshop paper or poster',
            weight: 0.9,
            is_mandatory: false,
          },
        ];
        this.vocabularyConcepts =
          'fairness metrics\nbias detection\ndisparate impact\nequal opportunity\ndemographic parity';
        this.updateVocabularyConcepts();
      }
      alert(`Loaded ${template} template`);
    },
    async startScreening() {
      this.loading = true;
      localStorage.setItem('screening_config', JSON.stringify(this.config));
      try {
        const response = await fetch('/api/screening/start', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(this.config),
        });
        const data = await response.json();
        this.jobId = data.job_id;
        const htmx: any = (window as any).htmx;
        if (htmx) {
          htmx.process(document.body);
        }
      } catch (error: any) {
        alert('Error starting screening: ' + error.message);
      } finally {
        this.loading = false;
      }
    },
  };
}
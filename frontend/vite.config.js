import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import { resolve } from 'node:path';

const snoDataPath = '/data/processed/record_role_classification_v1/full_drafts/sno_v31_reasonable_primary_v4_display/';
const snoSource = process.env.RECRUITMENT_SANDBOX_DIR ? pathToFileURL(resolve(process.env.RECRUITMENT_SANDBOX_DIR, 'display') + '/') : new URL('../data/processed/record_role_classification_v1/full_drafts/sno_v31_reasonable_primary_v4_display/', import.meta.url);

function snoDisplayData() {
  const files = new Set(['display_projection_v31_full_draft.json', 'sno_atomic_evidence_index_v1.json', 'unclassified_queue_v31.json', 'display_summary_v31.json', 'update_batches.json', 'daily_jobs_v1.json', 'job_search_index_v1.json', 'job_search_index_v1.meta.json', 'job_search_facets_v1.json']);
  return {
    name: 'readonly-sno-display-data',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const pathname = req.url?.split('?')[0] || '';
        if (!pathname.startsWith(snoDataPath)) return next();
        const file = pathname.slice(snoDataPath.length);
        if (!files.has(file)) { res.statusCode = 404; res.end('Not found'); return; }
        try { res.setHeader('Content-Type', 'application/json; charset=utf-8'); res.end(readFileSync(new URL(file, snoSource))); } catch (error) { next(error); }
      });
    },
    handleHotUpdate({ file, server }) {
      if (file.startsWith(snoSource.pathname)) { server.ws.send({ type: 'full-reload', path: '*' }); return []; }
      return undefined;
    },
    generateBundle() { for (const file of files) this.emitFile({ type: 'asset', fileName: snoDataPath.slice(1) + file, source: readFileSync(new URL(file, snoSource)) }); },
  };
}

export default defineConfig({
  plugins: [react(), snoDisplayData()],
  server: { proxy: { '/api': `http://127.0.0.1:${process.env.RECRUITMENT_API_PORT || '18087'}` } },
});

/**
 * Multimodal Context Types & Ingestion Schema (TASK-3.6).
 */

export interface ContextSummaryJSON {
  core_narrative: string;
  visual_style: string;
  key_entities: string[];
  pacing: string;
  themes: string[];
}

export type ContextSourceType = 'pdf' | 'docx' | 'pptx' | 'html' | 'url' | 'video' | 'audio' | string;

export interface ContextArtifactItem {
  id: string;
  project_id: string;
  content_hash: string;
  source_type: ContextSourceType;
  original_filename: string;
  storage_path: string;
  extracted_markdown?: string | null;
  summary_json?: ContextSummaryJSON | null;
  cached?: boolean;
}

export type IngestionStep = 'idle' | 'hashing' | 'uploading' | 'parsing' | 'summarizing' | 'ready' | 'error';

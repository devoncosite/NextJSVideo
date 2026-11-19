'use client';

import React, { useState } from 'react';
import { X, Copy, Check, FileText, Film, Globe, Sparkles, Tag, Eye } from 'lucide-react';
import { ContextArtifactItem } from '@/types/context';

interface ArtifactViewerModalProps {
  artifact: ContextArtifactItem | null;
  isOpen: boolean;
  onClose: () => void;
}

export function ArtifactViewerModal({ artifact, isOpen, onClose }: ArtifactViewerModalProps) {
  const [activeTab, setActiveTab] = useState<'summary' | 'markdown'>('summary');
  const [copied, setCopied] = useState(false);

  if (!isOpen || !artifact) return null;

  const summary = artifact.summary_json;

  const handleCopyMarkdown = () => {
    if (artifact.extracted_markdown) {
      navigator.clipboard.writeText(artifact.extracted_markdown);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const getSourceBadge = (type: string) => {
    switch (type.toLowerCase()) {
      case 'video':
        return <span className="flex items-center gap-1 rounded-full bg-violet-100 px-2.5 py-0.5 text-xs font-medium text-violet-800 dark:bg-violet-950/60 dark:text-violet-300"><Film className="h-3 w-3" /> Video</span>;
      case 'url':
        return <span className="flex items-center gap-1 rounded-full bg-sky-100 px-2.5 py-0.5 text-xs font-medium text-sky-800 dark:bg-sky-950/60 dark:text-sky-300"><Globe className="h-3 w-3" /> Web Article</span>;
      default:
        return <span className="flex items-center gap-1 rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-medium text-amber-800 dark:bg-amber-950/60 dark:text-amber-300"><FileText className="h-3 w-3" /> {type.toUpperCase()}</span>;
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-xs">
      <div className="flex max-h-[88vh] w-full max-w-3xl flex-col rounded-2xl border border-slate-200 bg-white shadow-2xl dark:border-slate-800 dark:bg-slate-900">
        {/* Header */}
        <div className="flex items-start justify-between border-b border-slate-100 p-5 dark:border-slate-800">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-semibold text-slate-900 dark:text-white">
                {artifact.original_filename}
              </h2>
              {getSourceBadge(artifact.source_type)}
            </div>
            <p className="mt-1 font-mono text-[11px] text-slate-500">
              SHA-256: {artifact.content_hash}
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-slate-800 dark:hover:text-slate-200"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="flex border-b border-slate-100 px-5 dark:border-slate-800">
          <button
            onClick={() => setActiveTab('summary')}
            className={`flex items-center gap-1.5 border-b-2 py-3 text-xs font-medium transition-colors ${
              activeTab === 'summary'
                ? 'border-indigo-600 text-indigo-600 dark:border-indigo-400 dark:text-indigo-400'
                : 'border-transparent text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200'
            }`}
          >
            <Sparkles className="h-3.5 w-3.5" />
            Multimodal Intelligence & Production Bible
          </button>
          <button
            onClick={() => setActiveTab('markdown')}
            className={`flex items-center gap-1.5 border-b-2 py-3 text-xs font-medium transition-colors ${
              activeTab === 'markdown'
                ? 'border-indigo-600 text-indigo-600 dark:border-indigo-400 dark:text-indigo-400'
                : 'border-transparent text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200'
            }`}
          >
            <FileText className="h-3.5 w-3.5" />
            Extracted Document Markdown
          </button>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-5 text-xs text-slate-700 dark:text-slate-300">
          {activeTab === 'summary' ? (
            <div className="space-y-4">
              {summary ? (
                <>
                  {/* Core Narrative */}
                  <div className="rounded-xl border border-slate-100 bg-slate-50/50 p-4 dark:border-slate-800/80 dark:bg-slate-800/30">
                    <h3 className="font-semibold text-slate-900 dark:text-white">Core Narrative & Premises</h3>
                    <p className="mt-1.5 leading-relaxed text-slate-600 dark:text-slate-300">
                      {summary.core_narrative}
                    </p>
                  </div>

                  {/* Visual Style & Aesthetic */}
                  <div className="rounded-xl border border-slate-100 bg-slate-50/50 p-4 dark:border-slate-800/80 dark:bg-slate-800/30">
                    <h3 className="font-semibold text-slate-900 dark:text-white">Observed Visual Style & Lighting</h3>
                    <p className="mt-1.5 leading-relaxed text-slate-600 dark:text-slate-300">
                      {summary.visual_style}
                    </p>
                  </div>

                  {/* Detected Key Entities */}
                  <div>
                    <h3 className="mb-2 font-semibold text-slate-900 dark:text-white">Detected Production Entities</h3>
                    <div className="flex flex-wrap gap-1.5">
                      {summary.key_entities && summary.key_entities.length > 0 ? (
                        summary.key_entities.map((entity, idx) => (
                          <span
                            key={idx}
                            className="flex items-center gap-1 rounded-md bg-indigo-50 px-2 py-1 text-[11px] font-medium text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300"
                          >
                            <Tag className="h-2.5 w-2.5" />
                            {entity}
                          </span>
                        ))
                      ) : (
                        <span className="text-slate-400">No explicit entities detected</span>
                      )}
                    </div>
                  </div>

                  {/* Pacing & Rhythm */}
                  <div className="rounded-xl border border-slate-100 bg-slate-50/50 p-4 dark:border-slate-800/80 dark:bg-slate-800/30">
                    <h3 className="font-semibold text-slate-900 dark:text-white">Pacing & Acoustic Mood</h3>
                    <p className="mt-1.5 leading-relaxed text-slate-600 dark:text-slate-300">
                      {summary.pacing}
                    </p>
                  </div>
                </>
              ) : (
                <div className="p-8 text-center text-slate-400">
                  No structured summary generated yet for this artifact.
                </div>
              )}
            </div>
          ) : (
            <div className="space-y-3">
              <div className="flex justify-end">
                <button
                  onClick={handleCopyMarkdown}
                  className="flex items-center gap-1 rounded-md border border-slate-200 px-2.5 py-1 text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
                >
                  {copied ? <Check className="h-3.5 w-3.5 text-emerald-600" /> : <Copy className="h-3.5 w-3.5" />}
                  {copied ? 'Copied' : 'Copy Markdown'}
                </button>
              </div>
              <pre className="max-h-96 overflow-auto rounded-lg bg-slate-900 p-4 font-mono text-xs text-slate-100 dark:bg-slate-950">
                {artifact.extracted_markdown || 'No extracted markdown text available.'}
              </pre>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between border-t border-slate-100 p-4 text-[11px] text-slate-500 dark:border-slate-800">
          <span>Storage: <code className="font-mono">{artifact.storage_path}</code></span>
          <button
            onClick={onClose}
            className="rounded-lg bg-slate-100 px-3 py-1.5 font-medium text-slate-700 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

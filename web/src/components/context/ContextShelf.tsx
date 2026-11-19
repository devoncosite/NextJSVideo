'use client';

import React, { useState, useEffect } from 'react';
import {
  FileText,
  Film,
  Globe,
  Plus,
  Trash2,
  Eye,
  Layers,
  ChevronRight,
  Database,
  CheckCircle2,
} from 'lucide-react';
import { ContextArtifactItem } from '@/types/context';
import { UploadDropzone } from './UploadDropzone';
import { ArtifactViewerModal } from './ArtifactViewerModal';

interface ContextShelfProps {
  projectId: string;
  isOpen: boolean;
  onToggle: () => void;
}

export function ContextShelf({ projectId, isOpen, onToggle }: ContextShelfProps) {
  const [artifacts, setArtifacts] = useState<ContextArtifactItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [showDropzone, setShowDropzone] = useState(false);
  const [selectedArtifact, setSelectedArtifact] = useState<ContextArtifactItem | null>(null);
  const [viewerOpen, setViewerOpen] = useState(false);

  const fetchArtifacts = async () => {
    try {
      setLoading(true);
      const res = await fetch(`/api/v1/projects/${projectId}/context`);
      if (res.ok) {
        const data = await res.json();
        setArtifacts(data);
      }
    } catch (err) {
      console.error('Failed to load project context artifacts:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (projectId) {
      fetchArtifacts();
    }
  }, [projectId]);

  const handleArtifactUploaded = (newArtifact: ContextArtifactItem) => {
    setArtifacts((prev) => {
      const exists = prev.some((a) => a.id === newArtifact.id);
      if (exists) return prev;
      return [newArtifact, ...prev];
    });
    setShowDropzone(false);
  };

  const handleDelete = async (artifactId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      const res = await fetch(`/api/v1/projects/${projectId}/context/${artifactId}`, {
        method: 'DELETE',
      });
      if (res.ok) {
        setArtifacts((prev) => prev.filter((a) => a.id !== artifactId));
      }
    } catch (err) {
      console.error('Failed to delete artifact:', err);
    }
  };

  const openViewer = (artifact: ContextArtifactItem) => {
    setSelectedArtifact(artifact);
    setViewerOpen(true);
  };

  const getSourceIcon = (type: string) => {
    switch (type.toLowerCase()) {
      case 'video':
        return <Film className="h-4 w-4 text-violet-500" />;
      case 'url':
        return <Globe className="h-4 w-4 text-sky-500" />;
      default:
        return <FileText className="h-4 w-4 text-amber-500" />;
    }
  };

  return (
    <>
      {/* Slide-over Shelf Container */}
      <div
        className={`fixed inset-y-0 right-0 z-40 flex w-96 flex-col border-l border-slate-200 bg-slate-50/95 shadow-xl backdrop-blur-md transition-transform duration-300 dark:border-slate-800 dark:bg-slate-900/95 ${
          isOpen ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        {/* Shelf Header */}
        <div className="flex items-center justify-between border-b border-slate-200 p-4 dark:border-slate-800">
          <div className="flex items-center gap-2">
            <Database className="h-4 w-4 text-indigo-600 dark:text-indigo-400" />
            <h2 className="text-sm font-semibold text-slate-900 dark:text-white">
              Multimodal Context Shelf
            </h2>
            <span className="rounded-full bg-slate-200 px-2 py-0.5 text-[10px] font-semibold text-slate-700 dark:bg-slate-800 dark:text-slate-300">
              {artifacts.length}
            </span>
          </div>

          <div className="flex items-center gap-1">
            <button
              onClick={() => setShowDropzone(!showDropzone)}
              className="flex items-center gap-1 rounded-lg bg-indigo-600 px-2.5 py-1 text-xs font-medium text-white transition-colors hover:bg-indigo-700"
            >
              <Plus className="h-3.5 w-3.5" />
              Add
            </button>
            <button
              onClick={onToggle}
              className="rounded-lg p-1 text-slate-400 hover:bg-slate-200 hover:text-slate-700 dark:hover:bg-slate-800 dark:hover:text-slate-200"
            >
              <ChevronRight className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* Ingestion Dropzone Drawer */}
        {showDropzone && (
          <div className="border-b border-slate-200 p-4 dark:border-slate-800">
            <UploadDropzone
              projectId={projectId}
              onArtifactUploaded={handleArtifactUploaded}
            />
          </div>
        )}

        {/* Artifact List */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {loading ? (
            <div className="p-8 text-center text-xs text-slate-500">Loading context artifacts...</div>
          ) : artifacts.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-200 p-8 text-center dark:border-slate-800">
              <Layers className="mx-auto h-8 w-8 text-slate-400" />
              <h3 className="mt-2 text-xs font-medium text-slate-800 dark:text-slate-200">
                No Context Artifacts
              </h3>
              <p className="mt-1 text-[11px] text-slate-500">
                Upload production bibles, character briefs, or web references to guide AI generation.
              </p>
              <button
                onClick={() => setShowDropzone(true)}
                className="mt-3 inline-flex items-center gap-1 text-xs font-medium text-indigo-600 hover:underline dark:text-indigo-400"
              >
                <Plus className="h-3 w-3" /> Add first reference
              </button>
            </div>
          ) : (
            artifacts.map((art) => (
              <div
                key={art.id}
                onClick={() => openViewer(art)}
                className="group relative cursor-pointer rounded-xl border border-slate-200 bg-white p-3.5 shadow-2xs transition-all hover:border-indigo-300 hover:shadow-xs dark:border-slate-800 dark:bg-slate-950 dark:hover:border-indigo-700"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-slate-100 dark:bg-slate-800">
                      {getSourceIcon(art.source_type)}
                    </div>
                    <div className="overflow-hidden">
                      <h4 className="truncate text-xs font-semibold text-slate-900 dark:text-white">
                        {art.original_filename}
                      </h4>
                      <p className="font-mono text-[10px] text-slate-400 truncate">
                        {art.content_hash.slice(0, 16)}...
                      </p>
                    </div>
                  </div>

                  <button
                    onClick={(e) => handleDelete(art.id, e)}
                    className="opacity-0 group-hover:opacity-100 rounded-md p-1 text-slate-400 hover:bg-rose-50 hover:text-rose-600 transition-opacity dark:hover:bg-rose-950/40"
                    title="Unlink artifact"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>

                {art.summary_json && (
                  <div className="mt-2.5 space-y-1.5 text-[11px] text-slate-600 dark:text-slate-400">
                    <p className="line-clamp-2 leading-relaxed">
                      {art.summary_json.core_narrative}
                    </p>

                    {art.summary_json.key_entities && art.summary_json.key_entities.length > 0 && (
                      <div className="flex flex-wrap gap-1 pt-1">
                        {art.summary_json.key_entities.slice(0, 3).map((ent, idx) => (
                          <span
                            key={idx}
                            className="rounded-sm bg-slate-100 px-1.5 py-0.5 text-[9px] font-medium text-slate-700 dark:bg-slate-800 dark:text-slate-300"
                          >
                            {ent}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                <div className="mt-2.5 flex items-center justify-between border-t border-slate-100 pt-2 text-[10px] text-slate-400 dark:border-slate-800/80">
                  <span className="flex items-center gap-1 text-emerald-600 dark:text-emerald-400">
                    <CheckCircle2 className="h-3 w-3" /> Ready
                  </span>
                  <span className="flex items-center gap-1 text-indigo-600 dark:text-indigo-400 group-hover:underline">
                    <Eye className="h-3 w-3" /> View Summary
                  </span>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Artifact Viewer Modal */}
      <ArtifactViewerModal
        artifact={selectedArtifact}
        isOpen={viewerOpen}
        onClose={() => setViewerOpen(false)}
      />
    </>
  );
}

'use client';

import React, { useState, useRef, ChangeEvent, DragEvent } from 'react';
import { Upload, Link2, FileCheck, Loader2, Sparkles, AlertCircle, ShieldCheck } from 'lucide-react';
import { ContextArtifactItem, IngestionStep } from '@/types/context';

interface UploadDropzoneProps {
  projectId: string;
  onArtifactUploaded: (artifact: ContextArtifactItem) => void;
  onError?: (error: string) => void;
}

export function UploadDropzone({ projectId, onArtifactUploaded, onError }: UploadDropzoneProps) {
  const [activeTab, setActiveTab] = useState<'file' | 'url'>('file');
  const [isDragging, setIsDragging] = useState(false);
  const [step, setStep] = useState<IngestionStep>('idle');
  const [computedHash, setComputedHash] = useState<string | null>(null);
  const [progressPercent, setProgressPercent] = useState<number>(0);
  const [statusMessage, setStatusMessage] = useState<string>('');
  const [urlInput, setUrlInput] = useState<string>('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Client-side SHA-256 calculation using Web Crypto API
  const computeClientSha256 = async (file: File): Promise<string> => {
    const buffer = await file.arrayBuffer();
    const hashBuffer = await crypto.subtle.digest('SHA-256', buffer);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map((b) => b.toString(16).padStart(2, '0')).join('');
  };

  const handleFile = async (file: File) => {
    try {
      setStep('hashing');
      setProgressPercent(20);
      setStatusMessage('Computing SHA-256 content hash...');

      const sha = await computeClientSha256(file);
      setComputedHash(sha);

      setStep('uploading');
      setProgressPercent(45);
      setStatusMessage('Uploading to S3 / Cloudflare R2...');

      const formData = new FormData();
      formData.append('file', file);

      setStep('parsing');
      setProgressPercent(70);
      setStatusMessage('Extracting Markdown & tables (Docling / MarkItDown)...');

      const res = await fetch(`/api/v1/projects/${projectId}/context/upload`, {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `Upload failed with status ${res.status}`);
      }

      setStep('summarizing');
      setProgressPercent(90);
      setStatusMessage('Running Gemini Flash multimodal summary pass...');

      const artifact: ContextArtifactItem = await res.json();

      setStep('ready');
      setProgressPercent(100);
      setStatusMessage(artifact.cached ? 'Reused existing content-addressed artifact!' : 'Multimodal artifact ready!');
      onArtifactUploaded(artifact);

      setTimeout(() => {
        setStep('idle');
        setComputedHash(null);
        setProgressPercent(0);
        setStatusMessage('');
      }, 3000);
    } catch (err: any) {
      setStep('error');
      setStatusMessage(err.message || 'Failed to process document');
      if (onError) onError(err.message);
    }
  };

  const handleUrlSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!urlInput.trim()) return;

    try {
      setStep('uploading');
      setProgressPercent(30);
      setStatusMessage('Validating SSRF guards & crawling URL...');

      const res = await fetch(`/api/v1/projects/${projectId}/context/url`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: urlInput.trim() }),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `URL ingestion failed (${res.status})`);
      }

      setStep('summarizing');
      setProgressPercent(80);
      setStatusMessage('Extracting article markdown & visual cues...');

      const artifact: ContextArtifactItem = await res.json();

      setStep('ready');
      setProgressPercent(100);
      setStatusMessage('Web context ingested successfully!');
      setUrlInput('');
      onArtifactUploaded(artifact);

      setTimeout(() => {
        setStep('idle');
        setProgressPercent(0);
        setStatusMessage('');
      }, 3000);
    } catch (err: any) {
      setStep('error');
      setStatusMessage(err.message || 'Failed to crawl URL');
      if (onError) onError(err.message);
    }
  };

  const onDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const onDragLeave = () => {
    setIsDragging(false);
  };

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFile(e.dataTransfer.files[0]);
    }
  };

  const onFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFile(e.target.files[0]);
    }
  };

  const isProcessing = step !== 'idle' && step !== 'ready' && step !== 'error';

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-xs dark:border-slate-800 dark:bg-slate-900">
      {/* Tab Switcher */}
      <div className="mb-3 flex gap-2 border-b border-slate-100 pb-2 dark:border-slate-800">
        <button
          type="button"
          onClick={() => setActiveTab('file')}
          className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
            activeTab === 'file'
              ? 'bg-indigo-50 text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300'
              : 'text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-200'
          }`}
        >
          <Upload className="h-3.5 w-3.5" />
          Upload Document / Media
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('url')}
          className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
            activeTab === 'url'
              ? 'bg-indigo-50 text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300'
              : 'text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-200'
          }`}
        >
          <Link2 className="h-3.5 w-3.5" />
          Ingest Web / Video URL
        </button>
      </div>

      {activeTab === 'file' ? (
        <div
          onDragOver={onDragOver}
          onDragLeave={onDragLeave}
          onDrop={onDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-6 text-center transition-all ${
            isDragging
              ? 'border-indigo-500 bg-indigo-50/50 dark:border-indigo-400 dark:bg-indigo-950/20'
              : 'border-slate-200 hover:border-slate-300 dark:border-slate-800 dark:hover:border-slate-700'
          }`}
        >
          <input
            ref={fileInputRef}
            type="file"
            className="hidden"
            accept=".pdf,.docx,.doc,.pptx,.ppt,.html,.txt,.md,.mp4,.mov,.mp3,.wav"
            onChange={onFileChange}
            disabled={isProcessing}
          />
          <div className="mb-2 flex h-10 w-10 items-center justify-center rounded-full bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300">
            {isProcessing ? (
              <Loader2 className="h-5 w-5 animate-spin text-indigo-600" />
            ) : step === 'ready' ? (
              <FileCheck className="h-5 w-5 text-emerald-600" />
            ) : (
              <Upload className="h-5 w-5" />
            )}
          </div>
          <p className="text-sm font-medium text-slate-800 dark:text-slate-200">
            {isProcessing ? 'Ingesting reference material...' : 'Drag & drop document or video'}
          </p>
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
            PDF, DOCX, PPTX, HTML, MP4, MP3 • Content-addressed SHA-256 deduplicated
          </p>
        </div>
      ) : (
        <form onSubmit={handleUrlSubmit} className="space-y-3">
          <div className="flex gap-2">
            <input
              type="url"
              placeholder="https://example.com/article or YouTube video URL"
              value={urlInput}
              onChange={(e) => setUrlInput(e.target.value)}
              disabled={isProcessing}
              required
              className="flex-1 rounded-lg border border-slate-200 px-3 py-2 text-xs focus:border-indigo-500 focus:outline-hidden dark:border-slate-800 dark:bg-slate-950 dark:text-slate-200"
            />
            <button
              type="submit"
              disabled={isProcessing || !urlInput.trim()}
              className="flex items-center gap-1.5 rounded-lg bg-indigo-600 px-4 py-2 text-xs font-medium text-white transition-opacity hover:bg-indigo-700 disabled:opacity-50"
            >
              {isProcessing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
              Ingest
            </button>
          </div>
          <div className="flex items-center gap-1.5 text-[11px] text-slate-500">
            <ShieldCheck className="h-3.5 w-3.5 text-emerald-600" />
            Protected by SSRF firewall & Crawl4AI article cleaner
          </div>
        </form>
      )}

      {/* Progress & Status Indicators */}
      {step !== 'idle' && (
        <div className="mt-3 space-y-1.5 rounded-lg bg-slate-50 p-2.5 text-xs dark:bg-slate-800/60">
          <div className="flex items-center justify-between text-slate-600 dark:text-slate-300">
            <span className="flex items-center gap-1.5">
              {step === 'error' ? (
                <AlertCircle className="h-3.5 w-3.5 text-rose-500" />
              ) : step === 'ready' ? (
                <FileCheck className="h-3.5 w-3.5 text-emerald-500" />
              ) : (
                <Loader2 className="h-3.5 w-3.5 animate-spin text-indigo-500" />
              )}
              {statusMessage}
            </span>
            <span className="font-mono text-[10px] text-slate-500">{progressPercent}%</span>
          </div>

          <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
            <div
              className={`h-full transition-all duration-300 ${
                step === 'error' ? 'bg-rose-500' : step === 'ready' ? 'bg-emerald-500' : 'bg-indigo-600'
              }`}
              style={{ width: `${progressPercent}%` }}
            />
          </div>

          {computedHash && (
            <div className="flex items-center gap-1 font-mono text-[10px] text-slate-500">
              <span className="text-slate-400">SHA-256:</span>
              <span className="truncate">{computedHash}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

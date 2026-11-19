'use client';

import React, { useState, useEffect } from 'react';
import {
  Sparkles,
  RefreshCw,
  AlertCircle,
  Clock,
  Maximize2,
  CheckCircle2,
  Film,
  Volume2,
} from 'lucide-react';
import { AssetStatus } from '@/types/manifest';
import { VariantPicker } from './VariantPicker';

interface GenerationCardProps {
  title: string;
  status: AssetStatus;
  progressPercent?: number;
  prompt: string;
  selectedAssetUrl?: string | null;
  variants?: string[];
  error?: string | null;
  mediaType?: 'image' | 'video' | 'audio';
  aspectRatio?: '16:9' | '9:16' | '1:1';
  badgeText?: string;
  onGenerate?: () => void;
  onRegenerate?: () => void;
  onPromptChange?: (newPrompt: string) => void;
  onSelectVariant?: (url: string) => void;
}

export function GenerationCard({
  title,
  status,
  progressPercent = 0,
  prompt,
  selectedAssetUrl,
  variants = [],
  error,
  mediaType = 'image',
  aspectRatio = '16:9',
  badgeText,
  onGenerate,
  onRegenerate,
  onPromptChange,
  onSelectVariant,
}: GenerationCardProps) {
  const [isEditingPrompt, setIsEditingPrompt] = useState(false);
  const [localPrompt, setLocalPrompt] = useState(prompt);
  const [elapsedSec, setElapsedSec] = useState(0);

  useEffect(() => {
    setLocalPrompt(prompt);
  }, [prompt]);

  useEffect(() => {
    let timer: NodeJS.Timeout | null = null;
    if (status === 'generating' || status === 'queued') {
      setElapsedSec(0);
      timer = setInterval(() => {
        setElapsedSec((prev) => prev + 1);
      }, 1000);
    }
    return () => {
      if (timer) clearInterval(timer);
    };
  }, [status]);

  const handleSavePrompt = () => {
    setIsEditingPrompt(false);
    if (onPromptChange && localPrompt !== prompt) {
      onPromptChange(localPrompt);
    }
  };

  const getAspectClass = () => {
    switch (aspectRatio) {
      case '9:16':
        return 'aspect-[9/16]';
      case '1:1':
        return 'aspect-square';
      case '16:9':
      default:
        return 'aspect-video';
    }
  };

  return (
    <div className="flex flex-col bg-zinc-950 border border-zinc-800 rounded-xl overflow-hidden shadow-lg transition-all hover:border-zinc-700">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-zinc-800/80 bg-zinc-900/60">
        <div className="flex items-center gap-2">
          {mediaType === 'video' ? (
            <Film className="w-4 h-4 text-sky-400" />
          ) : mediaType === 'audio' ? (
            <Volume2 className="w-4 h-4 text-amber-400" />
          ) : (
            <Sparkles className="w-4 h-4 text-emerald-400" />
          )}
          <span className="text-sm font-medium text-zinc-200">{title}</span>
        </div>

        <div className="flex items-center gap-2">
          {badgeText && (
            <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-zinc-800 text-zinc-300 border border-zinc-700">
              {badgeText}
            </span>
          )}

          {/* Status Badge */}
          {status === 'idle' && (
            <span className="text-[10px] uppercase font-bold px-2 py-0.5 rounded bg-zinc-800 text-zinc-400">
              Idle
            </span>
          )}
          {status === 'queued' && (
            <span className="text-[10px] uppercase font-bold px-2 py-0.5 rounded bg-amber-950/60 text-amber-400 border border-amber-800/50 flex items-center gap-1 animate-pulse">
              <Clock className="w-3 h-3" /> Queued
            </span>
          )}
          {status === 'generating' && (
            <span className="text-[10px] uppercase font-bold px-2 py-0.5 rounded bg-sky-950/60 text-sky-400 border border-sky-800/50 flex items-center gap-1">
              <RefreshCw className="w-3 h-3 animate-spin" /> Generating
            </span>
          )}
          {status === 'completed' && (
            <span className="text-[10px] uppercase font-bold px-2 py-0.5 rounded bg-emerald-950/60 text-emerald-400 border border-emerald-800/50 flex items-center gap-1">
              <CheckCircle2 className="w-3 h-3" /> Ready
            </span>
          )}
          {status === 'failed' && (
            <span className="text-[10px] uppercase font-bold px-2 py-0.5 rounded bg-red-950/60 text-red-400 border border-red-800/50 flex items-center gap-1">
              <AlertCircle className="w-3 h-3" /> Failed
            </span>
          )}
        </div>
      </div>

      {/* Main Preview Container */}
      <div className={`relative w-full ${getAspectClass()} bg-zinc-900/90 flex items-center justify-center overflow-hidden`}>
        {/* IDLE STATE */}
        {status === 'idle' && (
          <div className="flex flex-col items-center justify-center p-6 text-center gap-3">
            <div className="w-12 h-12 rounded-full border-2 border-dashed border-zinc-700 flex items-center justify-center text-zinc-500">
              <Sparkles className="w-6 h-6 text-zinc-600" />
            </div>
            <p className="text-xs text-zinc-400 max-w-xs line-clamp-2">
              {prompt || 'No prompt specified yet. Configure parameters to start generation.'}
            </p>
            {onGenerate && (
              <button
                type="button"
                onClick={onGenerate}
                className="mt-1 px-4 py-1.5 text-xs font-semibold rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white transition-colors flex items-center gap-1.5 shadow-md shadow-emerald-950/50"
              >
                <Sparkles className="w-3.5 h-3.5" />
                Generate Now
              </button>
            )}
          </div>
        )}

        {/* QUEUED STATE */}
        {status === 'queued' && (
          <div className="flex flex-col items-center justify-center gap-3 p-6 text-center">
            <div className="relative">
              <div className="w-10 h-10 rounded-full border-2 border-amber-500/30 flex items-center justify-center">
                <Clock className="w-5 h-5 text-amber-400" />
              </div>
              <div className="absolute inset-0 rounded-full border border-amber-400 animate-ping opacity-25" />
            </div>
            <p className="text-xs font-medium text-amber-300">Queued in Dispatch Pipeline</p>
            <span className="text-[11px] text-zinc-400 font-mono">Elapsed: {elapsedSec}s</span>
          </div>
        )}

        {/* GENERATING STATE */}
        {status === 'generating' && (
          <div className="flex flex-col items-center justify-center gap-3 p-6 w-full max-w-xs text-center">
            <RefreshCw className="w-8 h-8 text-sky-400 animate-spin" />
            <div className="w-full bg-zinc-800 rounded-full h-2 overflow-hidden">
              <div
                className="bg-sky-500 h-full rounded-full transition-all duration-300"
                style={{ width: `${Math.max(progressPercent, 10)}%` }}
              />
            </div>
            <div className="flex items-center justify-between w-full text-[11px] text-zinc-400 font-mono">
              <span>{progressPercent}% completed</span>
              <span>{elapsedSec}s elapsed</span>
            </div>
          </div>
        )}

        {/* COMPLETED STATE */}
        {status === 'completed' && selectedAssetUrl && (
          <div className="relative w-full h-full group">
            {mediaType === 'image' && (
              <img
                src={selectedAssetUrl}
                alt={title}
                className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-[1.02]"
              />
            )}
            {mediaType === 'video' && (
              <video
                src={selectedAssetUrl}
                className="w-full h-full object-cover"
                controls
                playsInline
              />
            )}
            {mediaType === 'audio' && (
              <div className="flex flex-col items-center justify-center w-full h-full p-4 gap-3 bg-gradient-to-b from-zinc-900 to-zinc-950">
                <Volume2 className="w-10 h-10 text-amber-400" />
                <audio src={selectedAssetUrl} controls className="w-full max-w-xs" />
              </div>
            )}

            {/* Quick Action Overlay */}
            <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1.5 bg-black/60 backdrop-blur-md p-1 rounded-lg">
              {onRegenerate && (
                <button
                  type="button"
                  onClick={onRegenerate}
                  className="p-1.5 rounded hover:bg-zinc-800 text-zinc-200"
                  title="Regenerate"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          </div>
        )}

        {/* FAILED STATE */}
        {status === 'failed' && (
          <div className="flex flex-col items-center justify-center gap-2 p-6 text-center text-red-400">
            <AlertCircle className="w-8 h-8 text-red-500" />
            <p className="text-xs font-semibold">Generation Failed</p>
            <p className="text-[11px] text-zinc-400 max-w-xs line-clamp-2">
              {error || 'An unexpected error occurred during model inference.'}
            </p>
            {onRegenerate && (
              <button
                type="button"
                onClick={onRegenerate}
                className="mt-2 px-3 py-1 text-xs font-medium rounded-md bg-red-900/60 hover:bg-red-800 text-red-200 border border-red-700/60 flex items-center gap-1.5"
              >
                <RefreshCw className="w-3 h-3" /> Retry Generation
              </button>
            )}
          </div>
        )}
      </div>

      {/* Footer & Controls */}
      <div className="p-3 bg-zinc-950 flex flex-col gap-2">
        {/* Prompt Row */}
        {isEditingPrompt ? (
          <div className="flex flex-col gap-1.5">
            <textarea
              value={localPrompt}
              onChange={(e) => setLocalPrompt(e.target.value)}
              className="w-full text-xs bg-zinc-900 border border-zinc-700 rounded-md p-2 text-zinc-200 focus:outline-none focus:border-emerald-500"
              rows={2}
            />
            <div className="flex justify-end gap-1.5">
              <button
                type="button"
                onClick={() => setIsEditingPrompt(false)}
                className="px-2 py-1 text-[11px] rounded bg-zinc-800 text-zinc-300"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleSavePrompt}
                className="px-2 py-1 text-[11px] rounded bg-emerald-600 text-white"
              >
                Save
              </button>
            </div>
          </div>
        ) : (
          <div
            onClick={() => onPromptChange && setIsEditingPrompt(true)}
            className={`text-xs text-zinc-400 line-clamp-2 ${
              onPromptChange ? 'cursor-pointer hover:text-zinc-200' : ''
            }`}
            title={prompt}
          >
            {prompt ? (
              <span>{prompt}</span>
            ) : (
              <span className="italic text-zinc-600">Click to set prompt...</span>
            )}
          </div>
        )}

        {/* Variants row if completed */}
        {status === 'completed' && variants.length > 0 && onSelectVariant && (
          <VariantPicker
            variants={variants}
            selectedUrl={selectedAssetUrl || null}
            onSelect={onSelectVariant}
            mediaType={mediaType}
          />
        )}
      </div>
    </div>
  );
}

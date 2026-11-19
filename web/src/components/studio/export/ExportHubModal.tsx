'use client';

import React, { useState } from 'react';
import { Download, X, Archive, Film, Smartphone, Check, Loader2 } from 'lucide-react';

interface ExportHubModalProps {
  projectId: string;
  isOpen: boolean;
  onClose: () => void;
  finalVideoUrl?: string | null;
  bundleZipUrl?: string | null;
  onExportZip: () => Promise<string | null>;
}

export function ExportHubModal({
  projectId,
  isOpen,
  onClose,
  finalVideoUrl,
  bundleZipUrl,
  onExportZip,
}: ExportHubModalProps) {
  const [isExporting, setIsExporting] = useState(false);
  const [activeZipUrl, setActiveZipUrl] = useState<string | null>(bundleZipUrl || null);
  const resolvedZipUrl = activeZipUrl || bundleZipUrl || null;

  if (!isOpen) return null;

  const handleCreateZip = async () => {
    setIsExporting(true);
    try {
      const url = await onExportZip();
      if (url) setActiveZipUrl(url);
    } catch (err) {
      console.error(err);
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4">
      <div className="bg-zinc-950 border border-zinc-800 rounded-3xl w-full max-w-2xl overflow-hidden shadow-2xl flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-800 bg-zinc-900/50">
          <div>
            <h2 className="text-lg font-bold text-zinc-100 flex items-center gap-2">
              <Film className="w-5 h-5 text-emerald-400" />
              Export & Delivery Hub
            </h2>
            <p className="text-xs text-zinc-400">
              Download transcoded presets or package all project assets into an archive.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 flex flex-col gap-6">
          {/* Transcoded Presets Grid */}
          <div className="flex flex-col gap-3">
            <span className="text-xs font-bold uppercase tracking-wider text-zinc-400">
              Video Master Presets
            </span>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {/* Preset 1: Web Master */}
              <div className="flex flex-col justify-between p-4 rounded-xl bg-zinc-900 border border-zinc-800">
                <div className="flex flex-col gap-1">
                  <span className="font-semibold text-xs text-zinc-200">Web Master (1080p)</span>
                  <span className="text-[11px] text-zinc-500">H.264 / AAC (-14 LUFS)</span>
                </div>
                {finalVideoUrl ? (
                  <a
                    href={finalVideoUrl}
                    download="master_1080p.mp4"
                    className="mt-3 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors"
                  >
                    <Download className="w-3.5 h-3.5" /> Download
                  </a>
                ) : (
                  <span className="mt-3 text-[11px] text-zinc-600 italic">Render master first</span>
                )}
              </div>

              {/* Preset 2: ProRes 422 HQ */}
              <div className="flex flex-col justify-between p-4 rounded-xl bg-zinc-900 border border-zinc-800">
                <div className="flex flex-col gap-1">
                  <span className="font-semibold text-xs text-zinc-200">ProRes 422 HQ</span>
                  <span className="text-[11px] text-zinc-500">Uncompressed NLE MOV</span>
                </div>
                {finalVideoUrl ? (
                  <a
                    href={finalVideoUrl}
                    download="master_prores.mov"
                    className="mt-3 px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors"
                  >
                    <Download className="w-3.5 h-3.5" /> QuickTime
                  </a>
                ) : (
                  <span className="mt-3 text-[11px] text-zinc-600 italic">Render master first</span>
                )}
              </div>

              {/* Preset 3: Vertical 9:16 Social */}
              <div className="flex flex-col justify-between p-4 rounded-xl bg-zinc-900 border border-zinc-800">
                <div className="flex flex-col gap-1">
                  <span className="font-semibold text-xs text-zinc-200">Vertical Social (9:16)</span>
                  <span className="text-[11px] text-zinc-500">TikTok / Reels / Shorts</span>
                </div>
                {finalVideoUrl ? (
                  <a
                    href={finalVideoUrl}
                    download="social_9_16.mp4"
                    className="mt-3 px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors"
                  >
                    <Smartphone className="w-3.5 h-3.5" /> Social Crop
                  </a>
                ) : (
                  <span className="mt-3 text-[11px] text-zinc-600 italic">Render master first</span>
                )}
              </div>
            </div>
          </div>

          {/* Full Project ZIP Bundle Card */}
          <div className="p-5 rounded-2xl bg-gradient-to-br from-emerald-950/40 via-zinc-900 to-zinc-950 border border-emerald-900/60 shadow-lg flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Archive className="w-5 h-5 text-emerald-400" />
                <span className="font-bold text-sm text-zinc-100">
                  Full Project Production Archive (.zip)
                </span>
              </div>
              {resolvedZipUrl && (
                <span className="text-[11px] text-emerald-400 font-semibold flex items-center gap-1">
                  <Check className="w-3.5 h-3.5" /> Archive Ready
                </span>
              )}
            </div>

            <p className="text-xs text-zinc-300 leading-relaxed">
              Packages <code>project.json</code> (Master JSON Manifest), character 360° sheets, anchor
              keyframes, raw audio tracks, <code>.ass</code> & <code>.srt</code> subtitles, and final
              renders into an offline portable production bundle.
            </p>

            <div className="flex items-center gap-3 pt-2">
              <button
                type="button"
                onClick={handleCreateZip}
                disabled={isExporting}
                className="px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-semibold text-xs flex items-center gap-2 shadow-lg shadow-emerald-950/50 transition-all"
              >
                {isExporting ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" /> Packaging ZIP Archive...
                  </>
                ) : (
                  <>
                    <Archive className="w-4 h-4" /> Package Full Production ZIP
                  </>
                )}
              </button>

              {resolvedZipUrl && (
                <a
                  href={resolvedZipUrl}
                  download={`cineforge_${projectId}.zip`}
                  className="px-5 py-2.5 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-emerald-300 font-semibold text-xs flex items-center gap-2 transition-colors border border-zinc-700"
                >
                  <Download className="w-4 h-4" /> Download ZIP Bundle
                </a>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

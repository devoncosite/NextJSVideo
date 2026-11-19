'use client';

import React, { useState } from 'react';
import { Eye, Check, ChevronLeft, ChevronRight } from 'lucide-react';

interface TurnaroundViewerProps {
  name: string;
  variants: string[];
  selectedUrl: string | null;
  onLockVariant: (url: string) => void;
}

export function TurnaroundViewer({
  name,
  variants,
  selectedUrl,
  onLockVariant,
}: TurnaroundViewerProps) {
  const [activeIndex, setActiveIndex] = useState(0);

  if (!variants || variants.length === 0) return null;

  const currentUrl = variants[activeIndex] || selectedUrl || variants[0];
  const isLocked = selectedUrl === currentUrl;

  const handlePrev = () => {
    setActiveIndex((prev) => (prev === 0 ? variants.length - 1 : prev - 1));
  };

  const handleNext = () => {
    setActiveIndex((prev) => (prev === variants.length - 1 ? 0 : prev + 1));
  };

  return (
    <div className="flex flex-col bg-zinc-950 border border-zinc-800 rounded-xl overflow-hidden shadow-lg">
      <div className="flex items-center justify-between px-4 py-2 bg-zinc-900 border-b border-zinc-800">
        <span className="text-xs font-semibold text-zinc-200">{name} (360° Sheet)</span>
        <span className="text-[10px] text-zinc-400 font-mono">
          Variant {activeIndex + 1} of {variants.length}
        </span>
      </div>

      {/* Main Viewport */}
      <div className="relative aspect-video bg-zinc-900 flex items-center justify-center overflow-hidden group">
        <img
          src={currentUrl}
          alt={`${name} variant`}
          className="w-full h-full object-cover"
        />

        {/* Carousel controls */}
        {variants.length > 1 && (
          <>
            <button
              type="button"
              onClick={handlePrev}
              className="absolute left-2 top-1/2 -translate-y-1/2 p-1.5 rounded-full bg-black/60 hover:bg-black text-white backdrop-blur-sm opacity-0 group-hover:opacity-100 transition-opacity"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button
              type="button"
              onClick={handleNext}
              className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 rounded-full bg-black/60 hover:bg-black text-white backdrop-blur-sm opacity-0 group-hover:opacity-100 transition-opacity"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </>
        )}
      </div>

      {/* Action Footer */}
      <div className="flex items-center justify-between p-3 bg-zinc-950 border-t border-zinc-800/80">
        <div className="flex items-center gap-1.5">
          {variants.map((v, idx) => (
            <button
              key={`${v}-${idx}`}
              type="button"
              onClick={() => setActiveIndex(idx)}
              className={`w-6 h-6 rounded border text-[10px] font-mono transition-colors ${
                activeIndex === idx
                  ? 'border-emerald-500 bg-emerald-950/60 text-emerald-400 font-bold'
                  : 'border-zinc-800 bg-zinc-900 text-zinc-400 hover:border-zinc-700'
              }`}
            >
              {idx + 1}
            </button>
          ))}
        </div>

        <button
          type="button"
          onClick={() => onLockVariant(currentUrl)}
          className={`px-3 py-1.5 rounded-md text-xs font-semibold flex items-center gap-1.5 transition-all ${
            isLocked
              ? 'bg-emerald-600 text-white cursor-default'
              : 'bg-zinc-800 hover:bg-zinc-700 text-zinc-200'
          }`}
        >
          <Check className="w-3.5 h-3.5" />
          {isLocked ? 'Locked' : 'Lock Selected'}
        </button>
      </div>
    </div>
  );
}

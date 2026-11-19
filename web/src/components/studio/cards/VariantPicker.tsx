'use client';

import React from 'react';
import { Check } from 'lucide-react';

interface VariantPickerProps {
  variants: string[];
  selectedUrl: string | null;
  onSelect: (url: string) => void;
  mediaType?: 'image' | 'video' | 'audio';
}

export function VariantPicker({
  variants,
  selectedUrl,
  onSelect,
  mediaType = 'image',
}: VariantPickerProps) {
  if (!variants || variants.length <= 1) return null;

  return (
    <div className="flex flex-col gap-1.5 mt-2">
      <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
        Candidate Variants ({variants.length})
      </span>
      <div className="flex items-center gap-2 overflow-x-auto pb-1">
        {variants.map((vUrl, idx) => {
          const isSelected = selectedUrl === vUrl;
          return (
            <button
              key={`${vUrl}-${idx}`}
              type="button"
              onClick={() => onSelect(vUrl)}
              className={`relative rounded-md overflow-hidden border-2 transition-all flex-shrink-0 w-16 h-12 bg-zinc-900 group ${
                isSelected
                  ? 'border-emerald-500 shadow-md shadow-emerald-950/40 ring-1 ring-emerald-500'
                  : 'border-zinc-700 hover:border-zinc-500 opacity-70 hover:opacity-100'
              }`}
            >
              {mediaType === 'image' && (
                <img
                  src={vUrl}
                  alt={`Variant ${idx + 1}`}
                  className="w-full h-full object-cover"
                />
              )}
              {mediaType === 'video' && (
                <video
                  src={vUrl}
                  className="w-full h-full object-cover pointer-events-none"
                  muted
                  playsInline
                />
              )}
              {mediaType === 'audio' && (
                <div className="w-full h-full flex items-center justify-center text-[10px] text-zinc-300 font-mono">
                  Audio {idx + 1}
                </div>
              )}
              {isSelected && (
                <div className="absolute top-0.5 right-0.5 bg-emerald-500 rounded-full p-0.5 text-black">
                  <Check className="w-2.5 h-2.5 stroke-[3]" />
                </div>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}

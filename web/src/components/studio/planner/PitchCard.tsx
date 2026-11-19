'use client';

import React from 'react';
import { Film, CheckCircle2 } from 'lucide-react';

export interface StoryPitchData {
  pitch_id: number;
  angle_title: string;
  hook: string;
  narrative_synopsis: string;
  tone_and_style: string;
  target_scene_count: number;
}

interface PitchCardProps {
  pitch: StoryPitchData;
  isSelected: boolean;
  onSelect: () => void;
}

export function PitchCard({ pitch, isSelected, onSelect }: PitchCardProps) {
  return (
    <div
      onClick={onSelect}
      className={`relative flex flex-col p-5 rounded-xl border-2 cursor-pointer transition-all ${
        isSelected
          ? 'bg-zinc-900 border-emerald-500 shadow-xl shadow-emerald-950/30'
          : 'bg-zinc-950 border-zinc-800 hover:border-zinc-700 hover:bg-zinc-900/60'
      }`}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div
            className={`w-7 h-7 rounded-lg flex items-center justify-center font-bold text-xs ${
              isSelected
                ? 'bg-emerald-500 text-black'
                : 'bg-zinc-800 text-zinc-300'
            }`}
          >
            #{pitch.pitch_id}
          </div>
          <h3 className="font-semibold text-sm text-zinc-100">{pitch.angle_title}</h3>
        </div>

        {isSelected && (
          <div className="flex items-center gap-1 text-emerald-400 text-xs font-semibold">
            <CheckCircle2 className="w-4 h-4" /> Selected
          </div>
        )}
      </div>

      {/* Hook */}
      <div className="mb-3 p-3 rounded-lg bg-zinc-900/80 border border-zinc-800/80">
        <span className="text-[10px] font-bold uppercase tracking-wider text-amber-400">
          Opening Hook
        </span>
        <p className="text-xs italic text-zinc-200 mt-1">"{pitch.hook}"</p>
      </div>

      {/* Synopsis */}
      <p className="text-xs text-zinc-400 leading-relaxed mb-4 flex-1">
        {pitch.narrative_synopsis}
      </p>

      {/* Footer metadata */}
      <div className="flex items-center justify-between pt-3 border-t border-zinc-800/60 text-[11px] text-zinc-400">
        <span className="truncate max-w-[200px]" title={pitch.tone_and_style}>
          <span className="text-zinc-500">Style:</span> {pitch.tone_and_style}
        </span>
        <span className="font-mono">{pitch.target_scene_count} Scenes</span>
      </div>
    </div>
  );
}

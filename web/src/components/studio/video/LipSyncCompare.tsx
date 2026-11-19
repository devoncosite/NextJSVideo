'use client';

import React, { useRef, useState } from 'react';
import { Play, Pause, SplitSquareVertical, Volume2 } from 'lucide-react';

interface LipSyncCompareProps {
  rawVideoUrl?: string | null;
  lipSyncedVideoUrl?: string | null;
  sceneNumber: number;
}

export function LipSyncCompare({
  rawVideoUrl,
  lipSyncedVideoUrl,
  sceneNumber,
}: LipSyncCompareProps) {
  const [sliderPosition, setSliderPosition] = useState(50);
  const [isPlaying, setIsPlaying] = useState(false);
  const rawVideoRef = useRef<HTMLVideoElement | null>(null);
  const lipVideoRef = useRef<HTMLVideoElement | null>(null);

  if (!rawVideoUrl && !lipSyncedVideoUrl) return null;

  const togglePlay = () => {
    if (rawVideoRef.current && lipVideoRef.current) {
      if (isPlaying) {
        rawVideoRef.current.pause();
        lipVideoRef.current.pause();
        setIsPlaying(false);
      } else {
        rawVideoRef.current.play();
        lipVideoRef.current.play();
        setIsPlaying(true);
      }
    }
  };

  const handleTimeUpdate = () => {
    if (rawVideoRef.current && lipVideoRef.current) {
      if (Math.abs(rawVideoRef.current.currentTime - lipVideoRef.current.currentTime) > 0.1) {
        lipVideoRef.current.currentTime = rawVideoRef.current.currentTime;
      }
    }
  };

  return (
    <div className="flex flex-col bg-zinc-950 border border-zinc-800 rounded-2xl overflow-hidden shadow-2xl">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 bg-zinc-900/80 border-b border-zinc-800">
        <div className="flex items-center gap-2">
          <SplitSquareVertical className="w-4 h-4 text-sky-400" />
          <span className="text-xs font-bold uppercase tracking-wider text-zinc-200">
            Scene #{sceneNumber}: Split Visual Comparison
          </span>
        </div>

        <div className="flex items-center gap-4 text-xs font-semibold">
          <span className="text-zinc-400">Raw Motion (Left)</span>
          <span className="text-zinc-600">vs</span>
          <span className="text-emerald-400">Lip-Synced Result (Right)</span>
        </div>
      </div>

      {/* Comparison Viewport with slider */}
      <div className="relative aspect-video w-full bg-black overflow-hidden select-none">
        {/* Right Video (Lip-Synced) */}
        {lipSyncedVideoUrl && (
          <video
            ref={lipVideoRef}
            src={lipSyncedVideoUrl}
            className="absolute inset-0 w-full h-full object-cover"
            loop
            muted={false}
            playsInline
          />
        )}

        {/* Left Video (Raw Video clipped with slider position) */}
        {rawVideoUrl && (
          <div
            className="absolute inset-0 overflow-hidden"
            style={{ width: `${sliderPosition}%` }}
          >
            <video
              ref={rawVideoRef}
              src={rawVideoUrl}
              onTimeUpdate={handleTimeUpdate}
              className="absolute inset-0 w-full h-full object-cover max-w-none"
              style={{ width: '100%', height: '100%' }}
              loop
              muted
              playsInline
            />
          </div>
        )}

        {/* Vertical Divider Line */}
        <div
          className="absolute top-0 bottom-0 w-0.5 bg-emerald-400 pointer-events-none shadow-lg shadow-emerald-500/50"
          style={{ left: `${sliderPosition}%` }}
        >
          <div className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-6 h-6 rounded-full bg-emerald-500 text-black flex items-center justify-center font-bold text-[10px] shadow-lg">
            ↔
          </div>
        </div>

        {/* Scrub Overlay Slider */}
        <input
          type="range"
          min="0"
          max="100"
          value={sliderPosition}
          onChange={(e) => setSliderPosition(Number(e.target.value))}
          className="absolute inset-0 opacity-0 cursor-ew-resize w-full h-full z-10"
        />
      </div>

      {/* Control Bar */}
      <div className="flex items-center justify-between p-3 bg-zinc-950 border-t border-zinc-800">
        <button
          type="button"
          onClick={togglePlay}
          className="px-4 py-1.5 rounded-lg bg-zinc-900 hover:bg-zinc-800 border border-zinc-700 text-zinc-200 text-xs font-semibold flex items-center gap-1.5 transition-colors"
        >
          {isPlaying ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
          {isPlaying ? 'Pause Comparison' : 'Play Synchronized'}
        </button>

        <span className="text-[11px] text-zinc-500 italic">
          Drag horizontally across the frame to inspect face tracking alignment.
        </span>
      </div>
    </div>
  );
}

'use client';

import React, { useEffect, useRef, useState } from 'react';
import { Play, Pause, Volume2, User, Mic } from 'lucide-react';

interface WaveformTrackProps {
  label: string;
  speaker?: string;
  text?: string;
  audioUrl?: string | null;
  startOffsetSec: number;
  endOffsetSec: number;
  totalDurationSec: number;
  waveColor?: string;
  progressColor?: string;
  onOffsetChange?: (start: number, end: number) => void;
}

export function WaveformTrack({
  label,
  speaker,
  text,
  audioUrl,
  startOffsetSec,
  endOffsetSec,
  totalDurationSec,
  waveColor = '#10b981',
  progressColor = '#059669',
  onOffsetChange,
}: WaveformTrackProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const wavesurferRef = useRef<any>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [duration, setDuration] = useState(endOffsetSec - startOffsetSec);

  useEffect(() => {
    let wsInstance: any = null;

    async function initWaveSurfer() {
      if (!containerRef.current || !audioUrl) return;

      try {
        const WaveSurferModule = await import('wavesurfer.js');
        const WaveSurfer = WaveSurferModule.default || WaveSurferModule;

        if (wavesurferRef.current) {
          wavesurferRef.current.destroy();
        }

        wsInstance = WaveSurfer.create({
          container: containerRef.current,
          waveColor: waveColor,
          progressColor: progressColor,
          cursorColor: '#f59e0b',
          barWidth: 2,
          barGap: 1,
          barRadius: 2,
          height: 48,
          normalize: true,
          url: audioUrl,
        });

        wsInstance.on('play', () => setIsPlaying(true));
        wsInstance.on('pause', () => setIsPlaying(false));
        wsInstance.on('ready', (d: number) => setDuration(d));

        wavesurferRef.current = wsInstance;
      } catch (err) {
        console.warn('WaveSurfer initialization error:', err);
      }
    }

    initWaveSurfer();

    return () => {
      if (wsInstance) {
        wsInstance.destroy();
      }
    };
  }, [audioUrl, waveColor, progressColor]);

  const togglePlay = () => {
    if (wavesurferRef.current) {
      wavesurferRef.current.playPause();
    }
  };

  const leftPercent = Math.min((startOffsetSec / (totalDurationSec || 1)) * 100, 100);
  const widthPercent = Math.min(
    ((endOffsetSec - startOffsetSec) / (totalDurationSec || 1)) * 100,
    100 - leftPercent
  );

  return (
    <div className="flex flex-col gap-2 p-3 bg-zinc-950 border border-zinc-800 rounded-xl">
      {/* Track Info Header */}
      <div className="flex items-center justify-between text-xs">
        <div className="flex items-center gap-2">
          {speaker ? (
            <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-zinc-900 border border-zinc-700 text-zinc-200 font-medium">
              <User className="w-3 h-3 text-emerald-400" />
              <span>{speaker}</span>
            </div>
          ) : (
            <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-zinc-900 border border-zinc-700 text-zinc-200 font-medium">
              <Mic className="w-3 h-3 text-sky-400" />
              <span>{label}</span>
            </div>
          )}

          {text && (
            <span className="italic text-zinc-400 truncate max-w-sm" title={text}>
              "{text}"
            </span>
          )}
        </div>

        <div className="flex items-center gap-2 font-mono text-[11px] text-zinc-400">
          <span>
            {startOffsetSec.toFixed(1)}s - {endOffsetSec.toFixed(1)}s
          </span>
          <span className="text-zinc-600">({(endOffsetSec - startOffsetSec).toFixed(1)}s)</span>
        </div>
      </div>

      {/* Visual Track Channel */}
      <div className="relative w-full h-14 bg-zinc-900/80 rounded-lg overflow-hidden border border-zinc-800 flex items-center px-2">
        {/* Play/Pause Button */}
        <button
          type="button"
          onClick={togglePlay}
          disabled={!audioUrl}
          className="mr-3 w-8 h-8 rounded-full bg-zinc-800 hover:bg-zinc-700 text-zinc-200 flex items-center justify-center flex-shrink-0 transition-colors disabled:opacity-40"
        >
          {isPlaying ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5 ml-0.5" />}
        </button>

        {/* WaveSurfer Container or Placeholder */}
        <div className="flex-1 relative h-12 flex items-center">
          {audioUrl ? (
            <div ref={containerRef} className="w-full" />
          ) : (
            <div className="w-full flex items-center justify-center text-zinc-600 text-xs italic">
              Audio track not yet synthesized.
            </div>
          )}
        </div>
      </div>

      {/* Timeline Offset Placement Bar */}
      <div className="relative w-full h-2 bg-zinc-900 rounded-full overflow-hidden">
        <div
          className="absolute h-full rounded-full transition-all"
          style={{
            left: `${leftPercent}%`,
            width: `${Math.max(widthPercent, 5)}%`,
            backgroundColor: waveColor,
          }}
        />
      </div>
    </div>
  );
}

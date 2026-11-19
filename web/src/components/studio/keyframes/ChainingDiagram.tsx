'use client';

import React from 'react';
import { ArrowRight, Link as LinkIcon, Sparkles } from 'lucide-react';
import { SceneNode } from '@/types/manifest';

interface ChainingDiagramProps {
  scenes: SceneNode[];
  outroEndFrame?: {
    prompt: string;
    selectedAssetUrl?: string | null;
  };
}

export function ChainingDiagram({ scenes, outroEndFrame }: ChainingDiagramProps) {
  if (!scenes || scenes.length === 0) return null;

  return (
    <div className="flex flex-col gap-3 p-5 bg-zinc-950 border border-zinc-800 rounded-2xl shadow-xl overflow-x-auto">
      <div className="flex items-center gap-2">
        <LinkIcon className="w-4 h-4 text-emerald-400" />
        <span className="text-xs font-bold uppercase tracking-wider text-zinc-200">
          Visual Frame Chaining Topology (Zero Morph Distortion)
        </span>
      </div>
      <p className="text-xs text-zinc-400">
        Each scene generates motion conditioned on its start keyframe and anchored by the subsequent scene's start keyframe.
      </p>

      {/* Reel */}
      <div className="flex items-center gap-3 pt-2 pb-2 min-w-max">
        {scenes.map((scene, idx) => {
          const isLast = idx === scenes.length - 1;
          const kfUrl = scene.keyframe.selectedAssetUrl;

          return (
            <React.Fragment key={scene.id}>
              {/* Scene Node */}
              <div className="flex flex-col gap-1.5 w-44 p-2.5 rounded-xl bg-zinc-900 border border-zinc-700/80">
                <div className="flex items-center justify-between text-[11px]">
                  <span className="font-bold text-zinc-300">Scene #{scene.sceneNumber}</span>
                  <span className="text-zinc-500 font-mono">
                    {scene.timestamp.startSec}s - {scene.timestamp.endSec}s
                  </span>
                </div>

                <div className="relative aspect-video rounded-lg overflow-hidden bg-zinc-950 border border-zinc-800 flex items-center justify-center">
                  {kfUrl ? (
                    <img src={kfUrl} alt={`Scene ${scene.sceneNumber}`} className="w-full h-full object-cover" />
                  ) : (
                    <Sparkles className="w-4 h-4 text-zinc-600" />
                  )}
                  <span className="absolute bottom-1 left-1 px-1.5 py-0.5 rounded bg-black/70 text-[9px] font-mono text-emerald-300">
                    Start Frame
                  </span>
                </div>

                <span className="text-[10px] text-zinc-400 line-clamp-1 truncate" title={scene.visualDescription}>
                  {scene.visualDescription}
                </span>
              </div>

              {/* Chaining Arrow */}
              <div className="flex flex-col items-center gap-1 text-zinc-600">
                <div className="text-[9px] font-mono uppercase tracking-widest text-emerald-500/80">
                  anchors
                </div>
                <ArrowRight className="w-4 h-4 text-emerald-500" />
              </div>
            </React.Fragment>
          );
        })}

        {/* Outro End Frame Node */}
        {outroEndFrame && (
          <div className="flex flex-col gap-1.5 w-44 p-2.5 rounded-xl bg-zinc-900 border border-emerald-900/60 shadow-md shadow-emerald-950/20">
            <div className="flex items-center justify-between text-[11px]">
              <span className="font-bold text-emerald-400">Outro Frame</span>
              <span className="text-zinc-500 font-mono">Final</span>
            </div>

            <div className="relative aspect-video rounded-lg overflow-hidden bg-zinc-950 border border-zinc-800 flex items-center justify-center">
              {outroEndFrame.selectedAssetUrl ? (
                <img src={outroEndFrame.selectedAssetUrl} alt="Outro End Frame" className="w-full h-full object-cover" />
              ) : (
                <Sparkles className="w-4 h-4 text-zinc-600" />
              )}
              <span className="absolute bottom-1 left-1 px-1.5 py-0.5 rounded bg-black/70 text-[9px] font-mono text-emerald-300">
                End Anchor
              </span>
            </div>

            <span className="text-[10px] text-zinc-400 line-clamp-1 truncate">
              {outroEndFrame.prompt || 'Closing shot'}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

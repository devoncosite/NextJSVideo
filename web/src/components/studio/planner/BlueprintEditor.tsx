'use client';

import React from 'react';
import { Camera, Clock, MessageSquare, ArrowRight, UserCheck } from 'lucide-react';
import { useStudioStore } from '@/store/studioStore';
import { SceneNode } from '@/types/manifest';

interface BlueprintEditorProps {
  onProceed: () => void;
}

export function BlueprintEditor({ onProceed }: BlueprintEditorProps) {
  const { manifest, updatePrompt } = useStudioStore();

  if (!manifest || !manifest.scenes || manifest.scenes.length === 0) {
    return null;
  }

  const { scenes, consistencies } = manifest;

  return (
    <div className="flex flex-col gap-6 mt-8 p-6 bg-zinc-950 border border-zinc-800 rounded-2xl shadow-xl">
      <div className="flex items-center justify-between border-b border-zinc-800 pb-4">
        <div>
          <h2 className="text-lg font-bold text-zinc-100 flex items-center gap-2">
            Story Blueprint & Scene Breakdown
          </h2>
          <p className="text-xs text-zinc-400 mt-0.5">
            Refine camera angles, timing, and dialogue lines before batch consistency generation.
          </p>
        </div>

        <button
          type="button"
          onClick={onProceed}
          className="px-5 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs flex items-center gap-2 shadow-lg shadow-emerald-950/40 transition-colors"
        >
          Lock Blueprint & Proceed to Stage 2
          <ArrowRight className="w-4 h-4" />
        </button>
      </div>

      {/* Consistency Preview Chips */}
      <div className="flex flex-col gap-2">
        <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
          Detected Consistency Entities ({consistencies.characters.length} Characters, {consistencies.objects.length} Objects)
        </span>
        <div className="flex flex-wrap gap-2">
          {consistencies.characters.map((char) => (
            <div
              key={char.id}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-zinc-900 border border-zinc-700 text-xs text-zinc-200"
            >
              <UserCheck className="w-3.5 h-3.5 text-emerald-400" />
              <span className="font-medium">{char.name}</span>
              <span className="text-[10px] text-zinc-400 font-mono">({char.role})</span>
            </div>
          ))}
          {consistencies.objects.map((obj) => (
            <div
              key={obj.id}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-zinc-900 border border-zinc-700 text-xs text-zinc-200"
            >
              <span className="text-xs">📦</span>
              <span className="font-medium">{obj.name}</span>
              <span className="text-[10px] text-zinc-400 font-mono">({obj.category})</span>
            </div>
          ))}
        </div>
      </div>

      {/* Scenes Table */}
      <div className="overflow-x-auto border border-zinc-800/80 rounded-xl">
        <table className="w-full text-left text-xs text-zinc-300">
          <thead className="bg-zinc-900/80 text-[11px] uppercase tracking-wider text-zinc-400 border-b border-zinc-800">
            <tr>
              <th className="p-3 w-16 text-center">Scene</th>
              <th className="p-3 w-28">Timing</th>
              <th className="p-3 w-48">Camera Spec</th>
              <th className="p-3">Visual Narrative & Keyframe</th>
              <th className="p-3 w-72">Dialogue & Audio</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800/60 bg-zinc-950">
            {scenes.map((scene: SceneNode, idx: number) => {
              const duration = scene.timestamp.endSec - scene.timestamp.startSec;
              return (
                <tr key={scene.id} className="hover:bg-zinc-900/40 transition-colors">
                  <td className="p-3 font-bold text-center text-zinc-400">
                    #{scene.sceneNumber}
                  </td>
                  <td className="p-3">
                    <div className="flex items-center gap-1 font-mono text-[11px] text-zinc-400">
                      <Clock className="w-3.5 h-3.5 text-zinc-500" />
                      <span>{scene.timestamp.startSec}s - {scene.timestamp.endSec}s</span>
                    </div>
                    <span className="text-[10px] text-zinc-500">({duration}s)</span>
                  </td>
                  <td className="p-3">
                    <div className="flex flex-col gap-0.5">
                      <span className="font-medium text-zinc-200 flex items-center gap-1">
                        <Camera className="w-3 h-3 text-sky-400" />
                        {scene.camera.angle}
                      </span>
                      <span className="text-zinc-400 text-[11px]">{scene.camera.movement}</span>
                      <span className="text-zinc-500 text-[10px]">{scene.camera.lens}</span>
                    </div>
                  </td>
                  <td className="p-3">
                    <p className="font-medium text-zinc-200 mb-1">{scene.visualDescription}</p>
                    <div className="p-2 rounded bg-zinc-900/90 border border-zinc-800/80">
                      <span className="text-[10px] font-semibold text-emerald-400 block mb-0.5">
                        Keyframe Prompt
                      </span>
                      <textarea
                        value={scene.keyframe.prompt}
                        onChange={(e) =>
                          updatePrompt(`/scenes/${idx}/keyframe/prompt`, e.target.value)
                        }
                        className="w-full bg-transparent text-[11px] text-zinc-300 focus:outline-none resize-none"
                        rows={2}
                      />
                    </div>
                  </td>
                  <td className="p-3">
                    {scene.audio.voiceover?.enabled && (
                      <div className="mb-2 p-1.5 rounded bg-zinc-900/60 border border-zinc-800 text-[11px]">
                        <span className="text-amber-400 font-semibold text-[10px] block">
                          Voiceover
                        </span>
                        <p className="italic text-zinc-300">"{scene.audio.voiceover.text}"</p>
                      </div>
                    )}
                    {scene.audio.dialogue?.length > 0 ? (
                      <div className="flex flex-col gap-1.5">
                        {scene.audio.dialogue.map((dlg, dIdx) => (
                          <div
                            key={dlg.id || dIdx}
                            className="p-1.5 rounded bg-zinc-900/80 border border-zinc-800 text-[11px]"
                          >
                            <span className="text-emerald-400 font-medium text-[10px]">
                              {dlg.speakerId}:
                            </span>
                            <p className="text-zinc-200">"{dlg.text}"</p>
                          </div>
                        ))}
                      </div>
                    ) : (
                      !scene.audio.voiceover?.enabled && (
                        <span className="text-[11px] text-zinc-600 italic">No dialogue</span>
                      )
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

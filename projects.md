I want to Create a fullstack nextjs web app (auth), by combining AI-Content-Studio and ContentMachine.

https://github.com/naqashafzal/AI-Content-Studio.git
https://github.com/Saganaki22/ContentMachine.git

Using a **Master JSON Manifest** as the single source of truth between your Next.js UI, FastAPI workers, AI providers, and FFmpeg solves the two hardest problems in long-form AI video generation: **cross-stage consistency** and **partial regeneration** without restarting the whole pipeline.

Below is the complete blueprint for merging both repositories, designing the reusable multimodal context layer, hardening your JSON schema for production, and wiring up the 7-stage batch engine.

---

## 1. Repository Merge Strategy (Next.js + FastAPI)

Instead of porting Python/FFmpeg logic into Next.js API routes (which will hit serverless timeouts and memory limits on long videos), keep **`AI-Content-Studio`'s decoupled monorepo architecture** and transplant **`ContentMachine`'s state model and prompt engine** into it.

| Layer | Keep from `AI-Content-Studio` | Transplant from `ContentMachine` | Upgrade Needed for Your Studio |
| --- | --- | --- | --- |
| **Frontend** | Next.js (Turbopack) app shell + WebSocket live progress hooks | Multi-stage UI flow, empty-state card grids, per-card regenerate, variant picker, hover previews | Add **Auth.js (NextAuth) or Clerk** + Zustand store synced to WebSocket deltas |
| **Backend API** | FastAPI server (`server/main.py`) + WebSocket manager | Replicate / Gemini / fal.ai / ElevenLabs provider adapters + 300+ line character prompt rules | Add **Redis + ARQ (or Celery)** for parallel batch queues with pause/resume |
| **Storage & DB** | SQLite + SQLAlchemy stage checkpoints | `project.json` restorable state + real file storage (no base64) | Upgrade to **PostgreSQL** (`JSONB` column for the manifest) + **S3 / Cloudflare R2** |
| **Media Engine** | FFmpeg pipeline (`-c:a aac` PTS drift fix, `loudnorm`, `pysubs2`), `yt-dlp`, Whisper | 1080p resolution lock + ZIP bundle exporter | Add per-scene audio mixing (`adelay`/`amix`) + conditional lip-sync routing |

> **Critical Gotcha from `ContentMachine`:** Video providers like Replicate expire hosted video URLs within hours. Your FastAPI worker must **immediately download** every generated image, audio clip, and video file to your own storage (local disk or S3/R2) and write the *permanent* URL into the Master JSON before notifying the UI.

---

## 2. NotebookLM-Style Multimodal Context Layer (Decode Once, Reuse Everywhere)

To avoid re-processing PDFs, URLs, images, or reference videos every time you tweak a script, build a **Content-Addressed Ingestion Service** that hashes each uploaded source (`SHA-256`) and saves a structured **Context Artifact** in your database.

* **Documents (PDF, DOCX, PPTX, HTML):** Use **Docling** (IBM) or **MarkItDown** (Microsoft) to extract clean Markdown, tables, and embedded images.
* **Web URLs:** Use **Crawl4AI** to pull clean article text and metadata without boilerplate.
* **Reference Videos & Audio:** Use **`yt-dlp`** + **FFmpeg scene-change detection** (extracts keyframes only when shots change) + **Faster-Whisper** (word-level transcript) + a single Vision-LLM pass (e.g., Gemini Flash) to summarize visual style, pacing, and key objects.
* **Deep Multimodal Search (Optional):** If users attach dozens of heavy files per project, plug in **Morphik Core** (open-source multimodal retrieval engine using ColPali) to search across visual PDFs, images, and videos without stuffing everything into the Planner's context window.

Once decoded, the Planner only reads the cached `context_summary.json`—zero reprocessing on script retries.

---

## 3. Production-Hardened Master JSON Schema

Your draft schema captures the right relationships, but three structural upgrades will prevent major headaches in React, TypeScript (Zod), and Python (Pydantic):

1. **Use arrays with stable IDs** (`"id": "char_01"`, `"id": "scene_01"`) instead of dynamic keys like `Name1` or `MoreNames`. Arrays let React render empty-state cards cleanly with `.map()` and let Python batch-dispatch jobs cleanly.
2. **Avoid special characters in keys** (`Char&Prot` → `characters`, `Audio&Sound` → `audio`).
3. **Separate `prompt` (input) from `generation` (output state)** on every node. That is what powers your **Empty State Card Templates**: when `status === "idle"`, the card renders a skeleton with the editable prompt; as FastAPI streams updates over WebSocket, the card flips to `"generating"` → `"completed"` with variant thumbnails.

```json
{
  "projectId": "proj_98a7f",
  "format": "cinematic_drama",
  "contextArtifactIds": ["ctx_pdf_01", "ctx_vid_04"],
  "globalStyle": {
    "aspectRatio": "16:9",
    "resolution": "1080p",
    "visualStylePrompt": "35mm anamorphic film, moody coastal lighting"
  },
  "consistencies": {
    "characters": [
      {
        "id": "char_01",
        "name": "Elena",
        "role": "protagonist",
        "prompt360": "Woman in her late 20s, wind-swept dark hair, weathered linen coat, 360-degree character turnaround sheet, neutral studio background",
        "status": "completed",
        "selectedAssetUrl": "https://cdn.app/proj_98a7f/chars/char_01_v2.png",
        "variants": [".../v1.png", ".../v2.png"]
      }
    ],
    "objects": [
      {
        "id": "obj_01",
        "name": "Red Silk Dress",
        "prompt360": "Flowing crimson silk dress, intricate gold embroidery, 360-degree product turnaround sheet",
        "status": "idle",
        "selectedAssetUrl": null,
        "variants": []
      }
    ]
  },
  "scenes": [
    {
      "sceneNumber": 1,
      "id": "scene_01",
      "timestamp": { "startSec": 0, "endSec": 10 },
      "visualDescription": "Elena stands at the shoreline as a drone glides overhead.",
      "camera": {
        "angle": "Low-angle medium wide",
        "movement": "Slow dolly push-in",
        "lens": "35mm shallow depth of field"
      },
      "keyframe": {
        "refIds": ["char_01", "obj_01", "obj_03"],
        "prompt": "Elena [char_01] standing close to the beach, eyes wide with surprise, wearing [obj_01], with [obj_03] flying above in the overcast sky.",
        "status": "idle",
        "selectedAssetUrl": null,
        "variants": []
      },
      "audio": {
        "voiceover": {
          "enabled": true,
          "startOffsetSec": 0.0,
          "endOffsetSec": 4.0,
          "provider": "elevenlabs",
          "voiceId": "narrator_deep_01",
          "text": "She never expected the signal to reach the coast.",
          "assetUrl": null
        },
        "dialogue": [
          {
            "speakerId": "char_01",
            "voiceId": "elena_voice_02",
            "startOffsetSec": 4.0,
            "endOffsetSec": 9.5,
            "text": "Wait—is that ours? It's coming straight toward us!",
            "assetUrl": null
          }
        ],
        "sfx": {
          "mode": "stock_or_model",
          "prompt": "Crashing ocean waves with distant mechanical hum",
          "assetUrl": null
        },
        "mergedSceneAudioUrl": null,
        "status": "idle"
      },
      "video": {
        "model": "kling_v3",
        "supportsNativeAudio": false,
        "requiresLipSync": true,
        "motionPrompt": "Slow push-in as wind blows her hair, eyes track upward",
        "rawVideoUrl": null,
        "lipSyncedVideoUrl": null,
        "status": "idle"
      }
    }
  ],
  "outroEndFrame": {
    "prompt": "Wide aerial pullback of the empty shoreline at dusk",
    "selectedAssetUrl": null
  },
  "assembly": {
    "transitionType": "cut",
    "burnCaptions": true,
    "thumbnail": { "prompt": "...", "selectedAssetUrl": null },
    "finalVideoUrl": null,
    "status": "idle"
  }
}

```

---

## 4. How Each Stage Executes in Batch

### Step 1: Planner Section

* Use **Structured Outputs** (Gemini / OpenAI JSON Schema enforcement) so the LLM *cannot* break your schema.
* Immediately after generation, save the JSON to PostgreSQL. Every downstream page (Steps 2–6) now reads this manifest and pre-populates its **empty-state cards** automatically.

### Step 2: Characters, Protagonists & Objects (Batch)

* FastAPI loops over `consistencies.characters` + `consistencies.objects` and dispatches them concurrently using `asyncio.Semaphore(5)` (prevents API 429 rate-limit errors).
* Format-aware routing: for a `single_person_speaking` or `podcast` format, the Planner only populates 1–2 host entries; for `cinematic_drama`, it generates full 360° turnaround sheets.

### Step 3: Keyframes (Reference-Injected Batch)

* Because each keyframe carries `refIds: ["char_01", "obj_01"]`, the backend automatically looks up the locked `selectedAssetUrl`s from Step 2 and passes them as **reference images** (e.g., Gemini Image Editing, Flux Kontext, or IP-Adapter) alongside the scene prompt.
* **Start-to-End Frame Chaining:** Your rule ("Scene $N+1$'s start frame is Scene $N$'s end frame") works cleanly—just include the single `outroEndFrame` field shown in the schema above so the very last scene also has an end anchor.

### Step 4: Audio, Dialogue & Per-Scene FFmpeg Merge

* Batch-generate all `voiceover` and `dialogue` clips via ElevenLabs or Google Cloud TTS in parallel.
* For scenes containing both voiceover (e.g., `0:00–0:04`) and dialogue (`0:04–0:10`), run an FFmpeg filtergraph per scene to offset and mix them into one `mergedSceneAudioUrl` padded to the exact scene duration:

```bash
ffmpeg -i voiceover.mp3 -i dialogue.mp3 -filter_complex \
  "[0:a]adelay=0|0,apad=whole_dur=10[vo]; \
   [1:a]adelay=4000|4000,apad=whole_dur=10[dlg]; \
   [vo][dlg]amix=inputs=2:duration=longest:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11[out]" \
  -map "[out]" -c:a aac -b:a 192k scene_01_master.m4a

```

### Step 5: Visual Scene Generation + Conditional Lip Sync

* For Scene $N$, FastAPI constructs the video API payload by pairing:
* `start_image` = `scenes[N].keyframe.selectedAssetUrl`
* `end_image` = `scenes[N+1].keyframe.selectedAssetUrl` (or `outroEndFrame.selectedAssetUrl` for the final scene)
* `duration` = `endSec - startSec`


* **Audio/Lip-Sync Routing:** If `supportsNativeAudio` is `true` (e.g., LTX-2, Kling v3, Veo), pass the audio/SFX prompt directly. If `false` and `requiresLipSync` is `true`, the worker automatically chains the output MP4 + `mergedSceneAudioUrl` into a lip-sync API (Sync Labs, LatentSync, or MuseTalk) before marking the card `"completed"`.

### Step 6 & 7: Assembly, Thumbnail & Export

* **Assembly:** FFmpeg stitches every scene's final clip (`lipSyncedVideoUrl ?? rawVideoUrl`) with its synced audio track (`-c:a aac` to prevent PTS drift), mixes optional background music with sidechain ducking, burns `.ass` subtitles if toggled, and runs a parallel batch call for 3–4 thumbnail variants.
* **Export Page:** Exposes container/codec presets (`H.264 MP4` for web, `ProRes` for NLEs), resolution/aspect ratio, FPS, audio loudness target (`-14 LUFS` for YouTube), and a full **Project ZIP Export** containing `project.json` + all raw scene assets so nothing is ever locked inside the app.

---

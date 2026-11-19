"""Per-Scene Multi-Track FFmpeg Audio Mixer & Loudness Normalization (TASK-6.4)."""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class AudioTrackInput:
    """An individual audio stem with offset timing within a scene."""

    file_path: Path
    offset_sec: float = 0.0
    label: str = "track"


class AudioMixer:
    """FFmpeg filtergraph engine for multi-track audio composition, delay alignment, and EBU R128 loudnorm."""

    def __init__(self, ffmpeg_bin: str = "ffmpeg") -> None:
        self.ffmpeg_bin = ffmpeg_bin

    def mix_scene_audio(
        self,
        tracks: List[AudioTrackInput],
        scene_duration_sec: float,
        output_path: Path,
        target_i: float = -16.0,
        target_tp: float = -1.5,
        target_lra: float = 11.0,
    ) -> Path:
        """Mix multiple audio tracks with millisecond delay alignment and pad to exact scene duration."""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if not tracks:
            # Generate silent stereo AAC track for duration
            cmd_silent = [
                self.ffmpeg_bin,
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"anullsrc=r=48000:cl=stereo:d={scene_duration_sec}",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                str(output_path),
            ]
            subprocess.run(cmd_silent, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            return output_path

        cmd = [self.ffmpeg_bin, "-y"]
        filter_parts: List[str] = []
        mix_inputs: List[str] = []

        # Add inputs
        for i, track in enumerate(tracks):
            cmd.extend(["-i", str(track.file_path)])
            offset_ms = max(0, int(round(track.offset_sec * 1000)))
            dur_int = max(1, int(round(scene_duration_sec)))
            # adelay format: delay_left|delay_right
            filter_parts.append(f"[{i}:a]adelay={offset_ms}|{offset_ms},apad=whole_dur={dur_int}[a{i}]")
            mix_inputs.append(f"[a{i}]")

        # Mix and loudness normalize
        mix_str = "".join(mix_inputs)
        loudnorm_str = f"loudnorm=I={target_i}:TP={target_tp}:LRA={target_lra}"
        filter_parts.append(f"{mix_str}amix=inputs={len(tracks)}:duration=longest:normalize=0,{loudnorm_str}[out]")

        filtergraph = ";".join(filter_parts)

        cmd.extend([
            "-filter_complex",
            filtergraph,
            "-map",
            "[out]",
            "-t",
            str(scene_duration_sec),
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            str(output_path),
        ])

        try:
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        except subprocess.CalledProcessError as err:
            logger.error("FFmpeg audio mix failed: %s\nStderr: %s", err, err.stderr.decode(errors="ignore"))
            # Fallback: simple copy or single track pass
            cmd_fb = [
                self.ffmpeg_bin,
                "-y",
                "-i",
                str(tracks[0].file_path),
                "-t",
                str(scene_duration_sec),
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                str(output_path),
            ]
            subprocess.run(cmd_fb, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

        return output_path

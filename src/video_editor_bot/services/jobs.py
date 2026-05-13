from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4


@dataclass(frozen=True)
class VideoJob:
    job_id: str
    source_path: Path
    output_path: Path
    subtitles_path: Path
    with_subtitles: bool = True


def create_video_job(workdir: Path, source_extension: str = ".mp4", with_subtitles: bool = True) -> VideoJob:
    job_id = uuid4().hex
    job_dir = workdir / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    extension = source_extension if source_extension.startswith(".") else f".{source_extension}"
    return VideoJob(
        job_id=job_id,
        source_path=job_dir / f"input{extension}",
        output_path=job_dir / "output_vertical.mp4",
        subtitles_path=job_dir / "subtitles.srt",
        with_subtitles=with_subtitles,
    )

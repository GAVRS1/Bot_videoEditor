from video_editor_bot.services.jobs import create_video_job


def test_create_video_job_creates_expected_paths(tmp_path) -> None:
    job = create_video_job(tmp_path, "mov")

    assert job.source_path.name == "input.mov"
    assert job.output_path.name == "output_vertical.mp4"
    assert job.subtitles_path.name == "subtitles.srt"
    assert job.source_path.parent.exists()

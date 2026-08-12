"""
YouTube transcript fetcher.
Strategy (in order):
  1. Fetch auto-generated captions via yt-dlp (fast, no download, works on cloud)
  2. Fall back to audio download + local Whisper (slow, only when captions unavailable)

Set USE_WHISPER_FALLBACK=false in .env to disable Whisper (cloud deployments).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import subprocess
import tempfile
from datetime import date
from pathlib import Path
import config
from storage.db import get_session, Transcript, init_db

AUDIO_DIR = Path(config.AUDIO_DOWNLOAD_DIR)
AUDIO_DIR.mkdir(exist_ok=True)

VIDEOS_PER_CHANNEL = 2
USE_WHISPER_FALLBACK = os.getenv("USE_WHISPER_FALLBACK", "true").lower() != "false"
MAX_DURATION_SECONDS = 7200  # skip videos longer than 2 hours


def _get_channel_videos(channel_url: str, max_videos: int = VIDEOS_PER_CHANNEL) -> list[dict]:
    cmd = [
        "yt-dlp", "--flat-playlist",
        "--playlist-end", str(max_videos),
        "--print", '{"id":"%(id)s","title":"%(title)s","url":"%(webpage_url)s","duration":%(duration)s}',
        channel_url,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        videos = []
        for line in result.stdout.strip().splitlines():
            try:
                videos.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        return videos
    except Exception as e:
        print(f"[YouTube] list failed for {channel_url}: {e}")
        return []


def _fetch_auto_captions(video_url: str, video_id: str) -> str | None:
    """Try to get auto-generated captions via yt-dlp. Returns text or None."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cmd = [
            "yt-dlp",
            "--write-auto-subs",
            "--sub-langs", "en",
            "--sub-format", "vtt",
            "--skip-download",
            "--output", os.path.join(tmpdir, "%(id)s.%(ext)s"),
            "--no-playlist",
            "--quiet",
            video_url,
        ]
        try:
            subprocess.run(cmd, timeout=60, check=True)
            # Find the .vtt file
            vtt_files = list(Path(tmpdir).glob("*.vtt"))
            if not vtt_files:
                return None
            raw = vtt_files[0].read_text(encoding="utf-8", errors="ignore")
            return _vtt_to_text(raw)
        except Exception as e:
            print(f"[YouTube] auto-caption fetch failed for {video_id}: {e}")
            return None


def _vtt_to_text(vtt: str) -> str:
    """Strip VTT timestamps and metadata, return clean transcript text."""
    import re
    lines = []
    seen = set()
    for line in vtt.splitlines():
        line = line.strip()
        # Skip header, timestamps, and position cues
        if not line or line.startswith("WEBVTT") or "-->" in line or line.startswith("NOTE"):
            continue
        # Strip inline tags like <00:00:00.000><c> etc.
        line = re.sub(r"<[^>]+>", "", line).strip()
        if not line or line in seen:
            continue
        seen.add(line)
        lines.append(line)
    return " ".join(lines)


def _download_and_transcribe(video_url: str, video_id: str) -> str:
    """Download audio and run local Whisper. Used as fallback."""
    out_template = str(AUDIO_DIR / f"{video_id}.%(ext)s")
    cmd = [
        "yt-dlp", "--format", "bestaudio[ext=m4a]/bestaudio",
        "--output", out_template, "--no-playlist", "--quiet", video_url,
    ]
    try:
        subprocess.run(cmd, timeout=300, check=True)
        matches = list(AUDIO_DIR.glob(f"{video_id}.*"))
        if not matches:
            return ""
        audio_path = matches[0]
    except Exception as e:
        print(f"[YouTube] audio download failed for {video_id}: {e}")
        return ""

    try:
        from faster_whisper import WhisperModel
        model = WhisperModel("base", device="cpu", compute_type="int8")
        segments, _ = model.transcribe(str(audio_path), beam_size=5, language="en")
        text = " ".join(seg.text for seg in segments).strip()
    except Exception as e:
        print(f"[YouTube] Whisper transcription failed for {video_id}: {e}")
        text = ""
    finally:
        try:
            audio_path.unlink()
        except Exception:
            pass

    return text


def _is_already_fetched(video_id: str) -> bool:
    with get_session() as session:
        return session.query(Transcript).filter_by(video_id=video_id).first() is not None


def _save_transcript(source: str, video: dict, transcript: str):
    with get_session() as session:
        if not session.query(Transcript).filter_by(video_id=video["id"]).first():
            session.add(Transcript(
                source=source,
                video_id=video["id"],
                title=video.get("title", ""),
                url=video.get("url", ""),
                transcript=transcript,
                duration_seconds=int(video.get("duration") or 0),
                fetch_date=date.today(),
            ))
            session.commit()


def _channel_display_name(url: str) -> str:
    return url.rstrip("/").split("@")[-1] if "@" in url else url


def run() -> int:
    init_db()
    total = 0

    for channel_url in config.YOUTUBE_CHANNELS:
        source_name = _channel_display_name(channel_url)
        videos = _get_channel_videos(channel_url)
        print(f"[YouTube] {source_name}: found {len(videos)} videos")

        for video in videos:
            vid_id = video.get("id", "")
            if not vid_id or _is_already_fetched(vid_id):
                print(f"[YouTube] {vid_id}: already processed, skipping")
                continue

            duration = int(video.get("duration") or 0)
            if duration > MAX_DURATION_SECONDS:
                print(f"[YouTube] {vid_id}: too long ({duration}s), skipping")
                continue

            title = video.get("title", vid_id)
            print(f"[YouTube] Processing: {title}")

            # Try captions first (fast, cloud-friendly)
            transcript = _fetch_auto_captions(video["url"], vid_id)

            if transcript and len(transcript) > 200:
                method = "captions"
            elif USE_WHISPER_FALLBACK:
                print(f"[YouTube] No captions — falling back to Whisper for {title}")
                transcript = _download_and_transcribe(video["url"], vid_id)
                method = "whisper"
            else:
                print(f"[YouTube] No captions and Whisper disabled — skipping {title}")
                continue

            if transcript:
                _save_transcript(source_name, video, transcript)
                total += 1
                print(f"[YouTube] Saved ({method}): {title} ({len(transcript)} chars)")

    print(f"[YouTube] {total} new transcripts saved")
    return total


if __name__ == "__main__":
    run()

"""
音频/视频转录 — 支持远程API调用
"""
import os
import logging
import tempfile
import requests
from pathlib import Path

logger = logging.getLogger("ingestion.transcriber")

SUPPORTED_VIDEO = {".mp4", ".avi", ".mov", ".mkv", ".flv", ".wmv"}
SUPPORTED_AUDIO = {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"}
SUPPORTED = SUPPORTED_VIDEO | SUPPORTED_AUDIO

# 远程转写API地址（31服务器）
REMOTE_API = os.getenv("WHISPER_API", "http://192.168.0.31:8089")


def is_supported(filepath: str) -> bool:
    ext = os.path.splitext(filepath)[1].lower()
    return ext in SUPPORTED


def transcribe(filepath: str, model_size: str = "tiny") -> str | None:
    """
    转录视频/音频文件为文本。
    优先使用远程API（192.168.0.31），失败则用本地faster-whisper
    """
    ext = os.path.splitext(filepath)[1].lower()
    if ext not in SUPPORTED:
        logger.warning("unsupported media format: %s", ext)
        return None

    # 优先调用远程API
    try:
        return _transcribe_remote(filepath)
    except Exception as e:
        logger.warning(f"远程转写失败，尝试本地: {e}")
        return _transcribe_local(filepath)


def _transcribe_remote(filepath: str) -> str | None:
    """调用31服务器的远程API转写"""
    try:
        logger.info(f"[远程转写] {filepath} -> {REMOTE_API}")
        with open(filepath, 'rb') as f:
            files = {'file': (os.path.basename(filepath), f)}
            resp = requests.post(
                f"{REMOTE_API}/transcribe",
                files=files,
                timeout=3600  # 1小时超时
            )

        if resp.status_code == 200:
            data = resp.json()
            logger.info(f"[远程转写] 完成: {data.get('char_count', 0)} 字符")
            return data.get("text", "")
        else:
            raise Exception(f"API返回 {resp.status_code}")

    except Exception as e:
        raise Exception(f"远程转写失败: {e}")


def _transcribe_local(filepath: str) -> str | None:
    """本地faster-whisper转写（备用）"""
    if "HF_ENDPOINT" not in os.environ:
        os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

    ext = os.path.splitext(filepath)[1].lower()
    try:
        from faster_whisper import WhisperModel

        audio_path = filepath
        tmp_audio = None
        if ext in SUPPORTED_VIDEO:
            tmp_audio = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            audio_path = tmp_audio.name
            _extract_audio(filepath, audio_path)

        logger.info("transcribing %s with faster-whisper local ...", os.path.basename(filepath))
        model = WhisperModel("tiny", device="cpu", compute_type="int8")
        segments, info = model.transcribe(audio_path, beam_size=5, language="zh")

        lines = []
        for seg in segments:
            ts = f"[{_fmt_time(seg.start)} -> {_fmt_time(seg.end)}]"
            lines.append(f"{ts} {seg.text.strip()}")

        text = "\n".join(lines)
        logger.info("transcribed local: %s → %d chars", os.path.basename(filepath), len(text))

        if tmp_audio:
            os.unlink(audio_path)

        return text

    except Exception as e:
        logger.error("local transcribe failed [%s]: %s", filepath, e)
        if tmp_audio and os.path.exists(audio_path):
            os.unlink(audio_path)
        return None


def _extract_audio(video_path: str, audio_path: str):
    """从视频中抽取音频轨道（ffmpeg）"""
    import subprocess

    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vn", "-acodec", "pcm_s16le",
        "-ar", "16000", "-ac", "1",
        audio_path
    ]
    subprocess.run(cmd, capture_output=True, check=True)


def _fmt_time(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"
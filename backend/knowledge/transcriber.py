"""
音频/视频转录 — faster-whisper
输出带时间戳的纯文本
"""
import os
import logging
import tempfile
from pathlib import Path

logger = logging.getLogger("ingestion.transcriber")

SUPPORTED_VIDEO = {".mp4", ".avi", ".mov", ".mkv", ".flv", ".wmv"}
SUPPORTED_AUDIO = {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"}
SUPPORTED = SUPPORTED_VIDEO | SUPPORTED_AUDIO


def is_supported(filepath: str) -> bool:
    ext = os.path.splitext(filepath)[1].lower()
    return ext in SUPPORTED


def transcribe(filepath: str, model_size: str = "small") -> str | None:
    """
    转录视频/音频文件为文本。
    model_size: tiny / base / small / medium / large-v3
    默认 small（平衡速度与质量，~1GB 内存）
    首次运行会自动下载模型到 ~/.cache/huggingface/hub/
    """
    # HuggingFace 镜像（国内必需）
    if "HF_ENDPOINT" not in os.environ:
        os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

    ext = os.path.splitext(filepath)[1].lower()
    if ext not in SUPPORTED:
        logger.warning("unsupported media format: %s", ext)
        return None

    try:
        from faster_whisper import WhisperModel

        # 提取音频轨道（视频需要）
        audio_path = filepath
        tmp_audio = None
        if ext in SUPPORTED_VIDEO:
            tmp_audio = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            audio_path = tmp_audio.name
            _extract_audio(filepath, audio_path)

        # 转录（99 无 GPU，用 CPU int8）
        logger.info("transcribing %s with faster-whisper %s ...", os.path.basename(filepath), model_size)
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
        segments, info = model.transcribe(audio_path, beam_size=5, language="zh")

        lines = []
        for seg in segments:
            ts = f"[{_fmt_time(seg.start)} -> {_fmt_time(seg.end)}]"
            lines.append(f"{ts} {seg.text.strip()}")

        text = "\n".join(lines)
        logger.info("transcribed: %s → %d chars, language=%s", os.path.basename(filepath), len(text), info.language)

        # 清理临时音频文件
        if tmp_audio:
            os.unlink(audio_path)

        return text

    except Exception as e:
        logger.error("transcribe failed [%s]: %s", filepath, e)
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
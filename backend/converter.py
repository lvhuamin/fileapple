#!/usr/bin/env python3
"""
音视频转文字转换器
使用 Whisper 模型进行音频/视频转写
"""

import os
import json
import asyncio
from pathlib import Path
from typing import Optional, Callable, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class TranscriptConverter:
    """音视频转文字转换器"""
    
    SUPPORTED_AUDIO = {'.mp3', '.wav', '.m4a', '.flac', '.ogg', '.wma', '.aac', '.opus'}
    SUPPORTED_VIDEO = {'.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.wmv', '.m4v'}
    SUPPORTED_FORMATS = SUPPORTED_AUDIO | SUPPORTED_VIDEO
    
    def __init__(self, model_name: str = "base"):
        self.model_name = model_name
        self.model = None
        self.is_loaded = False
    
    def load_model(self) -> bool:
        """加载 Whisper 模型"""
        if self.is_loaded:
            return True
        
        try:
            import whisper
            logger.info(f"[Converter] 加载 Whisper 模型: {self.model_name}")
            self.model = whisper.load_model(self.model_name)
            self.is_loaded = True
            logger.info("[Converter] Whisper 模型加载完成")
            return True
        except Exception as e:
            logger.error(f"[Converter] Whisper 模型加载失败: {e}", exc_info=True)
            self.model = None
            return False
    
    def unload_model(self):
        """卸载模型释放内存"""
        if self.model:
            del self.model
            self.model = None
            self.is_loaded = False
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except ImportError:
                pass
            logger.info("[Converter] 模型已卸载")
    
    def is_supported(self, file_path: str) -> bool:
        """检查是否支持该格式"""
        ext = Path(file_path).suffix.lower()
        return ext in self.SUPPORTED_FORMATS
    
    def get_format(self, file_path: str) -> str:
        """获取文件格式类型"""
        ext = Path(file_path).suffix.lower()
        if ext in self.SUPPORTED_AUDIO:
            return "audio"
        elif ext in self.SUPPORTED_VIDEO:
            return "video"
        return "unknown"
    
    async def transcribe(
        self, 
        audio_path: str, 
        output_dir: Optional[str] = None,
        language: str = "zh",
        task: str = "transcribe",
        verbose: bool = False,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> Dict[str, Any]:
        """
        转写音频/视频
        
        Args:
            audio_path: 音视频文件路径
            output_dir: 输出目录，默认与源文件同目录
            language: 语言，默认中文
            task: transcribe 或 translate
            verbose: 是否输出详细日志
            progress_callback: 进度回调函数 (progress: float, message: str)
        
        Returns:
            {
                "success": bool,
                "text": str,           # 转写文本
                "json_path": str,      # JSON结果文件路径
                "segments": list,      # 分段结果
                "language": str,       # 检测到的语言
                "duration": float      # 时长
            }
        """
        if not self.model and not self.load_model():
            return {"success": False, "error": "模型加载失败"}
        
        audio_path = Path(audio_path)
        if not audio_path.exists():
            return {"success": False, "error": f"文件不存在: {audio_path}"}
        
        if not self.is_supported(str(audio_path)):
            return {"success": False, "error": f"不支持的格式: {audio_path.suffix}"}
        
        output_dir = Path(output_dir) if output_dir else audio_path.parent
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 输出文件路径
        stem = audio_path.stem
        txt_path = output_dir / f"{stem}.txt"
        json_path = output_dir / f"{stem}.json"
        
        logger.info(f"[Converter] 开始转写: {audio_path.name} 语言={language} 模型={self.model_name}")
        
        try:
            # 执行转写（非阻塞）
            loop = asyncio.get_event_loop()
            
            def do_transcribe():
                options = {
                    'language': language,
                    'task': task,
                    'verbose': verbose,
                    'fp16': False,
                    'word_timestamps': True
                }
                return self.model.transcribe(str(audio_path), **options)
            
            # 带超时
            result = await asyncio.wait_for(
                loop.run_in_executor(None, do_transcribe),
                timeout=3600  # 1小时超时
            )
            
            transcript_text = result.get('text', '').strip()
            
            # 保存纯文本
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(transcript_text)
            
            # 保存完整 JSON
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'source': str(audio_path),
                    'format': self.get_format(str(audio_path)),
                    'model': self.model_name,
                    'language': result.get('language', language),
                    'duration': result.get('duration', 0),
                    'text': transcript_text,
                    'segments': result.get('segments', []),
                    'transcribed_at': datetime.now().isoformat()
                }, f, ensure_ascii=False, indent=2)
            
            logger.info(f"[Converter] 转写完成: {txt_path} 时长={result.get('duration', 0):.1f}s")
            
            return {
                "success": True,
                "text": transcript_text,
                "txt_path": str(txt_path),
                "json_path": str(json_path),
                "segments": result.get('segments', []),
                "language": result.get('language', language),
                "duration": result.get('duration', 0)
            }
            
        except asyncio.TimeoutError:
            logger.error(f"[Converter] 转写超时: {audio_path.name}")
            return {"success": False, "error": "转写超时（超过1小时）"}
        except Exception as e:
            logger.error(f"[Converter] 转写失败: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    async def batch_transcribe(
        self,
        directory: str,
        pattern: str = "*",
        output_dir: Optional[str] = None,
        language: str = "zh",
        max_workers: int = 2,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> list:
        """
        批量转写目录下的音视频文件
        
        Args:
            directory: 目录路径
            pattern: 文件匹配模式，如 "*.mp3"
            output_dir: 输出目录
            language: 语言
            max_workers: 最大并发数
            progress_callback: 进度回调 (current, total, filename)
        
        Returns:
            结果列表
        """
        directory = Path(directory)
        if not directory.exists():
            return [{"success": False, "error": "目录不存在"}]
        
        # 查找所有支持的文件
        files = []
        for ext in self.SUPPORTED_FORMATS:
            files.extend(directory.glob(f"**/*{ext}"))
        
        if not files:
            return [{"success": False, "error": "未找到音视频文件"}]
        
        logger.info(f"[Converter] 批量转写: {len(files)} 个文件")
        
        results = []
        for i, file_path in enumerate(files):
            if progress_callback:
                progress_callback(i + 1, len(files), str(file_path.name))
            
            result = await self.transcribe(
                str(file_path),
                output_dir=output_dir,
                language=language
            )
            result['source'] = str(file_path)
            results.append(result)
        
        return results


# 全局转换器实例
_converter: Optional[TranscriptConverter] = None


def get_converter(model_name: str = "base") -> TranscriptConverter:
    """获取转换器单例"""
    global _converter
    if _converter is None:
        _converter = TranscriptConverter(model_name)
    return _converter


# ========== CLI 工具 ==========

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="音视频转文字工具")
    parser.add_argument("input", help="输入文件或目录")
    parser.add_argument("-o", "--output", help="输出目录")
    parser.add_argument("-m", "--model", default="base", help="Whisper 模型")
    parser.add_argument("-l", "--language", default="zh", help="语言")
    parser.add_argument("--batch", action="store_true", help="批量模式")
    parser.add_argument("--unload", action="store_true", help="完成后卸载模型")
    
    args = parser.parse_args()
    
    converter = get_converter(args.model)
    
    if args.batch or Path(args.input).is_dir():
        # 批量转写
        results = asyncio.run(converter.batch_transcribe(
            args.input,
            output_dir=args.output,
            language=args.language
        ))
        for r in results:
            status = "✅" if r.get("success") else "❌"
            print(f"{status} {r.get('source', '')}: {r.get('error', r.get('txt_path', ''))}")
    else:
        # 单文件转写
        result = asyncio.run(converter.transcribe(
            args.input,
            output_dir=args.output,
            language=args.language
        ))
        if result["success"]:
            print(f"✅ 转写完成: {result['txt_path']}")
            print(f"\n--- 转写结果 ---\n{result['text'][:500]}...")
        else:
            print(f"❌ 转写失败: {result['error']}")
    
    if args.unload:
        converter.unload_model()

"""Prompt builder module for speaker notes (extracted from enhanced_ppt_service).

This isolates prompt construction so future optimization / A-B testing /
model-specific tuning can occur without touching the main service logic.

Design goals:
- Keep interfaces small & explicit
- No external service imports (pure function module)
- Backwards compatible: enhanced_ppt_service keeps its old private methods but delegates here
"""
from __future__ import annotations
from typing import Optional

def build_single_pass_prompt(topic: str, total: int, outline_block: str, language: str,
                              words_per_slide: Optional[int] = None) -> str:
    words_hint = ""
    if words_per_slide:
        if language.startswith('zh'):
            words_hint = f"每页约{words_per_slide}字"
        else:
            words_hint = f"~{words_per_slide} words each"
    if language.startswith('zh'):
        return (
            f"请一次性为以下演示文稿生成逐页演讲稿，要求整体连贯：\n"
            f"主题：{topic}\n"
            f"共{total}页，{words_hint}\n"
            f"页结构与可见要点：\n{outline_block}\n"
            "输出格式：按照页顺序，用标记 '## 第X页' 开头，然后正文。不要再输出目录；避免重复开场寒暄；"
            "每页之间加入自然过渡（上一页结尾自然引向下一页）；最后一页做收束和致谢。只输出演讲稿，不要额外说明。"
        )
    else:
        return (
            f"Generate the full set of presenter scripts in one pass for coherence.\n"
            f"Topic: {topic}\nSlides: {total} {words_hint}\n"
            f"Slides with extracted visible text:\n{outline_block}\n"
            "Format: For each slide use a heading '## Slide X' then body. Provide smooth transitions;"
            " no repeated greetings; final slide concludes succinctly. Output scripts only."
        )

def build_per_slide_prompt(**kwargs) -> str:
    # We keep the original logic inside enhanced_ppt_service; this is placeholder for future full move.
    # For now simply raise to ensure we consciously migrate piece by piece.
    raise NotImplementedError("Per-slide prompt still constructed in service; move here once stabilized.")

"""Slide outline prompt helpers.

This module provides static methods that build prompt strings sent to LLMs.
Methods return strings only and do not perform network or model calls.
"""

from typing import Optional


class OutlinePrompts:
    """Collection of prompt templates for Slide outline generation.

    Methods return prompt text in Chinese or English and include JSON output
    format requirements to help downstream parsers process model output.
    """

    @staticmethod
    def get_outline_prompt_zh(
        topic: str,
        scenario_desc: str,
        target_audience: str,
        style_desc: str,
        requirements: Optional[str],
        description: Optional[str],
        research_section: Optional[str],
        page_count_instruction: str,
        expected_page_count: int,
        language: str = "zh",
    ) -> str:
        """Return a Chinese prompt string for outline generation."""
        req = requirements or "无"
        desc = description or "无"
        research = research_section or ""

        return (
            f"你是一位专业的Slide大纲策划专家。基于以下项目信息，生成一个结构清晰、格式规范的JSON格式Slide大纲。\n\n"
            f"主题: {topic}\n"
            f"场景: {scenario_desc}\n"
            f"目标受众: {target_audience}\n"
            f"风格: {style_desc}\n"
            f"特殊要求: {req}\n"
            f"补充说明: {desc}\n"
            f"{research}\n\n"
            f"页数要求: {page_count_instruction}，目标页数: {expected_page_count}\n\n"
            "请严格按 JSON 格式输出，返回对象中必须包含字段: title, total_pages, page_count_mode, slides, metadata。\n"
            "slides 为数组，每个元素包含: page_number, title, content_points (数组), slide_type (title|content|conclusion), description, chart_config(可选)。\n"
            "注意: 每页内容点控制在 3-6 条，每条不超过 50 字。\n"
        )

    @staticmethod
    def get_outline_prompt_en(
        topic: str,
        scenario_desc: str,
        target_audience: str,
        style_desc: str,
        requirements: Optional[str],
        description: Optional[str],
        research_section: Optional[str],
        page_count_instruction: str,
        expected_page_count: int,
        language: str = "en",
    ) -> str:
        """Return an English prompt string for outline generation."""
        req = requirements or "None"
        desc = description or "None"
        research = research_section or ""

        return (
            f"You are a professional Slide outline designer. Based on the project details below, generate a JSON-format Slide outline.\n\n"
            f"Topic: {topic}\n"
            f"Scenario: {scenario_desc}\n"
            f"Target audience: {target_audience}\n"
            f"Style: {style_desc}\n"
            f"Requirements: {req}\n"
            f"Notes: {desc}\n"
            f"{research}\n\n"
            f"Page count instructions: {page_count_instruction}, expected pages: {expected_page_count}\n\n"
            "Return a valid JSON object containing: title, total_pages, page_count_mode, slides (array), metadata.\n"
            "Each slide item should include: page_number, title, content_points (array), slide_type, description, chart_config (optional).\n"
        )

    @staticmethod
    def get_streaming_outline_prompt(
        topic: str,
        target_audience: str,
        ppt_style: str,
        page_count_instruction: str,
        research_section: Optional[str] = None,
    ) -> str:
        """Return a prompt for streaming outline generation (chunked output)."""
        research = research_section or ""
        return (
            f"作为专业的Slide大纲生成助手，请为以下项目生成详细的大纲，并以流式(chunked)方式逐步返回结果，最终保证可以组合成一个完整的 JSON 对象。\n\n"
            f"主题: {topic}\n"
            f"目标受众: {target_audience}\n"
            f"风格: {ppt_style}\n"
            f"{research}\n\n"
            f"页数/分配要求: {page_count_instruction}\n\n"
            "流式返回要求: 每个 chunk 包含可解析的 JSON 片段(例如单个 slide 项)，最终拼接应得到完整 slides 数组和 metadata。\n"
        )

    @staticmethod
    def get_outline_generation_context(
        topic: str,
        target_audience: str,
        page_count_instruction: str,
        ppt_style: str,
        custom_style: Optional[str],
        description: Optional[str],
        page_count_mode: str,
    ) -> str:
        """Return context prompt for outline generation (machine-readable)."""
        custom = custom_style or ""
        desc = description or ""
        return (
            f"项目信息:\n- 主题: {topic}\n- 目标受众: {target_audience}\n- 页数要求: {page_count_instruction}\n"
            f"- 风格: {ppt_style}\n- 自定义风格: {custom}\n- 说明: {desc}\n\n"
            "任务: 生成完整的 Slide 大纲，输出 JSON 格式，包含 title、total_pages、slides 和 metadata。"
        )

"""
图节点实现 - 定义LangGraph工作流中的各个节点
"""

import json
import logging
from typing import Any, Dict, Literal

from langchain_core.runnables import RunnableConfig

from ..core.json_parser import JSONParser
from ..core.models import PPTState
from ..generators.chains import ChainExecutor, ChainManager
from ..utils.logger import LoggerMixin

logger = logging.getLogger(__name__)


class GraphNodes(LoggerMixin):
    """图节点集合，包含所有工作流节点的实现"""

    def __init__(self, chain_manager: ChainManager, config=None):
        self.chain_manager = chain_manager
        self.chain_executor = ChainExecutor(chain_manager)
        self.json_parser = JSONParser()
        self.config = config  # 添加配置参数

    def _get_slides_range_text(self, state: Dict[str, Any]) -> str:
        """根据状态中的页数模式生成页数约束文本"""
        page_count_mode = state.get("page_count_mode", "ai_decide")
        min_pages = state.get("min_pages")
        max_pages = state.get("max_pages")
        fixed_pages = state.get("fixed_pages")

        if page_count_mode == "fixed" and fixed_pages:
            result = f"【强制要求】必须生成恰好{fixed_pages}页的PPT，不能多也不能少"
        elif page_count_mode == "custom_range" and min_pages and max_pages:
            result = f"【强制要求】必须严格控制在{min_pages}-{max_pages}页范围内，最少{min_pages}页，最多{max_pages}页，不能超出此范围"
        else:  # ai_decide
            result = (
                "根据内容的复杂度、深度和逻辑结构，自主决定最合适的页数，确保内容充实且逻辑清晰"
            )

        return result

    async def analyze_structure(self, state: PPTState, config: RunnableConfig) -> Dict[str, Any]:
        """
        分析文档结构节点

        Args:
            state: 当前状态
            config: 运行配置

        Returns:
            更新的状态字段
        """
        self.logger.info("开始分析文档结构...")

        try:
            # 获取第一个文档块
            first_chunk = state["document_chunks"][0] if state["document_chunks"] else ""

            if not first_chunk.strip():
                self.logger.warning("第一个文档块为空，使用默认结构")
                structure = {
                    "title": "文档分析",
                    "type": "通用文档",
                    "sections": [],
                    "key_concepts": [],
                    "language": "中文",
                    "complexity": "中等",
                }
            else:
                # 调用结构分析链
                structure_response = await self.chain_executor.execute_with_retry(
                    "structure_analysis",
                    {
                        "content": first_chunk,
                        "project_topic": state.get("project_topic", ""),
                        "project_scenario": state.get("project_scenario", "general"),
                        "project_requirements": state.get("project_requirements", ""),
                        "target_audience": state.get("target_audience", "普通大众"),
                        "custom_audience": state.get("custom_audience", ""),
                        "ppt_style": state.get("ppt_style", "general"),
                        "custom_style_prompt": state.get("custom_style_prompt", ""),
                    },
                    config,
                )

                # 解析JSON响应
                structure = self.json_parser.extract_json_from_response(structure_response)

                # 验证结构
                if not isinstance(structure, dict):
                    raise ValueError("结构分析返回的不是有效的字典")

            self.logger.info(f"文档结构分析完成: {structure.get('title', '未知标题')}")

            return {
                "document_structure": structure,
                "accumulated_context": first_chunk[:500],  # 保留前500字作为上下文
            }

        except Exception as e:
            self.logger.error(f"文档结构分析失败: {e}")
            # 返回默认结构
            return {
                "document_structure": {
                    "title": "文档分析",
                    "type": "通用文档",
                    "sections": [],
                    "key_concepts": [],
                    "language": "中文",
                    "complexity": "中等",
                },
                "accumulated_context": (first_chunk[:500] if state["document_chunks"] else ""),
            }

    async def generate_initial_outline(
        self, state: PPTState, config: RunnableConfig
    ) -> Dict[str, Any]:
        """
        生成初始PPT框架节点

        Args:
            state: 当前状态
            config: 运行配置

        Returns:
            更新的状态字段
        """
        self.logger.info("开始生成初始PPT框架...")

        try:
            # 准备输入
            structure_json = json.dumps(state["document_structure"], ensure_ascii=False)
            first_chunk = state["document_chunks"][0] if state["document_chunks"] else ""

            # 准备输入参数，包含页数范围、目标语言和项目信息
            chain_inputs = {
                "structure": structure_json,
                "content": first_chunk,
                "project_topic": state.get("project_topic", ""),
                "project_scenario": state.get("project_scenario", "general"),
                "project_requirements": state.get("project_requirements", ""),
                "target_audience": state.get("target_audience", "普通大众"),
                "custom_audience": state.get("custom_audience", ""),
                "ppt_style": state.get("ppt_style", "general"),
                "custom_style_prompt": state.get("custom_style_prompt", ""),
            }

            # 添加页数范围信息
            slides_range_text = self._get_slides_range_text(state)
            chain_inputs["slides_range"] = slides_range_text
            if self.config:
                chain_inputs["target_language"] = self.config.target_language
            else:
                chain_inputs["target_language"] = "zh"  # 默认中文

            # 调用初始大纲生成链
            outline_response = await self.chain_executor.execute_with_retry(
                "initial_outline", chain_inputs, config
            )

            # 解析JSON响应
            outline = self.json_parser.extract_json_from_response(outline_response)

            # 验证和修复大纲结构
            outline = self.json_parser.validate_ppt_structure(outline)

            self.logger.info(f"初始PPT框架生成完成: {outline.get('title', '未知标题')}")

            return {
                **state,  # 保留所有原始状态
                "ppt_title": outline.get("title", "学术演示"),
                "total_pages": outline.get("total_pages", 15),
                "page_count_mode": state.get("page_count_mode", "estimated"),  # 保持原始页数模式
                "slides": outline.get("slides", []),
                "current_index": 1,
            }

        except Exception as e:
            self.logger.error(f"初始PPT框架生成失败: {e}")
            # 返回默认框架
            return {
                "ppt_title": "学术演示",
                "total_pages": 15,
                "page_count_mode": "estimated",
                "slides": [
                    {
                        "page_number": 1,
                        "title": "标题页",
                        "content_points": ["演示标题", "演示者", "日期"],
                        "slide_type": "title",
                        "description": "PPT开场标题页",
                    }
                ],
                "current_index": 1,
            }

    async def refine_outline(self, state: PPTState, config: RunnableConfig) -> Dict[str, Any]:
        """
        细化Slide大纲节点

        Args:
            state: 当前状态
            config: 运行配置

        Returns:
            更新的状态字段
        """
        current_index = state["current_index"]
        total_chunks = len(state["document_chunks"])

        self.logger.info(f"正在细化Slide大纲 ({current_index + 1}/{total_chunks})...")

        # 检查是否还有内容需要处理
        if current_index >= total_chunks:
            self.logger.info("所有文档块已处理完成")
            return state

        try:
            # 获取当前文档块
            current_content = state["document_chunks"][current_index]

            # 准备现有大纲
            existing_outline = {
                "title": state["ppt_title"],
                "total_pages": state["total_pages"],
                "slides": state["slides"],
            }
            existing_outline_json = json.dumps(existing_outline, ensure_ascii=False)

            # 准备输入参数，包含页数范围、目标语言和项目信息
            chain_inputs = {
                "existing_outline": existing_outline_json,
                "new_content": current_content,
                "context": state["accumulated_context"],
                "project_topic": state.get("project_topic", ""),
                "project_scenario": state.get("project_scenario", "general"),
                "project_requirements": state.get("project_requirements", ""),
                "target_audience": state.get("target_audience", "普通大众"),
                "custom_audience": state.get("custom_audience", ""),
                "ppt_style": state.get("ppt_style", "general"),
                "custom_style_prompt": state.get("custom_style_prompt", ""),
            }

            # 添加页数范围信息和目标语言
            slides_range_text = self._get_slides_range_text(state)
            chain_inputs["slides_range"] = slides_range_text
            if self.config:
                chain_inputs["target_language"] = self.config.target_language
            else:
                chain_inputs["target_language"] = "zh"  # 默认中文

            # 调用细化链
            refined_response = await self.chain_executor.execute_with_retry(
                "refine_outline", chain_inputs, config
            )

            # 解析JSON响应
            refined_outline = self.json_parser.extract_json_from_response(refined_response)

            # 验证和修复结构
            refined_outline = self.json_parser.validate_ppt_structure(refined_outline)

            # 更新累积上下文
            new_context = state["accumulated_context"] + "\n" + current_content[:300]
            if len(new_context) > 2000:  # 限制上下文长度
                new_context = new_context[-2000:]

            return {
                **state,  # 保留所有原始状态
                "ppt_title": refined_outline.get("title", state["ppt_title"]),
                "total_pages": refined_outline.get("total_pages", state["total_pages"]),
                "slides": refined_outline.get("slides", state["slides"]),
                "current_index": current_index + 1,
                "accumulated_context": new_context,
            }

        except Exception as e:
            self.logger.error(f"Slide大纲细化失败: {e}")
            # 继续处理下一个块
            return {**state, "current_index": current_index + 1}

    async def finalize_outline(self, state: PPTState, config: RunnableConfig) -> Dict[str, Any]:
        """
        最终优化Slide大纲节点

        Args:
            state: 当前状态
            config: 运行配置

        Returns:
            更新的状态字段
        """
        self.logger.info("开始最终优化Slide大纲...")

        try:
            # 准备当前大纲
            current_outline = {
                "title": state["ppt_title"],
                "total_pages": state["total_pages"],
                "page_count_mode": state["page_count_mode"],
                "slides": state["slides"],
            }
            outline_json = json.dumps(current_outline, ensure_ascii=False)

            # 准备输入参数，包含页数范围、目标语言和项目信息
            chain_inputs = {
                "outline": outline_json,
                "project_topic": state.get("project_topic", ""),
                "project_scenario": state.get("project_scenario", "general"),
                "project_requirements": state.get("project_requirements", ""),
                "target_audience": state.get("target_audience", "普通大众"),
                "custom_audience": state.get("custom_audience", ""),
                "ppt_style": state.get("ppt_style", "general"),
                "custom_style_prompt": state.get("custom_style_prompt", ""),
            }

            # 添加页数范围信息和目标语言
            slides_range_text = self._get_slides_range_text(state)
            chain_inputs["slides_range"] = slides_range_text
            if self.config:
                chain_inputs["target_language"] = self.config.target_language
            else:
                chain_inputs["target_language"] = "zh"  # 默认中文

            # 调用最终优化链
            final_response = await self.chain_executor.execute_with_retry(
                "finalize_outline", chain_inputs, config
            )

            # 解析JSON响应
            final_outline = self.json_parser.extract_json_from_response(final_response)

            # 验证和修复结构
            final_outline = self.json_parser.validate_ppt_structure(final_outline)

            # 确保幻灯片编号正确
            slides = final_outline.get("slides", [])
            for i, slide in enumerate(slides):
                slide["page_number"] = i + 1

            # 验证页数是否在范围内
            total_pages = len(slides)
            if self.config:
                if total_pages < self.config.min_slides:
                    self.logger.warning(
                        f"生成的页数({total_pages})少于最小要求({self.config.min_slides})"
                    )
                    # 自动扩展页数到最小要求
                    needed_pages = self.config.min_slides - total_pages

                    # 添加扩展页面
                    for i in range(needed_pages):
                        new_page_num = total_pages + i + 1
                        if i < needed_pages // 2:
                            # 前半部分添加详细内容页
                            slides.append(
                                {
                                    "page_number": new_page_num,
                                    "title": f"详细分析 {i + 1}",
                                    "content_points": [
                                        "深入分析相关概念和原理",
                                        "提供具体案例和实践经验",
                                        "探讨实施过程中的关键要点",
                                        "分析可能遇到的挑战和解决方案",
                                    ],
                                    "slide_type": "content",
                                    "description": "扩展的详细分析内容页",
                                }
                            )
                        else:
                            # 后半部分添加总结和展望页
                            slides.append(
                                {
                                    "page_number": new_page_num,
                                    "title": f"总结与展望 {i - needed_pages // 2 + 1}",
                                    "content_points": [
                                        "总结关键要点和核心价值",
                                        "分析未来发展趋势和机遇",
                                        "提出改进建议和优化方向",
                                        "展望长期发展前景",
                                    ],
                                    "slide_type": "content",
                                    "description": "扩展的总结展望内容页",
                                }
                            )

                    total_pages = len(slides)

                elif total_pages > self.config.max_slides:
                    self.logger.warning(
                        f"生成的页数({total_pages})超过最大限制({self.config.max_slides})"
                    )
                    # 如果超过最大页数，截取到最大页数
                    slides = slides[: self.config.max_slides]
                    total_pages = len(slides)
                    # 重新编号
                    for i, slide in enumerate(slides):
                        slide["page_number"] = i + 1

            return {
                **state,  # 保留所有原始状态
                "ppt_title": final_outline.get("title", state["ppt_title"]),
                "total_pages": total_pages,
                "page_count_mode": "final",
                "slides": slides,
            }

        except Exception as e:
            self.logger.error(f"Slide大纲最终优化失败: {e}")
            # 返回当前状态，但标记为最终状态
            slides = state["slides"]
            for i, slide in enumerate(slides):
                slide["page_number"] = i + 1

            return {
                **state,  # 保留所有原始状态
                "ppt_title": state["ppt_title"],
                "total_pages": len(slides),
                "page_count_mode": "final",
                "slides": slides,
            }

    def should_continue_refining(
        self, state: PPTState
    ) -> Literal["refine_outline", "finalize_outline"]:
        """
        判断是否继续细化的条件函数

        Args:
            state: 当前状态

        Returns:
            下一个节点名称
        """
        current_index = state["current_index"]
        total_chunks = len(state["document_chunks"])

        if current_index >= total_chunks:
            self.logger.info("所有文档块已处理，进入最终优化阶段")
            return "finalize_outline"
        else:
            self.logger.debug(f"继续处理文档块 {current_index + 1}/{total_chunks}")
            return "refine_outline"

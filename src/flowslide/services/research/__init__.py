"""
Research module for FlowSlide

This module provides comprehensive research functionality including:
- SearXNG content search provider
- Web content extraction pipeline
- Enhanced research service with multiple providers
"""

from .content_extractor import ExtractedContent, WebContentExtractor
from .enhanced_research_service import (EnhancedResearchReport,
                                        EnhancedResearchService,
                                        EnhancedResearchStep)
from .searxng_provider import (SearXNGContentProvider, SearXNGSearchResponse,
                               SearXNGSearchResult)

__all__ = [
    "SearXNGContentProvider",
    "SearXNGSearchResult",
    "SearXNGSearchResponse",
    "WebContentExtractor",
    "ExtractedContent",
    "EnhancedResearchService",
    "EnhancedResearchStep",
    "EnhancedResearchReport",
]

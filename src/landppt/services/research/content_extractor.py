"""
Web Content Extraction Pipeline for Research Functionality

This module provides robust web content extraction using BeautifulSoup to fetch
and parse HTML content from web pages, with proper error handling and content cleaning.
"""

import asyncio
import logging
import re
import time
from typing import Dict, List, Optional, Any, Set
from urllib.parse import urljoin, urlparse
import aiohttp
from bs4 import BeautifulSoup, Comment
from langchain.text_splitter import RecursiveCharacterTextSplitter

from ...core.config import ai_config

logger = logging.getLogger(__name__)


class ExtractedContent:
    """Represents extracted content from a web page"""
    
    def __init__(self, url: str, title: str = "", content: str = "", 
                 metadata: Optional[Dict[str, Any]] = None):
        self.url = url
        self.title = title
        self.content = content
        self.metadata = metadata or {}
        self.extraction_time = time.time()
        self.word_count = len(content.split()) if content else 0
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'url': self.url,
            'title': self.title,
            'content': self.content,
            'metadata': self.metadata,
            'extraction_time': self.extraction_time,
            'word_count': self.word_count
        }


class WebContentExtractor:
    """Web content extraction pipeline using BeautifulSoup"""
    
    def __init__(self):
        self.timeout = ai_config.research_extraction_timeout
        self.max_content_length = ai_config.research_max_content_length
        self.user_agent = "LandPPT Research Bot 1.0"
        
        # Content selectors for different types of content
        self.content_selectors = [
            'article',
            'main',
            '.content',
            '.post-content',
            '.entry-content',
            '.article-content',
            '.story-body',
            '.post-body',
            '#content',
            '#main-content'
        ]
        
        # Tags to remove completely
        self.remove_tags = {
            'script', 'style', 'nav', 'header', 'footer', 'aside',
            'advertisement', 'ads', 'sidebar', 'menu', 'popup'
        }
        
        # Text splitter for long content
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.max_content_length,
            chunk_overlap=200,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize extracted text"""
        if not text:
            return ""
            
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove common unwanted patterns
        text = re.sub(r'(Cookie|Privacy) Policy.*?(?=\n|$)', '', text, flags=re.IGNORECASE)
        text = re.sub(r'Subscribe.*?newsletter.*?(?=\n|$)', '', text, flags=re.IGNORECASE)
        text = re.sub(r'Follow us on.*?(?=\n|$)', '', text, flags=re.IGNORECASE)
        text = re.sub(r'Share this.*?(?=\n|$)', '', text, flags=re.IGNORECASE)
        
        # Remove URLs
        text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
        
        return text.strip()
    
    def _extract_metadata(self, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        """Extract metadata from HTML"""
        metadata = {}
        
        # Basic metadata
        if soup.title:
            metadata['title'] = soup.title.string.strip() if soup.title.string else ""
        
        # Meta tags
        meta_tags = soup.find_all('meta')
        for tag in meta_tags:
            name = tag.get('name') or tag.get('property')
            content = tag.get('content')
            if name and content:
                metadata[name] = content
        
        # Language
        html_tag = soup.find('html')
        if html_tag and html_tag.get('lang'):
            metadata['language'] = html_tag.get('lang')
        
        # Domain
        parsed_url = urlparse(url)
        metadata['domain'] = parsed_url.netloc
        
        return metadata
    
    def _extract_main_content(self, soup: BeautifulSoup) -> str:
        """Extract main content from HTML using various strategies"""
        
        # Remove unwanted tags
        for tag_name in self.remove_tags:
            for tag in soup.find_all(tag_name):
                tag.decompose()
        
        # Remove comments
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()
        
        # Try content selectors in order of preference
        for selector in self.content_selectors:
            content_element = soup.select_one(selector)
            if content_element:
                text = content_element.get_text(separator=' ', strip=True)
                if len(text) > 100:  # Minimum content length
                    return self._clean_text(text)
        
        # Fallback: extract from body
        body = soup.find('body')
        if body:
            # Remove navigation, sidebar, and footer elements
            for element in body.find_all(['nav', 'aside', 'footer', 'header']):
                element.decompose()
            
            text = body.get_text(separator=' ', strip=True)
            return self._clean_text(text)
        
        # Last resort: get all text
        return self._clean_text(soup.get_text(separator=' ', strip=True))
    
    async def extract_content(self, url: str) -> Optional[ExtractedContent]:
        """
        Extract content from a single URL
        
        Args:
            url: URL to extract content from
            
        Returns:
            ExtractedContent object or None if extraction fails
        """
        try:
            headers = {
                'User-Agent': self.user_agent,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
            }
            
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout),
                headers=headers
            ) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        logger.warning(f"Failed to fetch {url}: HTTP {response.status}")
                        return None
                    
                    # Check content type
                    content_type = response.headers.get('content-type', '').lower()
                    if 'text/html' not in content_type:
                        logger.warning(f"Skipping non-HTML content: {url}")
                        return None
                    
                    html_content = await response.text()
            
            # Parse HTML
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Extract metadata
            metadata = self._extract_metadata(soup, url)
            
            # Extract main content
            content = self._extract_main_content(soup)
            
            # Limit content length
            if len(content) > self.max_content_length:
                chunks = self.text_splitter.split_text(content)
                content = chunks[0] if chunks else content[:self.max_content_length]
            
            # Get title
            title = metadata.get('title', '')
            if not title and soup.title:
                title = soup.title.string.strip() if soup.title.string else ""
            
            extracted = ExtractedContent(
                url=url,
                title=title,
                content=content,
                metadata=metadata
            )
            
            logger.info(f"Extracted {extracted.word_count} words from {url}")
            return extracted
            
        except asyncio.TimeoutError:
            logger.warning(f"Timeout extracting content from {url}")
            return None
        except Exception as e:
            logger.warning(f"Error extracting content from {url}: {e}")
            return None
    
    async def extract_multiple(self, urls: List[str], 
                             max_concurrent: int = 5,
                             delay_between_requests: float = 0.5) -> List[ExtractedContent]:
        """
        Extract content from multiple URLs with concurrency control
        
        Args:
            urls: List of URLs to extract content from
            max_concurrent: Maximum concurrent requests
            delay_between_requests: Delay between requests in seconds
            
        Returns:
            List of ExtractedContent objects
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        results = []
        
        async def extract_with_semaphore(url: str) -> Optional[ExtractedContent]:
            async with semaphore:
                result = await self.extract_content(url)
                if delay_between_requests > 0:
                    await asyncio.sleep(delay_between_requests)
                return result
        
        # Create tasks for all URLs
        tasks = [extract_with_semaphore(url) for url in urls]
        
        # Execute tasks and collect results
        completed_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in completed_results:
            if isinstance(result, ExtractedContent):
                results.append(result)
            elif isinstance(result, Exception):
                logger.warning(f"Content extraction failed: {result}")
        
        logger.info(f"Successfully extracted content from {len(results)}/{len(urls)} URLs")
        return results
    
    def get_status(self) -> Dict[str, Any]:
        """Get extractor status information"""
        return {
            'timeout': self.timeout,
            'max_content_length': self.max_content_length,
            'user_agent': self.user_agent,
            'content_selectors': self.content_selectors,
            'remove_tags': list(self.remove_tags)
        }

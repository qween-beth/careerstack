import os
import logging
from typing import Dict, Any, List
import scrapy
from scrapy.crawler import CrawlerProcess
from scrapy.http import Request
from itemloaders import ItemLoader
from itemloaders.processors import TakeFirst, Join
from pydantic import BaseModel, Field

class WebResearchConfig(BaseModel):
    allowed_domains: List[str] = Field(default_factory=list)
    start_urls: List[str] = Field(default_factory=list)
    extract_rules: Dict[str, str] = Field(default_factory=dict)

class ResearchItem(scrapy.Item):
    title = scrapy.Field()
    content = scrapy.Field()
    url = scrapy.Field()
    metadata = scrapy.Field()

class WebResearchSpider(scrapy.Spider):
    name = 'research_spider'
    
    def __init__(self, config: WebResearchConfig, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = config
        self.allowed_domains = config.allowed_domains
        self.start_urls = config.start_urls
    
    def parse(self, response):
        # Create research item
        item_loader = ItemLoader(item=ResearchItem(), response=response)
        
        # Extract metadata based on configuration
        item_loader.add_value('url', response.url)
        item_loader.add_value('title', response.css('title::text').get())
        
        # Custom extraction rules
        for field, selector in self.config.extract_rules.items():
            item_loader.add_css(field, selector)
        
        # Fallback full page text extraction
        content_selectors = [
            'div.content', 'article', 'main', 
            'div[class*="content"]', 'div[id*="content"]'
        ]
        
        for selector in content_selectors:
            content = response.css(f'{selector}::text').getall()
            if content:
                item_loader.add_value('content', ' '.join(content))
                break
        
        yield item_loader.load_item()
        
        # Follow links if needed
        for href in response.css('a::attr(href)').getall():
            yield response.follow(href, self.parse)

class ScrapyWebResearchAgent:
    def __init__(self, query: str):
        self.query = query
        self.results = []
        
    def configure_research(self) -> WebResearchConfig:
        """
        Dynamically configure research based on query
        
        Returns:
            WebResearchConfig with research parameters
        """
        # Example configuration (would be more dynamic in practice)
        return WebResearchConfig(
            allowed_domains=['wikipedia.org', 'nature.com'],
            start_urls=[f'https://en.wikipedia.org/wiki/{self.query.replace(" ", "_")}'],
            extract_rules={
                'metadata': 'meta[name="description"]::attr(content)',
                'sections': 'div.mw-parser-output > p'
            }
        )
    
    def run_research(self) -> List[Dict[str, Any]]:
        """
        Execute web research using Scrapy
        
        Returns:
            List of research findings
        """
        # Configure research parameters
        config = self.configure_research()
        
        # Prepare results storage
        self.results = []
        
        # Configure Scrapy crawler
        process = CrawlerProcess(settings={
            'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'ROBOTSTXT_OBEY': True,
            'DOWNLOAD_DELAY': 1,  # Respectful crawling
            'CONCURRENT_REQUESTS': 1
        })
        
        # Custom pipeline to collect results
        class ResultsPipeline:
            def process_item(self, item, spider):
                self.results.append(dict(item))
                return item
        
        process.crawl(WebResearchSpider, config=config)
        process.start()
        
        return self.results



# Dependency requirements
# pip install scrapy itemloaders pydantic
import requests
from bs4 import BeautifulSoup
import re
import json
from typing import Dict, List, Optional
import time
import logging

# Import the OSDR scrapper
from fastapi_backend.rag_module.osdr_scrapper import extract_all_sections

class PaperScraper:
    """
    Enhanced paper scraper using OSDR scrapper for comprehensive section extraction.
    Handles error cases and provides fallback mechanisms.
    """
    
    def __init__(self, timeout: int = 30, delay: float = 1.0):
        """
        Initialize the paper scraper.
        
        Args:
            timeout: Request timeout in seconds
            delay: Delay between requests in seconds
        """
        self.timeout = timeout
        self.delay = delay
        self.logger = logging.getLogger(__name__)
        
        # Headers for web scraping
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
    
    def scrape_paper(self, url: str) -> Dict[str, any]:
        """
        Scrape a research paper and extract all sections using OSDR scrapper.
        
        Args:
            url: URL of the research paper
            
        Returns:
            Dict containing all extracted sections and metadata
        """
        try:
            self.logger.info(f"Scraping paper: {url}")
            
            # First, try the OSDR scrapper
            sections = self._scrape_with_osdr(url)
            
            if sections and self._is_valid_content(sections):
                self.logger.info(f"Successfully scraped paper with OSDR scrapper")
                return self._process_sections(sections, url)
            
            # Fallback to basic scraping if OSDR fails
            self.logger.warning(f"OSDR scrapper failed, trying fallback method for {url}")
            return self._scrape_fallback(url)
            
        except Exception as e:
            self.logger.error(f"Error scraping {url}: {str(e)}")
            return self._create_empty_content(url)
    
    def _scrape_with_osdr(self, url: str) -> Optional[Dict]:
        """
        Use OSDR scrapper to extract all sections.
        
        Args:
            url: URL of the paper
            
        Returns:
            Dict of extracted sections or None if failed
        """
        try:
            # Add delay to be respectful
            time.sleep(self.delay)
            
            # Use the OSDR scrapper
            sections = extract_all_sections(url)
            return sections
            
        except Exception as e:
            self.logger.error(f"OSDR scrapper failed for {url}: {str(e)}")
            return None
    
    def _scrape_fallback(self, url: str) -> Dict[str, any]:
        """
        Fallback scraping method using basic BeautifulSoup extraction.
        
        Args:
            url: URL of the paper
            
        Returns:
            Dict containing basic extracted content
        """
        try:
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            content = {
                'title': '',
                'abstract': '',
                'results': '',
                'full_text': '',
                'sections': {},
                'authors': [],
                'keywords': '',
                'figures': [],
                'tables': []
            }
            
            # Extract title
            title_elem = soup.find('h1', class_='content-title')
            if not title_elem:
                title_elem = soup.find('h1')
            if title_elem:
                content['title'] = title_elem.get_text(strip=True)
            
            # Extract abstract
            abstract_section = soup.find(['div', 'section', 'p'], 
                                        class_=re.compile(r'abstract', re.I))
            if not abstract_section:
                abstract_section = soup.find(['div', 'section'], 
                                            id=re.compile(r'abstract', re.I))
            if abstract_section:
                content['abstract'] = abstract_section.get_text(strip=True, separator=' ')
            
            # Extract results section
            results_section = soup.find(['div', 'section'], 
                                       class_=re.compile(r'results?', re.I))
            if not results_section:
                results_section = soup.find(['div', 'section'], 
                                          id=re.compile(r'results?', re.I))
            if results_section:
                content['results'] = results_section.get_text(strip=True, separator=' ')
            
            # Extract full text with better filtering
            content['full_text'] = self._extract_filtered_content(soup)
            
            # Clean up
            for key in ['abstract', 'results', 'full_text']:
                content[key] = re.sub(r'\s+', ' ', content[key]).strip()
            
            return content
            
        except Exception as e:
            self.logger.error(f"Fallback scraping failed for {url}: {str(e)}")
            return self._create_empty_content(url)

    def _process_sections(self, sections: Dict, url: str) -> Dict[str, any]:
        """
        Process sections extracted by OSDR scrapper into standardized format.
        
        Args:
            sections: Raw sections from OSDR scrapper
            url: Original URL
            
        Returns:
            Processed content dictionary
        """
        content = {
            'title': sections.get('title', ''),
            'abstract': sections.get('abstract', ''),
            'results': '',
            'full_text': '',
            'sections': {},
            'authors': sections.get('authors', []),
            'keywords': sections.get('keywords', ''),
            'figures': sections.get('figures', []),
            'tables': sections.get('tables', []),
            'url': url
        }
        
        # Extract results section from sections
        for key, value in sections.items():
            if isinstance(value, dict) and 'title' in value:
                section_title = value['title'].lower()
                if 'result' in section_title:
                    content['results'] = value['content']
                    break
        
        # Process all sections with filtering
        section_texts = []
        for key, value in sections.items():
            if isinstance(value, dict) and 'title' in value and 'content' in value:
                content['sections'][key] = value
                
                # Filter out references and other non-essential sections
                if not self._should_exclude_section(value['title']):
                    section_texts.append(value['content'])
            elif isinstance(value, str) and key in ['abstract', 'title']:
                section_texts.append(value)
        
        # Combine all text for full_text with proper formatting
        content['full_text'] = self._format_full_text(section_texts)
        
        # Clean up text
        for key in ['abstract', 'results', 'full_text']:
            content[key] = re.sub(r'\s+', ' ', content[key]).strip()
        
        return content

    def _should_exclude_section(self, section_title: str) -> bool:
        """
        Determine if a section should be excluded from full_text.
        
        Args:
            section_title: Title of the section
            
        Returns:
            True if section should be excluded, False otherwise
        """
        title_lower = section_title.lower()
        
        # Sections to exclude
        exclude_patterns = [
            'references',
            'bibliography',
            'acknowledgments',
            'acknowledgements',
            'appendix',
            'appendices',
            'supplementary',
            'supplement',
            'author information',
            'competing interests',
            'conflicts of interest',
            'funding',
            'data availability',
            'ethics',
            'permissions',
            'copyright',
            'disclaimer',
            'notes',
            'footnotes'
        ]
        
        return any(pattern in title_lower for pattern in exclude_patterns)

    def _format_full_text(self, section_texts: List[str]) -> str:
        """
        Format the full text with proper structure and readability.
        
        Args:
            section_texts: List of section text content
            
        Returns:
            Formatted full text string
        """
        if not section_texts:
            return ""
        
        # Join sections with double newlines for better readability
        formatted_text = '\n\n'.join(section_texts)
        
        # Clean up excessive whitespace while preserving paragraph structure
        formatted_text = re.sub(r'\n\s*\n\s*\n+', '\n\n', formatted_text)  # Max 2 newlines
        formatted_text = re.sub(r'[ \t]+', ' ', formatted_text)  # Normalize spaces
        
        return formatted_text.strip()

    def _extract_filtered_content(self, soup: BeautifulSoup) -> str:
        """
        Extract content while filtering out references and other non-essential sections.
        
        Args:
            soup: BeautifulSoup object of the page
            
        Returns:
            Filtered and formatted content
        """
        # Find main content area
        content_divs = soup.find_all(['div', 'article', 'section'], 
                                    class_=re.compile(r'body|content|article'))
        
        if not content_divs:
            # Fallback to all paragraphs
            paragraphs = soup.find_all('p')
            content_elements = [p for p in paragraphs]
        else:
            content_elements = content_divs
        
        # Extract text from elements, filtering out references
        filtered_texts = []
        for element in content_elements:
            text = element.get_text(strip=True, separator=' ')
            if text and len(text) > 20:  # Filter out very short text
                # Check if this looks like a reference section
                if not self._looks_like_references(text):
                    filtered_texts.append(text)
        
        return '\n\n'.join(filtered_texts)

    def _looks_like_references(self, text: str) -> bool:
        """
        Check if text looks like a references section.
        
        Args:
            text: Text to check
            
        Returns:
            True if text appears to be references
        """
        text_lower = text.lower()
        
        # Patterns that indicate references
        reference_patterns = [
            r'^\s*\[\d+\]',  # Starts with [1], [2], etc.
            r'^\s*\d+\.\s*[A-Z]',  # Starts with "1. Author"
            r'^\s*\d+\)\s*[A-Z]',  # Starts with "1) Author"
            r'et al\.',  # Contains "et al."
            r'doi:',  # Contains DOI
            r'http[s]?://',  # Contains URLs
            r'vol\.|volume|pp\.|pages|journal|proceedings',  # Common reference terms
        ]
        
        # Check if text matches reference patterns
        for pattern in reference_patterns:
            if re.search(pattern, text_lower):
                return True
        
        # Check if text is mostly citations (short lines with numbers)
        lines = text.split('\n')
        if len(lines) > 3:
            citation_like_lines = 0
            for line in lines[:10]:  # Check first 10 lines
                line = line.strip()
                if len(line) < 200 and (re.match(r'^\s*\[\d+\]', line) or 
                                      re.match(r'^\s*\d+\.', line) or
                                      'et al.' in line):
                    citation_like_lines += 1
            
            # If more than 50% of lines look like citations, it's probably references
            if citation_like_lines / min(len(lines), 10) > 0.5:
                return True
        
        return False
    
    def _is_valid_content(self, sections: Dict) -> bool:
        """
        Check if the scraped content is valid and useful.
        
        Args:
            sections: Extracted sections
            
        Returns:
            True if content is valid, False otherwise
        """
        if not sections:
            return False
        
        # Check if we have at least a title or abstract
        has_title = bool(sections.get('title', '').strip())
        has_abstract = bool(sections.get('abstract', '').strip())
        has_sections = any(isinstance(v, dict) and 'content' in v for v in sections.values())
        
        return has_title or has_abstract or has_sections
    
    def _create_empty_content(self, url: str) -> Dict[str, any]:
        """
        Create empty content structure when scraping fails.
        
        Args:
            url: Original URL
            
        Returns:
            Empty content dictionary
        """
        return {
            'title': '',
            'abstract': '',
            'results': '',
            'full_text': '',
            'sections': {},
            'authors': [],
            'keywords': '',
            'figures': [],
            'tables': [],
            'url': url,
            'error': 'Failed to scrape content'
        }
    
    def batch_scrape(self, urls: List[str]) -> List[Dict[str, any]]:
        """
        Scrape multiple papers in batch.
        
        Args:
            urls: List of paper URLs
            
        Returns:
            List of scraped content dictionaries
        """
        results = []
        
        for i, url in enumerate(urls):
            self.logger.info(f"Scraping {i+1}/{len(urls)}: {url}")
            content = self.scrape_paper(url)
            results.append(content)
            
            # Add delay between requests
            if i < len(urls) - 1:
                time.sleep(self.delay)
        
        return results

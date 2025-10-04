import requests
from bs4 import BeautifulSoup
import re
import json

def extract_all_sections(url):
    """
    Extract all sections from a PMC research paper
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/115.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }
    
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, "html.parser")
    
    # Dictionary to store all extracted sections
    sections = {}
    
    # 1. Extract title
    title = soup.find("h1", {"class": "content-title"})
    if title:
        sections['title'] = title.get_text(strip=True)
    
    # 2. Extract authors from meta tags
    authors = []
    author_meta_tags = soup.find_all("meta", {"name": "citation_author"})
    for author_meta in author_meta_tags:
        author_name = author_meta.get("content", "").strip()
        if author_name:
            authors.append(author_name)
    
    # Also try the old method as fallback
    if not authors:
        author_elements = soup.find_all("span", {"class": "authors-list"})
        for author in author_elements:
            authors.append(author.get_text(strip=True))
    
    if authors:
        sections['authors'] = authors
    
    # 3. Extract abstract
    abstract_section = soup.find(['div', 'section', 'p'], 
                                class_=re.compile(r'abstract', re.I))
    if abstract_section:
        # Get all paragraphs in abstract
        abstract_text = []
        for p in abstract_section.find_all('p'):
            abstract_text.append(p.get_text(strip=True))
        sections['abstract'] = '\n'.join(abstract_text)
    
    # 4. Extract keywords
    keyword_section = soup.find(['div', 'section', 'p'], 
                               class_=re.compile(r'keywords?', re.I))
    if keyword_section:
        keywords_text = keyword_section.get_text(strip=True)
        # Clean up keywords (remove "Keywords:" prefix)
        keywords_text = re.sub(r'^Keywords?:\s*', '', keywords_text, flags=re.I)
        sections['keywords'] = keywords_text
    
    # 5. Extract main content sections using pmc_sec_title class
    # Find all section headers with pmc_sec_title class
    section_headers = soup.find_all("h2", {"class": "pmc_sec_title"})
    
    for i, header in enumerate(section_headers):
        section_title = header.get_text(strip=True)
        
        # Find the parent section element
        parent_section = header.find_parent("section")
        if not parent_section:
            # If no parent section, look for the next section element
            current = header.next_sibling
            while current and current.name != 'section':
                current = current.next_sibling
            if current:
                parent_section = current
        
        # Extract content from the section
        content_elements = []
        if parent_section:
            # Get all paragraphs, divs, and lists in the section
            for element in parent_section.find_all(['p', 'div', 'li', 'ul', 'ol']):
                text = element.get_text(strip=True)
                if text and len(text) > 10:  # Filter out very short text
                    content_elements.append(text)
        
        # Store section content
        if content_elements:
            # Clean section title for key
            clean_title = section_title.lower().replace(" ", "_").replace("&", "and")
            sections[f'section_{i+1}_{clean_title}'] = {
                'title': section_title,
                'content': '\n'.join(content_elements)
            }
    
    # 6. Also try to extract sections by looking for specific patterns
    # This is a backup method in case the above doesn't work
    main_content = soup.find("div", {"class": "tsec"}) or soup.find("div", {"class": "body"})
    
    if main_content:
        # Look for h2 elements with section titles
        backup_headers = main_content.find_all("h2")
        for header in backup_headers:
            if header.get("class") and "pmc_sec_title" in header.get("class"):
                continue  # Skip if already processed above
            
            section_title = header.get_text(strip=True)
            
            # Get content following this header until next h2
            content_elements = []
            current = header.next_sibling
            
            while current:
                if current.name == 'h2':
                    break
                
                if hasattr(current, 'get_text'):
                    text = current.get_text(strip=True)
                    if text and len(text) > 10:
                        content_elements.append(text)
                
                current = current.next_sibling
            
            if content_elements:
                clean_title = section_title.lower().replace(" ", "_").replace("&", "and")
                sections[f'backup_section_{clean_title}'] = {
                    'title': section_title,
                    'content': '\n'.join(content_elements)
                }
    
    # 7. Extract figures and tables
    figures = []
    for fig in soup.find_all(['figure', 'div'], class_=re.compile(r'fig', re.I)):
        caption = fig.find(['figcaption', 'p'], class_=re.compile(r'caption', re.I))
        if caption:
            figures.append({
                'caption': caption.get_text(strip=True),
                'element': str(fig)
            })
    if figures:
        sections['figures'] = figures
    
    tables = []
    for table in soup.find_all('table'):
        caption = table.find_previous(['p', 'div'], class_=re.compile(r'caption', re.I))
        if caption:
            tables.append({
                'caption': caption.get_text(strip=True),
                'data': [[cell.get_text(strip=True) for cell in row.find_all(['td', 'th'])] 
                        for row in table.find_all('tr')]
            })
    if tables:
        sections['tables'] = tables
    
    return sections
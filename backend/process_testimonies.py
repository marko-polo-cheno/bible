#!/usr/bin/env python3
"""
Script to process .docx files from testimonies folder and create JSONL artifact.
Extracts content and links from each file.
"""

import os
import re
import json
from pathlib import Path
from docx import Document
from typing import List, Dict, Any
import argparse

def extract_links_from_text(text: str) -> List[str]:
    """Extract all URLs from text using regex."""
    # Pattern to match URLs starting with https://
    url_pattern = r'https://[^\s<>"{}|\\^`\[\]]+'
    links = re.findall(url_pattern, text)
    return links

def process_docx_file(file_path: Path) -> Dict[str, Any]:
    """Process a single .docx file and extract content and links."""
    try:
        doc = Document(file_path)
        
        # Extract all text content
        full_text = []
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                full_text.append(paragraph.text.strip())
        
        content = '\n'.join(full_text)
        
        # Extract links from the content
        links = extract_links_from_text(content)
        
        # Get the main link (first one found, or empty string if none)
        main_link = links[0] if links else ""
        
        return {
            "filename": file_path.name,
            "content": content,
            "link": main_link,
            "all_links": links
        }
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return {
            "filename": file_path.name,
            "content": "",
            "link": "",
            "all_links": [],
            "error": str(e)
        }

def process_testimonies_folder(testimonies_path: str, output_path: str):
    """Process all .docx files in the testimonies folder and create JSONL file."""
    testimonies_dir = Path(testimonies_path)
    
    if not testimonies_dir.exists():
        raise FileNotFoundError(f"Testimonies directory not found: {testimonies_path}")
    
    # Find all .docx files
    docx_files = list(testimonies_dir.glob("*.docx"))
    print(f"Found {len(docx_files)} .docx files to process")
    
    # Process each file
    results = []
    for i, docx_file in enumerate(docx_files, 1):
        print(f"Processing {i}/{len(docx_files)}: {docx_file.name}")
        result = process_docx_file(docx_file)
        results.append(result)
    
    # Write to JSONL file
    with open(output_path, 'w', encoding='utf-8') as f:
        for result in results:
            f.write(json.dumps(result, ensure_ascii=False) + '\n')
    
    print(f"Processed {len(results)} files and saved to {output_path}")
    
    # Print summary statistics
    files_with_links = sum(1 for r in results if r.get('link'))
    total_links = sum(len(r.get('all_links', [])) for r in results)
    
    print(f"Summary:")
    print(f"  Total files processed: {len(results)}")
    print(f"  Files with links: {files_with_links}")
    print(f"  Total links found: {total_links}")

def main():
    parser = argparse.ArgumentParser(description='Process testimonies .docx files to JSONL')
    parser.add_argument('--testimonies-path', 
                       default='/Users/markchen/Desktop/learning/testimonies',
                       help='Path to testimonies folder')
    parser.add_argument('--output', 
                       default='/Users/markchen/Desktop/learning/bible/backend/testimonies.jsonl',
                       help='Output JSONL file path')
    
    args = parser.parse_args()
    
    process_testimonies_folder(args.testimonies_path, args.output)

if __name__ == "__main__":
    main()

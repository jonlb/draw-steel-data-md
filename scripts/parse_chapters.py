#!/usr/bin/env python3
"""
Parse chapter markdown files from Rules/Chapters into JSON format.
Extracts front matter and content, strips markdown links, and outputs to data/chapters.json
"""

import os
import json
import re
import yaml
from pathlib import Path


def parse_frontmatter(content):
    """
    Extract YAML frontmatter from markdown content.
    Returns tuple of (frontmatter_dict, remaining_content)
    """
    # Check if content starts with ---
    if not content.startswith('---'):
        return {}, content
    
    # Find the closing ---
    parts = content.split('---', 2)
    if len(parts) < 3:
        return {}, content
    
    frontmatter_text = parts[1].strip()
    remaining_content = parts[2].strip()
    
    # Parse YAML
    try:
        frontmatter = yaml.safe_load(frontmatter_text)
        return frontmatter if frontmatter else {}, remaining_content
    except yaml.YAMLError as e:
        print(f"Error parsing YAML frontmatter: {e}")
        return {}, content


def strip_markdown_links(text):
    """
    Remove markdown links from text, keeping only the link text.
    [link text](url) -> link text
    [link text][ref] -> link text
    """
    # Replace [text](url) with text
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    
    # Replace [text][ref] with text
    text = re.sub(r'\[([^\]]+)\]\[[^\]]*\]', r'\1', text)
    
    # Remove reference-style link definitions [ref]: url
    text = re.sub(r'^\[([^\]]+)\]:\s+.*$', '', text, flags=re.MULTILINE)
    
    return text


def parse_chapter_file(filepath):
    """
    Parse a single chapter markdown file.
    Returns a dictionary with frontmatter fields and content.
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    frontmatter, markdown_content = parse_frontmatter(content)
    
    # Strip markdown links from content
    clean_content = strip_markdown_links(markdown_content)
    
    # Create chapter object with frontmatter and content
    chapter = {**frontmatter, 'content': clean_content}
    
    return chapter


def parse_all_chapters(chapters_dir):
    """
    Parse all chapter files in the directory.
    Returns a list of chapter dictionaries.
    """
    chapters = []
    
    # Get all markdown files except _Index.md
    md_files = [f for f in os.listdir(chapters_dir) 
                if f.endswith('.md') and f != '_Index.md']
    
    for filename in sorted(md_files):
        filepath = os.path.join(chapters_dir, filename)
        print(f"Parsing {filename}...")
        
        try:
            chapter = parse_chapter_file(filepath)
            chapters.append(chapter)
        except Exception as e:
            print(f"Error parsing {filename}: {e}")
    
    return chapters


def main():
    # Set up paths
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    chapters_dir = project_root / 'Rules' / 'Chapters'
    data_dir = project_root / 'data'
    output_file = data_dir / 'chapters.json'
    
    # Create data directory if it doesn't exist
    data_dir.mkdir(exist_ok=True)
    
    # Parse all chapters
    print(f"Parsing chapters from {chapters_dir}...")
    chapters = parse_all_chapters(chapters_dir)
    
    # Write to JSON file
    print(f"\nWriting {len(chapters)} chapters to {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(chapters, f, indent=2, ensure_ascii=False)
    
    print(f"Done! Chapters saved to {output_file}")


if __name__ == '__main__':
    main()

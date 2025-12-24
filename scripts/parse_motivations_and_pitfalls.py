#!/usr/bin/env python3
"""
Parser for Draw Steel Motivations and Pitfalls markdown files.
Extracts motivation/pitfall information and converts to JSON format.
Treated like chapters - content for display purposes.
"""

import os
import re
import json
import yaml

def strip_markdown_links(text):
    """Remove markdown link syntax, keeping only the link text."""
    if not text:
        return text
    # Replace [text](url) with just text
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    return text

def parse_motivation_file(filepath):
    """Parse a single motivation/pitfall markdown file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Split frontmatter and content
    parts = content.split('---', 2)
    if len(parts) < 3:
        return None
    
    # Parse YAML frontmatter
    try:
        frontmatter = yaml.safe_load(parts[1])
    except yaml.YAMLError:
        return None
    
    main_content = parts[2].strip()
    
    # Strip markdown links from content
    main_content = strip_markdown_links(main_content)
    
    # Build the motivation object
    motivation = {
        'item_id': frontmatter.get('item_id'),
        'item_name': frontmatter.get('item_name'),
        'item_index': frontmatter.get('item_index'),
        'source': frontmatter.get('source'),
        'type': frontmatter.get('type'),
        'content': main_content
    }
    
    return motivation

def main():
    # Paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    motivations_dir = os.path.join(project_root, 'Rules', 'Negotiation', 'Motivations and Pitfalls')
    output_file = os.path.join(project_root, 'data', 'motivations_and_pitfalls.json')
    
    print(f"Parsing motivations and pitfalls from {motivations_dir}...")
    
    # Get all markdown files
    motivation_files = [f for f in os.listdir(motivations_dir) 
                        if f.endswith('.md')]
    
    motivations = []
    for filename in sorted(motivation_files):
        filepath = os.path.join(motivations_dir, filename)
        print(f"Parsing {filename}...")
        motivation = parse_motivation_file(filepath)
        if motivation:
            motivations.append(motivation)
    
    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    # Write to JSON file
    print(f"Writing {len(motivations)} motivations/pitfalls to {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(motivations, f, indent=2, ensure_ascii=False)
    
    print(f"Done! Motivations and pitfalls saved to {output_file}")

if __name__ == '__main__':
    main()

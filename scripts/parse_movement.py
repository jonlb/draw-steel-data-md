#!/usr/bin/env python3
"""
Parser for Draw Steel Movement markdown files.
Extracts movement information and converts to JSON format.
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

def parse_movement_file(filepath):
    """Parse a single movement markdown file."""
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
    
    # Build the movement object
    movement = {
        'item_id': frontmatter.get('item_id'),
        'item_name': frontmatter.get('item_name'),
        'item_index': frontmatter.get('item_index'),
        'source': frontmatter.get('source'),
        'type': frontmatter.get('type'),
        'content': main_content
    }
    
    return movement

def main():
    # Paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    movement_dir = os.path.join(project_root, 'Rules', 'Movement')
    output_file = os.path.join(project_root, 'data', 'movement.json')
    
    print(f"Parsing movement files from {movement_dir}...")
    
    # Get all markdown files except _Index.md
    movement_files = [f for f in os.listdir(movement_dir) 
                      if f.endswith('.md') and f != '_Index.md']
    
    movements = []
    for filename in sorted(movement_files):
        filepath = os.path.join(movement_dir, filename)
        print(f"Parsing {filename}...")
        movement = parse_movement_file(filepath)
        if movement:
            movements.append(movement)
    
    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    # Write to JSON file
    print(f"Writing {len(movements)} movement entries to {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(movements, f, indent=2, ensure_ascii=False)
    
    print(f"Done! Movement entries saved to {output_file}")

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Parse condition markdown files from Rules/Conditions directory into structured JSON.
"""

import os
import re
import json
import yaml
from pathlib import Path


def parse_frontmatter(content):
    """Extract YAML frontmatter from markdown content."""
    frontmatter_pattern = r'^---\s*\n(.*?)\n---\s*\n'
    match = re.match(frontmatter_pattern, content, re.DOTALL)
    
    if match:
        frontmatter_text = match.group(1)
        try:
            return yaml.safe_load(frontmatter_text), content[match.end():]
        except yaml.YAMLError:
            return {}, content
    return {}, content


def strip_markdown_links(text):
    """Remove markdown link syntax, keeping only the link text."""
    return re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)


def parse_condition_file(file_path):
    """Parse a single condition markdown file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Parse frontmatter
    frontmatter, remaining_content = parse_frontmatter(content)
    
    # Remove the heading (##### Condition Name)
    remaining_content = re.sub(r'^#{1,6}\s+[^\n]+\n+', '', remaining_content, count=1)
    
    # Strip markdown links from content
    content_text = strip_markdown_links(remaining_content.strip())
    
    # Build condition object
    condition = {
        "item_id": frontmatter.get("item_id", ""),
        "item_name": frontmatter.get("item_name", ""),
        "item_index": frontmatter.get("item_index", ""),
        "source": frontmatter.get("source", ""),
        "content": content_text
    }
    
    return condition


def main():
    # Get the project root directory
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    conditions_dir = project_root / "Rules" / "Conditions"
    output_file = project_root / "data" / "conditions.json"
    
    print(f"Parsing conditions from {conditions_dir}...")
    
    conditions = []
    
    # Process each markdown file in the directory
    for file_path in sorted(conditions_dir.glob("*.md")):
        # Skip _Index.md files
        if file_path.name.startswith("_"):
            continue
        
        print(f"Parsing {file_path.name}...")
        condition = parse_condition_file(file_path)
        conditions.append(condition)
    
    # Write to JSON file
    print(f"Writing {len(conditions)} conditions to {output_file}...")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(conditions, f, indent=2, ensure_ascii=False)
    
    print(f"Done! Conditions saved to {output_file}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Parse complication markdown files from Rules/Complications into JSON format.
Extracts front matter, description, and structured benefit/drawback mechanics.
Outputs to data/complications.json
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
    if not content.startswith('---'):
        return {}, content
    
    parts = content.split('---', 2)
    if len(parts) < 3:
        return {}, content
    
    frontmatter_text = parts[1].strip()
    remaining_content = parts[2].strip()
    
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


def parse_benefit_drawback_section(text):
    """
    Parse a benefit or drawback section to determine its type and structure.
    Returns a dictionary with type and structured content.
    """
    if not text:
        return None
    
    text = text.strip()
    
    # Check for test outcomes with tiered results
    if re.search(r'[≤<]11:', text) or re.search(r'12-16:', text) or re.search(r'17\+:', text):
        # Extract the introductory text before outcomes
        intro_match = re.match(r'^(.*?)(?=\n\s*[-•≤<])', text, re.DOTALL)
        intro_text = intro_match.group(1).strip() if intro_match else ""
        
        # Extract outcomes
        outcomes = []
        tier_pattern = r'^\s*[-•]?\s*\*\*([≤<]11|12-16|17\+):\*\*\s*(.+?)(?=\n\s*[-•]?\s*\*\*(?:[≤<]11|12-16|17\+):|$)'
        for match in re.finditer(tier_pattern, text, re.MULTILINE | re.DOTALL):
            tier = match.group(1)
            effect = match.group(2).strip()
            outcomes.append({
                "tier": tier,
                "effect": effect
            })
        
        if outcomes:
            return {
                "type": "test",
                "text": intro_text,
                "outcomes": outcomes
            }
    
    # Check for resource tracking (contains points, charges, etc.)
    if re.search(r'\d+\s+(?:destiny points|charges|uses)', text, re.IGNORECASE):
        return {
            "type": "resource",
            "text": text
        }
    
    # Check for choice mechanics
    if re.search(r'choose|select|pick', text, re.IGNORECASE):
        return {
            "type": "choice",
            "text": text
        }
    
    # Check for conditional triggers
    if re.search(r'whenever|when|if|while', text, re.IGNORECASE):
        return {
            "type": "conditional",
            "text": text
        }
    
    # Default to simple
    return {
        "type": "simple",
        "text": text
    }


def parse_complication_content(content):
    """
    Parse the markdown content to extract description and mechanics.
    Returns dict with 'description' and 'mechanics' (benefit/drawback).
    """
    # Remove the header (#### Title)
    content = re.sub(r'^####\s+.*$', '', content, flags=re.MULTILINE).strip()
    
    # Split into description and mechanics sections
    benefit_match = re.search(r'\*\*Benefit(?:\s+and\s+Drawback)?:\*\*\s*(.+?)(?=\*\*(?:Drawback|Benefit)|$)', content, re.DOTALL)
    drawback_match = re.search(r'\*\*Drawback:\*\*\s*(.+?)(?=\*\*Benefit|$)', content, re.DOTALL)
    
    # Extract description (everything before Benefit/Drawback)
    desc_match = re.match(r'^(.*?)(?=\*\*(?:Benefit|Drawback))', content, re.DOTALL)
    description = desc_match.group(1).strip() if desc_match else ""
    
    # Parse benefit and drawback
    benefit = None
    drawback = None
    
    if benefit_match:
        benefit_text = benefit_match.group(1).strip()
        benefit = parse_benefit_drawback_section(benefit_text)
    
    if drawback_match:
        drawback_text = drawback_match.group(1).strip()
        drawback = parse_benefit_drawback_section(drawback_text)
    
    # Handle "Benefit and Drawback" combined sections
    if "Benefit and Drawback:" in content and not drawback_match:
        # This is a combined section, store in benefit only
        pass
    
    return {
        "description": description,
        "mechanics": {
            "benefit": benefit,
            "drawback": drawback
        }
    }


def parse_complication_file(filepath):
    """
    Parse a single complication markdown file.
    Returns a dictionary with all complication data.
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    frontmatter, markdown_content = parse_frontmatter(content)
    
    # Strip markdown links from content
    clean_content = strip_markdown_links(markdown_content)
    
    # Parse the content structure
    parsed_content = parse_complication_content(clean_content)
    
    # Build the complication object
    complication = {
        **frontmatter,
        "name": frontmatter.get('item_name', ''),
        "description": parsed_content['description'],
        "mechanics": parsed_content['mechanics']
    }
    
    return complication


def parse_all_complications(complications_dir):
    """
    Parse all complication files in the directory.
    Returns a list of complication dictionaries.
    """
    complications = []
    
    # Get all markdown files except _Index.md
    md_files = [f for f in os.listdir(complications_dir) 
                if f.endswith('.md') and f != '_Index.md']
    
    for filename in sorted(md_files):
        filepath = os.path.join(complications_dir, filename)
        print(f"Parsing {filename}...")
        
        try:
            complication = parse_complication_file(filepath)
            complications.append(complication)
        except Exception as e:
            print(f"Error parsing {filename}: {e}")
            import traceback
            traceback.print_exc()
    
    return complications


def main():
    # Set up paths
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    complications_dir = project_root / 'Rules' / 'Complications'
    data_dir = project_root / 'data'
    output_file = data_dir / 'complications.json'
    
    # Create data directory if it doesn't exist
    data_dir.mkdir(exist_ok=True)
    
    # Parse all complications
    print(f"Parsing complications from {complications_dir}...")
    complications = parse_all_complications(complications_dir)
    
    # Write to JSON file
    print(f"\nWriting {len(complications)} complications to {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(complications, f, indent=2, ensure_ascii=False)
    
    print(f"Done! Complications saved to {output_file}")


if __name__ == '__main__':
    main()

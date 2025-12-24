#!/usr/bin/env python3
"""
Parse environment markdown files from Rules/Cultures/Environments directory into structured JSON.
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


def parse_quick_build(text):
    """Extract quick build value from parentheses."""
    match = re.search(r'\(\*Quick Build:\*\s*([^)]+)\)', text)
    if match:
        return match.group(1).strip().rstrip('.')
    return None


def parse_skill_options(content):
    """Parse the Skill Options section."""
    skill_match = re.search(r'\*\*Skill Options:\*\*\s*([^\n]+)', content)
    
    if not skill_match:
        return None
    
    skill_text = skill_match.group(1)
    quick_build = parse_quick_build(skill_text)
    
    # Remove quick build from description
    description = re.sub(r'\s*\(\*Quick Build:\*[^)]+\)', '', skill_text).strip()
    
    # Parse choice - look for "One skill from the X or Y skill groups" pattern
    choice = None
    
    # Pattern: "One skill from the X or Y skill groups"
    or_pattern = r'(One|Two|Three|Four)\s+skills?\s+from\s+the\s+(\w+)\s+or\s+(\w+)\s+skill\s+groups?'
    or_match = re.search(or_pattern, skill_text, re.IGNORECASE)
    
    if or_match:
        number_str = or_match.group(1).lower()
        group1 = or_match.group(2)
        group2 = or_match.group(3)
        
        number_map = {"one": 1, "two": 2, "three": 3, "four": 4}
        number = number_map.get(number_str, 1)
        
        choice = {
            "number": number,
            "group": {
                "names": [group1, group2],
                "type": "or"
            }
        }
    else:
        # Pattern: "One skill from the X skill group"
        single_pattern = r'(One|Two|Three|Four)\s+skills?\s+from\s+the\s+(\w+)\s+skill\s+groups?'
        single_match = re.search(single_pattern, skill_text, re.IGNORECASE)
        
        if single_match:
            number_str = single_match.group(1).lower()
            group = single_match.group(2)
            
            number_map = {"one": 1, "two": 2, "three": 3, "four": 4}
            number = number_map.get(number_str, 1)
            
            choice = {
                "number": number,
                "group": {
                    "names": [group],
                    "type": "from"
                }
            }
    
    return {
        "description": description,
        "choice": choice,
        "quick_build": quick_build
    }


def parse_environment_file(file_path):
    """Parse a single environment markdown file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Parse frontmatter
    frontmatter, remaining_content = parse_frontmatter(content)
    
    # Remove the heading (##### Environment Name)
    remaining_content = re.sub(r'^#{1,6}\s+[^\n]+\n+', '', remaining_content, count=1)
    
    # Split at "Skill Options:"
    parts = re.split(r'\*\*Skill Options:\*\*', remaining_content, maxsplit=1)
    
    # Description is everything before "Skill Options:"
    description = parts[0].strip() if parts else remaining_content.strip()
    description = strip_markdown_links(description)
    
    # Parse skill options
    skill_options = parse_skill_options(remaining_content)
    
    # Build environment object
    environment = {
        "item_id": frontmatter.get("item_id", ""),
        "item_name": frontmatter.get("item_name", ""),
        "item_index": frontmatter.get("item_index", ""),
        "source": frontmatter.get("source", ""),
        "culture_benefit_type": frontmatter.get("culture_benefit_type", ""),
        "description": description,
        "skill_options": skill_options
    }
    
    return environment


def main():
    # Get the project root directory
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    environments_dir = project_root / "Rules" / "Cultures" / "Environments"
    output_file = project_root / "data" / "environments.json"
    
    print(f"Parsing environments from {environments_dir}...")
    
    environments = []
    
    # Process each markdown file in the directory
    for file_path in sorted(environments_dir.glob("*.md")):
        print(f"Parsing {file_path.name}...")
        environment = parse_environment_file(file_path)
        environments.append(environment)
    
    # Write to JSON file
    print(f"Writing {len(environments)} environments to {output_file}...")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(environments, f, indent=2, ensure_ascii=False)
    
    print(f"Done! Environments saved to {output_file}")


if __name__ == "__main__":
    main()

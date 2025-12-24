#!/usr/bin/env python3
"""
Parser for Draw Steel Skills markdown files.
Extracts skill group and individual skill information and converts to JSON format.
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

def parse_skills_table(content):
    """Extract individual skills from the markdown table."""
    skills = []
    
    # Find the skills table
    table_match = re.search(r'\| Skill\s+\| Use\s+\|(.+?)(?=\n\n|$)', content, re.DOTALL)
    if not table_match:
        return skills
    
    table_content = table_match.group(1)
    
    # Parse each row (skip the separator line with dashes)
    for line in table_content.split('\n'):
        if '|' not in line or '---' in line:
            continue
        
        # Split by | and clean up
        parts = [p.strip() for p in line.split('|')]
        # Filter out empty strings from leading/trailing |
        parts = [p for p in parts if p]
        
        if len(parts) >= 2:
            skill_name = parts[0].strip()
            skill_use = parts[1].strip()
            
            skills.append({
                'name': skill_name,
                'use': strip_markdown_links(skill_use)
            })
    
    return skills

def parse_skill_group_file(filepath):
    """Parse a single skill group markdown file."""
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
    
    main_content = parts[2]
    
    # Extract description (first paragraph after the heading, before table)
    desc_match = re.search(r'##### .+?\n\n(.+?)(?=\n#|$)', main_content, re.DOTALL)
    description = None
    if desc_match:
        # Get text up to the table or next section
        desc_text = desc_match.group(1)
        # Stop at the table heading
        if '###### ' in desc_text:
            desc_text = desc_text.split('######')[0]
        description = desc_text.strip()
        description = strip_markdown_links(description)
    
    # Extract rewards paragraph
    rewards_match = re.search(r'Rewards for tests made with \w+ skills typically include (.+?)(?=\n\n|Consequences)', main_content, re.DOTALL)
    typical_rewards = None
    if rewards_match:
        typical_rewards = rewards_match.group(1).strip()
        typical_rewards = strip_markdown_links(typical_rewards)
    
    # Extract consequences paragraph
    consequences_match = re.search(r'Consequences for tests made with \w+ skills (typically )?include (.+?)(?=\n\n|######)', main_content, re.DOTALL)
    typical_consequences = None
    if consequences_match:
        typical_consequences = consequences_match.group(2).strip()
        typical_consequences = strip_markdown_links(typical_consequences)
    
    # Parse the skills table
    skills = parse_skills_table(main_content)
    
    # Build the skill group object
    skill_group = {
        'item_id': frontmatter.get('item_id'),
        'item_name': frontmatter.get('item_name'),
        'item_index': frontmatter.get('item_index'),
        'source': frontmatter.get('source'),
        'type': frontmatter.get('type'),
        'description': description,
        'typical_rewards': typical_rewards,
        'typical_consequences': typical_consequences,
        'skills': skills
    }
    
    return skill_group

def main():
    # Paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    skills_dir = os.path.join(project_root, 'Rules', 'Skills')
    output_file = os.path.join(project_root, 'data', 'skills.json')
    
    print(f"Parsing skill groups from {skills_dir}...")
    
    # Get all markdown files except _Index.md
    skill_files = [f for f in os.listdir(skills_dir) 
                   if f.endswith('.md') and f != '_Index.md']
    
    skill_groups = []
    for filename in sorted(skill_files):
        filepath = os.path.join(skills_dir, filename)
        print(f"Parsing {filename}...")
        skill_group = parse_skill_group_file(filepath)
        if skill_group:
            skill_groups.append(skill_group)
    
    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    # Write to JSON file
    print(f"Writing {len(skill_groups)} skill groups to {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(skill_groups, f, indent=2, ensure_ascii=False)
    
    print(f"Done! Skill groups saved to {output_file}")

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Parser for Draw Steel Titles markdown files.
Extracts title information from echelon subdirectories and converts to JSON format.
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

def parse_abilities(content):
    """Extract structured abilities from content with blockquote format."""
    abilities = []
    
    # Find all ability blocks that start with ###### in a blockquote
    ability_pattern = r'>\s*######\s+(.+?)(?=\n>\s*######|\Z)'
    
    for match in re.finditer(ability_pattern, content, re.DOTALL):
        ability_content = match.group(0)
        
        # Extract ability name (may include resource cost in parentheses)
        name_match = re.search(r'######\s+([^(\n]+)(?:\(([^)]+)\))?', ability_content)
        if not name_match:
            continue
        
        ability_name = name_match.group(1).strip()
        resource_cost = name_match.group(2).strip() if name_match.group(2) else None
        
        # Extract heroic resource numeric value if present
        heroic_resource_cost = None
        if resource_cost and 'heroic resource' in resource_cost.lower():
            hr_match = re.search(r'(\d+)', resource_cost)
            if hr_match:
                heroic_resource_cost = int(hr_match.group(1))
        
        # Extract flavor text (italicized text after name, before table)
        # Match single asterisk (italic), not double asterisk (bold)
        flavor_match = re.search(r'>\s*\*([^*\n]+?)\*\s*(?=\n|\|)', ability_content)
        flavor_text = flavor_match.group(1).strip() if flavor_match else None
        
        # Extract keywords from table (first column, may have multiple bold segments)
        keywords_match = re.search(r'\|\s*(.+?)\s*\|', ability_content)
        keywords = None
        if keywords_match:
            # Extract all text from first column, remove bold markers and split by comma
            keywords_text = keywords_match.group(1).strip()
            keywords_text = re.sub(r'\*\*', '', keywords_text)  # Remove bold markers
            keywords = [k.strip() for k in keywords_text.split(',')]
        
        # Extract action type (matches "Main action", "Maneuver", etc.)
        action_match = re.search(r'\|\s*\*\*([^*]*(?:action|Maneuver|Triggered action)[^*]*)\*\*\s*\|', ability_content, re.IGNORECASE)
        action_type = action_match.group(1).strip() if action_match else None
        
        # Extract distance/range
        distance_match = re.search(r'\*\*📏\s*([^*]+)\*\*', ability_content)
        distance = distance_match.group(1).strip() if distance_match else None
        
        # Extract target
        target_match = re.search(r'\*\*🎯\s*([^*]+)\*\*', ability_content)
        target = target_match.group(1).strip() if target_match else None
        
        # Extract power roll
        power_roll_match = re.search(r'\*\*Power Roll \+ ([^:*]+):\*\*', ability_content)
        power_roll = power_roll_match.group(1).strip() if power_roll_match else None
        
        # Extract tier effects
        tier_effects = []
        tier_pattern = r'>\s*-\s*\*\*([≤\d\-+]+):\*\*\s*(.+?)(?=\n>\s*-|\n>\s*\n|\n\n|\Z)'
        for tier_match in re.finditer(tier_pattern, ability_content, re.DOTALL):
            tier = tier_match.group(1).strip()
            effect = tier_match.group(2).strip()
            tier_effects.append({
                'tier': tier,
                'effect': strip_markdown_links(effect)
            })
        
        # Extract effect (outside tier effects)
        effect_match = re.search(r'>\s*\*\*Effect:\*\*\s*(.+?)(?=\n>\s*\n|\n\n|\Z)', ability_content, re.DOTALL)
        effect = None
        if effect_match:
            effect = effect_match.group(1).strip()
            effect = strip_markdown_links(effect)
        
        ability = {
            'name': ability_name,
            'resource_cost': resource_cost,
            'heroic_resource_cost': heroic_resource_cost,
            'flavor_text': flavor_text,
            'keywords': keywords,
            'action_type': action_type,
            'distance': distance,
            'target': target,
            'power_roll': power_roll,
            'tier_effects': tier_effects if tier_effects else None,
            'effect': effect
        }
        
        abilities.append(ability)
    
    return abilities if abilities else None

def parse_title_file(filepath, echelon_dir):
    """Parse a single title markdown file."""
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
    
    # NOTE: In titles, <!-- --> is used as a separator before optional abilities
    # that ARE part of the title benefits, so we don't remove content after HTML comments
    
    # Extract flavor text (italicized text right after the heading)
    flavor_match = re.search(r'#### .+?\n\n\*(.+?)\*', main_content, re.DOTALL)
    flavor_text = None
    if flavor_match:
        flavor_text = flavor_match.group(1).strip()
        flavor_text = strip_markdown_links(flavor_text)
    
    # Extract prerequisite
    prereq_match = re.search(r'\*\*Prerequisite:\*\*\s*(.+?)(?=\n\n|\*\*Effect)', main_content, re.DOTALL)
    prerequisite = None
    if prereq_match:
        prerequisite = prereq_match.group(1).strip()
        prerequisite = strip_markdown_links(prerequisite)
    
    # Extract effect
    effect_match = re.search(r'\*\*Effect:\*\*\s*(.+?)(?=\n\n\*\*Special|\Z)', main_content, re.DOTALL)
    effect = None
    if effect_match:
        effect = effect_match.group(1).strip()
        effect = strip_markdown_links(effect)
    
    # Extract special (optional)
    special_match = re.search(r'\*\*Special:\*\*\s*(.+?)(?=\n\n|\Z)', main_content, re.DOTALL)
    special = None
    if special_match:
        special = special_match.group(1).strip()
        special = strip_markdown_links(special)
    
    # Parse abilities from the content
    abilities = parse_abilities(main_content)
    
    # Build the title object
    title = {
        'item_id': frontmatter.get('item_id'),
        'item_name': frontmatter.get('item_name'),
        'item_index': frontmatter.get('item_index'),
        'source': frontmatter.get('source'),
        'type': frontmatter.get('type'),
        'echelon': frontmatter.get('echelon'),
        'flavor_text': flavor_text,
        'prerequisite': prerequisite,
        'effect': effect,
        'special': special,
        'abilities': abilities
    }
    
    return title

def main():
    # Paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    titles_dir = os.path.join(project_root, 'Rules', 'Titles')
    output_file = os.path.join(project_root, 'data', 'titles.json')
    
    print(f"Parsing titles from {titles_dir}...")
    
    # Get all echelon subdirectories
    echelon_dirs = [d for d in os.listdir(titles_dir) 
                    if os.path.isdir(os.path.join(titles_dir, d)) and 'Echelon' in d]
    
    titles = []
    for echelon_dir in sorted(echelon_dirs):
        echelon_path = os.path.join(titles_dir, echelon_dir)
        print(f"\nProcessing {echelon_dir}...")
        
        # Get all markdown files in this echelon directory
        title_files = [f for f in os.listdir(echelon_path) 
                       if f.endswith('.md')]
        
        for filename in sorted(title_files):
            filepath = os.path.join(echelon_path, filename)
            print(f"  Parsing {filename}...")
            title = parse_title_file(filepath, echelon_dir)
            if title:
                titles.append(title)
    
    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    # Write to JSON file
    print(f"\nWriting {len(titles)} titles to {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(titles, f, indent=2, ensure_ascii=False)
    
    print(f"Done! Titles saved to {output_file}")

if __name__ == '__main__':
    main()

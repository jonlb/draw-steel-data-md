#!/usr/bin/env python3
"""
Parser for Draw Steel Treasures markdown files.
Extracts treasure information from subdirectories and converts to JSON format.
Handles: Artifacts, Consumables (by echelon), Trinkets (by echelon), and Leveled Treasures (by type).
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

def extract_treasure_category_from_path(file_dpath):
    """Extract the treasure category from the file path."""
    # Examples: "Treasures/Artifacts", "Treasures/Consumables/1st Echelon Consumables"
    parts = file_dpath.split('/')
    if len(parts) >= 2:
        return parts[1]  # "Artifacts", "Consumables", "Trinkets", "Leveled Treasures"
    return None

def extract_subcategory_from_path(file_dpath):
    """Extract the subcategory (echelon or type) from nested directories."""
    # Examples: "1st Echelon Consumables", "Leveled Weapon Treasures"
    parts = file_dpath.split('/')
    if len(parts) >= 3:
        return parts[2]  # The subdirectory name
    return None

def parse_treasure_file(filepath):
    """Parse a single treasure markdown file."""
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
    
    # NOTE: Unlike perks, treasures use <!-- --> as a separator before ability blocks
    # that ARE part of the treasure, so we don't remove content after HTML comments
    
    # Strip markdown links from content
    main_content = strip_markdown_links(main_content)
    
    # Extract flavor text (italicized text right after the heading)
    flavor_match = re.search(r'##### .+?\n\n\*(.+?)\*', main_content, re.DOTALL)
    flavor_text = None
    if flavor_match:
        flavor_text = flavor_match.group(1).strip()
    
    # Get treasure category and subcategory from path
    file_dpath = frontmatter.get('file_dpath', '')
    treasure_category = extract_treasure_category_from_path(file_dpath)
    treasure_subcategory = extract_subcategory_from_path(file_dpath)
    
    # Parse abilities from the content
    abilities = parse_abilities(main_content)
    
    # Build the treasure object
    treasure = {
        'item_id': frontmatter.get('item_id'),
        'item_name': frontmatter.get('item_name'),
        'item_index': frontmatter.get('item_index'),
        'source': frontmatter.get('source'),
        'type': frontmatter.get('type'),
        'treasure_type': frontmatter.get('treasure_type'),
        'treasure_category': treasure_category,
        'treasure_subcategory': treasure_subcategory,
        'echelon': frontmatter.get('echelon'),
        'flavor_text': flavor_text,
        'content': main_content,
        'abilities': abilities
    }
    
    return treasure

def main():
    # Paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    treasures_dir = os.path.join(project_root, 'Rules', 'Treasures')
    output_file = os.path.join(project_root, 'data', 'treasures.json')
    
    print(f"Parsing treasures from {treasures_dir}...")
    
    treasures = []
    
    # Walk through all subdirectories
    for root, dirs, files in os.walk(treasures_dir):
        # Skip _Index directories
        dirs[:] = [d for d in dirs if not d.startswith('_')]
        
        # Get relative path for display
        rel_path = os.path.relpath(root, treasures_dir)
        if rel_path != '.':
            print(f"\nProcessing {rel_path}...")
        
        for filename in sorted(files):
            if filename.endswith('.md') and not filename.startswith('_'):
                filepath = os.path.join(root, filename)
                print(f"  Parsing {filename}...")
                treasure = parse_treasure_file(filepath)
                if treasure:
                    treasures.append(treasure)
    
    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    # Write to JSON file
    print(f"\nWriting {len(treasures)} treasures to {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(treasures, f, indent=2, ensure_ascii=False)
    
    print(f"Done! Treasures saved to {output_file}")

if __name__ == '__main__':
    main()

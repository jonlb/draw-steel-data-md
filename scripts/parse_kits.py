#!/usr/bin/env python3
"""
Parser for Draw Steel Kits markdown files.
Extracts kit information and converts to JSON format.
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

def parse_equipment(content):
    """Extract equipment description."""
    match = re.search(r'##### Equipment\s*\n\n(.+?)(?=\n\n|$)', content, re.DOTALL)
    if match:
        equipment = match.group(1).strip()
        equipment = strip_markdown_links(equipment)
        # Remove "You wear" or "You wield" prefix for cleaner data
        equipment = re.sub(r'^You (wear|wield)\s+', '', equipment)
        return equipment
    return None

def parse_kit_bonuses(content):
    """Extract all kit bonuses."""
    bonuses = {}
    
    # Find the Kit Bonuses section
    match = re.search(r'##### Kit Bonuses\s*\n\n(.+?)(?=\n##### |$)', content, re.DOTALL)
    if not match:
        return bonuses
    
    bonuses_text = match.group(1)
    
    # Parse each bonus type
    bonus_patterns = {
        'stamina_bonus': r'\*\*Stamina Bonus:\*\*\s*([+\d]+(?:\s+per\s+echelon)?)',
        'speed_bonus': r'\*\*Speed Bonus:\*\*\s*([+\d]+)',
        'stability_bonus': r'\*\*Stability Bonus:\*\*\s*([+\d]+)',
        'melee_damage_bonus': r'\*\*Melee Damage Bonus:\*\*\s*([\+\d/]+)',
        'ranged_damage_bonus': r'\*\*Ranged Damage Bonus:\*\*\s*([\+\d/]+)',
        'ranged_distance_bonus': r'\*\*Ranged Distance Bonus:\*\*\s*([+\d]+)',
        'disengage_bonus': r'\*\*Disengage Bonus:\*\*\s*([+\d]+)',
        'mobility_bonus': r'\*\*Mobility Bonus:\*\*\s*([+\d]+)',
    }
    
    for bonus_name, pattern in bonus_patterns.items():
        match = re.search(pattern, bonuses_text)
        if match:
            value = match.group(1)
            # Convert damage bonuses with "/" into arrays of integers
            if 'damage_bonus' in bonus_name and '/' in value:
                # Remove + signs and split by /
                bonuses[bonus_name] = [int(x.replace('+', '')) for x in value.split('/')]
            # Convert stamina bonus (may have "per echelon" text)
            elif bonus_name == 'stamina_bonus':
                # Extract just the number, keeping "per echelon" as part of the structure
                num_match = re.search(r'[+]?(\d+)', value)
                if num_match:
                    bonuses[bonus_name] = int(num_match.group(1))
            # Convert other numeric bonuses
            else:
                # Remove + sign and convert to int
                bonuses[bonus_name] = int(value.replace('+', ''))
    
    return bonuses

def parse_signature_ability(content):
    """Extract the signature ability."""
    # Find the signature ability section
    match = re.search(r'##### Signature Ability\s*\n\n###### (.+?)\n\n\*(.+?)\*\n\n(.+?)(?=\n---|\Z)', content, re.DOTALL)
    if not match:
        return None
    
    ability_name = match.group(1).strip()
    flavor_text = match.group(2).strip()
    ability_content = match.group(3).strip()
    
    ability = {
        'name': ability_name,
        'flavor_text': strip_markdown_links(flavor_text)
    }
    
    # Parse the ability table and details
    # Extract keywords from the table header
    keywords_match = re.search(r'\|\s*\*\*([^*]+)\*\*\s*\|', ability_content)
    if keywords_match:
        keywords_text = keywords_match.group(1).strip()
        ability['keywords'] = [k.strip() for k in keywords_text.split(',')]
    
    # Extract action type
    action_match = re.search(r'\|\s*\*\*([^*]+action)\*\*\s*\|', ability_content)
    if action_match:
        ability['action_type'] = action_match.group(1).strip()
    
    # Extract distance/range
    distance_match = re.search(r'\*\*📏\s*([^*]+)\*\*', ability_content)
    if distance_match:
        ability['distance'] = strip_markdown_links(distance_match.group(1).strip())
    
    # Extract target
    target_match = re.search(r'\*\*🎯\s*([^*]+)\*\*', ability_content)
    if target_match:
        ability['target'] = strip_markdown_links(target_match.group(1).strip())
    
    # Extract power roll
    power_roll_match = re.search(r'\*\*Power Roll \+ ([^:*]+):\*\*', ability_content)
    if power_roll_match:
        ability['power_roll'] = power_roll_match.group(1).strip()
    
    # Extract tier effects
    tier_effects = []
    tier_pattern = r'-\s*\*\*([≤\d\-+]+):\*\*\s*(.+?)(?=\n-|\n\n|\Z)'
    for tier_match in re.finditer(tier_pattern, ability_content, re.DOTALL):
        tier = tier_match.group(1).strip()
        effect = tier_match.group(2).strip()
        effect = strip_markdown_links(effect)
        tier_effects.append({
            'tier': tier,
            'effect': effect
        })
    
    if tier_effects:
        ability['tier_effects'] = tier_effects
    
    # Extract effect (outside the tier effects)
    effect_match = re.search(r'\*\*Effect:\*\*\s*(.+?)(?=\n\n|\Z)', ability_content, re.DOTALL)
    if effect_match:
        effect = effect_match.group(1).strip()
        ability['effect'] = strip_markdown_links(effect)
    
    return ability

def parse_primordial_storm(content):
    """Extract primordial storm."""
    match = re.search(r'##### Primordial Storm\s*\n\n(.+?)(?=\n##### |$)', content, re.DOTALL)
    if match:
        return strip_markdown_links(match.group(1).strip())
    return None

def parse_aspect_benefits(content):
    """Extract aspect benefits."""
    match = re.search(r'##### Aspect Benefits\s*\n\n(.+?)(?=\n##### |$)', content, re.DOTALL)
    if match:
        return strip_markdown_links(match.group(1).strip())
    return None

def parse_animal_form(content):
    """Extract animal form."""
    match = re.search(r'##### Animal Form: (.+?)\s*\n\n(.+?)(?=\n##### |$)', content, re.DOTALL)
    if match:
        return {
            'animal': match.group(1).strip(),
            'description': strip_markdown_links(match.group(2).strip())
        }
    return None

def parse_hybrid_form(content):
    """Extract hybrid form."""
    match = re.search(r'##### Hybrid Form: (.+?)\s*\n\n(.+?)(?=\n##### |$)', content, re.DOTALL)
    if match:
        return {
            'animal': match.group(1).strip(),
            'description': strip_markdown_links(match.group(2).strip())
        }
    return None

def parse_growing_ferocity(content):
    """Extract growing ferocity table."""
    match = re.search(r'##### Growing Ferocity\s*\n\n(.+?)(?=\n#### |\Z)', content, re.DOTALL)
    if match:
        table_text = match.group(1).strip()
        # Parse the table
        lines = table_text.split('\n')
        ferocity_data = []
        for line in lines:
            if '|' in line and not line.startswith('| ---'):
                cells = [cell.strip() for cell in line.split('|')[1:-1]]
                if len(cells) >= 2:
                    ferocity = cells[0]
                    benefit = cells[1]
                    ferocity_data.append({
                        'ferocity': ferocity,
                        'benefit': strip_markdown_links(benefit)
                    })
        return ferocity_data
    return None

def parse_kit_file(filepath):
    """Parse a single kit markdown file."""
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
    
    # Extract description (first paragraph after the kit name heading)
    desc_match = re.search(r'#### .+?\n\n(.+?)(?=\n##### |$)', main_content, re.DOTALL)
    description = None
    if desc_match:
        description = desc_match.group(1).strip()
        description = strip_markdown_links(description)
    
    # Build the kit object
    kit = {
        'item_id': frontmatter.get('item_id'),
        'item_name': frontmatter.get('item_name'),
        'item_index': frontmatter.get('item_index'),
        'source': frontmatter.get('source'),
        'type': frontmatter.get('type'),
        'description': description,
        'equipment': parse_equipment(main_content),
        'kit_bonuses': parse_kit_bonuses(main_content),
        'signature_ability': parse_signature_ability(main_content),
        'primordial_storm': parse_primordial_storm(main_content),
        'aspect_benefits': parse_aspect_benefits(main_content),
        'animal_form': parse_animal_form(main_content),
        'hybrid_form': parse_hybrid_form(main_content),
        'growing_ferocity': parse_growing_ferocity(main_content)
    }
    
    return kit

def parse_aspect_benefits(content):
    """Extract aspect benefits."""
    match = re.search(r'##### Aspect Benefits\s*\n\n(.+?)(?=\n##### |$)', content, re.DOTALL)
    if match:
        return strip_markdown_links(match.group(1).strip())
    return None

def parse_animal_form(content):
    """Extract animal form."""
    match = re.search(r'##### Animal Form: (.+?)\s*\n\n(.+?)(?=\n##### |$)', content, re.DOTALL)
    if match:
        return {
            'animal': match.group(1).strip(),
            'description': strip_markdown_links(match.group(2).strip())
        }
    return None

def parse_hybrid_form(content):
    """Extract hybrid form."""
    match = re.search(r'##### Hybrid Form: (.+?)\s*\n\n(.+?)(?=\n##### |$)', content, re.DOTALL)
    if match:
        return {
            'animal': match.group(1).strip(),
            'description': strip_markdown_links(match.group(2).strip())
        }
    return None

def parse_growing_ferocity(content):
    """Extract growing ferocity table."""
    match = re.search(r'##### Growing Ferocity\s*\n\n(.+?)(?=\n#### |\Z)', content, re.DOTALL)
    if match:
        table_text = match.group(1).strip()
        # Parse the table
        lines = table_text.split('\n')
        ferocity_data = []
        for line in lines:
            if '|' in line and not line.startswith('| ---'):
                cells = [cell.strip() for cell in line.split('|')[1:-1]]
                if len(cells) >= 2:
                    ferocity = cells[0]
                    benefit = cells[1]
                    ferocity_data.append({
                        'ferocity': ferocity,
                        'benefit': strip_markdown_links(benefit)
                    })
        return ferocity_data
    return None

def parse_stormwight_kit(content, kit_name):
    """Parse a single stormwight kit from content."""
    # Find the kit section
    pattern = rf'#### {re.escape(kit_name)}\s*\n\n(.+?)(?=\n#### |\Z)'
    match = re.search(pattern, content, re.DOTALL)
    if not match:
        return None
    
    kit_content = match.group(1)
    
    # Extract description
    desc_match = re.search(r'With this stormwight kit.+?\.(.+?)(?=\n##### |$)', kit_content, re.DOTALL)
    description = None
    if desc_match:
        description = desc_match.group(1).strip()
        description = strip_markdown_links(description)
    
    # Build the kit object
    kit = {
        'item_id': kit_name.lower(),
        'item_name': kit_name,
        'item_index': None,  # Will be set later
        'source': 'mcdm.heroes.v1',
        'type': 'kit',
        'description': description,
        'equipment': parse_equipment(kit_content),
        'kit_bonuses': parse_kit_bonuses(kit_content),
        'signature_ability': parse_signature_ability(kit_content),
        'primordial_storm': parse_primordial_storm(kit_content),
        'aspect_benefits': parse_aspect_benefits(kit_content),
        'animal_form': parse_animal_form(kit_content),
        'hybrid_form': parse_hybrid_form(kit_content),
        'growing_ferocity': parse_growing_ferocity(kit_content)
    }
    
    return kit

def parse_stormwight_kits(fury_content):
    """Parse all stormwight kits from Fury.md content."""
    kits = []
    stormwight_kits = ['Boren', 'Corven', 'Raden', 'Vuken']
    
    for kit_name in stormwight_kits:
        kit = parse_stormwight_kit(fury_content, kit_name)
        if kit:
            kits.append(kit)
    
    return kits

def main():
    # Paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    kits_dir = os.path.join(project_root, 'Rules', 'Kits')
    fury_file = os.path.join(project_root, 'Rules', 'Classes', 'Fury.md')
    output_file = os.path.join(project_root, 'data', 'kits.json')
    
    print(f"Parsing kits from {kits_dir}...")
    
    # Get all markdown files except _Index.md
    kit_files = [f for f in os.listdir(kits_dir) 
                 if f.endswith('.md') and f != '_Index.md' and f != 'Kits Table.md']
    
    kits = []
    for filename in sorted(kit_files):
        filepath = os.path.join(kits_dir, filename)
        print(f"Parsing {filename}...")
        kit = parse_kit_file(filepath)
        if kit:
            kits.append(kit)
    
    # Parse Stormwight Kits from Fury.md
    if os.path.exists(fury_file):
        print(f"Parsing Stormwight Kits from {fury_file}...")
        with open(fury_file, 'r', encoding='utf-8') as f:
            fury_content = f.read()
        stormwight_kits = parse_stormwight_kits(fury_content)
        kits.extend(stormwight_kits)
        print(f"Parsed {len(stormwight_kits)} Stormwight kits")
    
    # Assign item_index to new kits
    existing_indices = {kit['item_index'] for kit in kits if kit['item_index']}
    next_index = max([int(idx) for idx in existing_indices if idx.isdigit()], default=0) + 1
    for kit in kits:
        if kit['item_index'] is None:
            kit['item_index'] = str(next_index).zfill(2)
            next_index += 1
    
    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    # Write to JSON file
    print(f"Writing {len(kits)} kits to {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(kits, f, indent=2, ensure_ascii=False)
    
    print(f"Done! Kits saved to {output_file}")

if __name__ == '__main__':
    main()

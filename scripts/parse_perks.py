#!/usr/bin/env python3
"""
Parser for Draw Steel Perks markdown files.
Extracts perk information from subdirectories and converts to JSON format.
Each perk is simple text content for display, organized by perk group.
"""

import os
import re
import json
from typing import Dict, Any, Optional
import yaml

def strip_markdown_links(text):
    """Remove markdown link syntax, keeping only the link text."""
    if not text:
        return text
    # Replace [text](url) with just text
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    return text

def parse_stat_block(content):
    """Extract stat block information from content if present."""
    # Look for "X Statblock" heading (may be blockquoted)
    match = re.search(r'>?\s*#{6}\s+(.+?)\s+Statblock\s*\n', content, re.IGNORECASE)
    if not match:
        return None
    
    stat_block_name = match.group(1).strip()
    start_pos = match.end()
    
    # Find the end of the stat block section (next heading or end of content)
    next_heading = re.search(r'\n(?:>\s*)?#{1,6}\s+', content[start_pos:])
    if next_heading:
        stat_block_content = content[start_pos:start_pos + next_heading.start()]
    else:
        stat_block_content = content[start_pos:]
    
    # Extract the creature name (bold text after the heading, may have blockquote)
    creature_match = re.search(r'>?\s*\*\*(.+?)\*\*\s*\n', stat_block_content)
    creature_name = creature_match.group(1).strip() if creature_match else stat_block_name
    
    # Find the main stat table - it comes after the creature name and before traits
    # Look for consecutive table lines (with optional > prefix), stop at empty line or trait
    table_lines = []
    lines = stat_block_content.split('\n')
    in_table = False
    for line in lines:
        # Skip the creature name line
        if creature_name in line and '**' in line:
            continue
        # Check if this is a table line
        if '|' in line and not line.strip().startswith('> >'):
            table_lines.append(line)
            in_table = True
        elif in_table and line.strip() in ['', '>']:
            # End of table
            break
    
    stat_table = '\n'.join(table_lines).strip() if table_lines else None
    # Clean blockquote markers from table
    if stat_table:
        stat_table = re.sub(r'^>\s*', '', stat_table, flags=re.MULTILINE)
    
    # Extract traits/abilities (nested blockquoted sections: > > **Name**)
    # These appear after the main stat table
    traits = []
    # Split content to find where traits start (after the main stat table and an empty line)
    if stat_table:
        # Find where the stat table ends in the content
        table_end = stat_block_content.find(stat_table) + len(stat_table)
        traits_section = stat_block_content[table_end:]
    else:
        traits_section = stat_block_content
    
    # Split traits section by trait headings (> > **Name**)
    trait_splits = re.split(r'\n>\s*>\s*\*\*([^*]+)\*\*\s*\n', traits_section)
    
    # Process pairs of (name, content)
    for i in range(1, len(trait_splits), 2):
        if i + 1 <= len(trait_splits):
            trait_name = trait_splits[i].strip()
            trait_content = trait_splits[i + 1] if i + 1 < len(trait_splits) else ''
            
            # Clean up the trait content (remove blockquote markers)
            trait_content = re.sub(r'^>\s*>?\s*', '', trait_content, flags=re.MULTILINE).strip()
            
            # Check if this trait contains a table (it's an ability)
            if '|' in trait_content:
                traits.append({
                    'name': trait_name,
                    'type': 'ability',
                    'content': trait_content
                })
            else:
                traits.append({
                    'name': trait_name,
                    'type': 'trait',
                    'description': trait_content
                })
    
    # Parse stat table into structured fields
    stats = parse_stat_table_fields(stat_table) if stat_table else None
    
    return {
        'name': creature_name,
        'full_content': stat_block_content.strip(),
        'stat_table': stat_table,
        'stats': stats,
        'traits': traits if traits else None
    }


def parse_stat_table_fields(table: str) -> Optional[Dict[str, Any]]:
    """Parse stat table into structured fields."""
    lines = table.strip().split('\n')
    if len(lines) < 5:  # Need at least header + separator + 3 data rows
        return {}
    
    # Helper to extract value from cell (gets bold text if present, strips HTML)
    def extract_value(cell: str) -> Optional[str]:
        cell = cell.strip()
        # Extract bold text if present: **value**<br/> Label
        bold_match = re.search(r'\*\*([^*]+)\*\*', cell)
        if bold_match:
            value = bold_match.group(1).strip()
        else:
            value = re.sub(r'<br/>.*', '', cell).strip()
        return value if value and value != '-' else None
    
    # Split each row into cells
    def split_row(line: str) -> list:
        # Remove leading/trailing pipes and split
        cells = [c.strip() for c in line.strip('|').split('|')]
        return cells
    
    # Parse rows (skip separator row at index 1)
    row1 = split_row(lines[0]) if len(lines) > 0 else []
    row2 = split_row(lines[2]) if len(lines) > 2 else []  # Skip separator at index 1
    row3 = split_row(lines[3]) if len(lines) > 3 else []
    row4 = split_row(lines[4]) if len(lines) > 4 else []
    
    stats = {}
    
    # Row 1: Type/Ancestry | - | Level | Role | EV
    if len(row1) >= 5:
        ancestry = extract_value(row1[0])
        if ancestry:
            stats['ancestry'] = ancestry
        level_val = extract_value(row1[2])
        if level_val:
            # Extract numeric level if present (e.g., "Level 8" -> 8)
            level_match = re.search(r'Level\s+(\d+)', level_val)
            if level_match:
                stats['level'] = int(level_match.group(1))
            else:
                stats['level'] = level_val  # Keep as string for "Level -" etc.
        role = extract_value(row1[3])
        if role:
            stats['role'] = role
        ev = extract_value(row1[4])
        if ev and ev.startswith('EV'):
            ev_match = re.search(r'EV\s+(.+)', ev)
            stats['ev'] = ev_match.group(1).strip() if ev_match else ev
    
    # Row 2: Size | Speed | Stamina | Stability | Free Strike
    if len(row2) >= 5:
        size = extract_value(row2[0])
        if size:
            stats['size'] = size
        speed = extract_value(row2[1])
        if speed:
            # Try to parse as int
            try:
                stats['speed'] = int(speed)
            except (ValueError, TypeError):
                stats['speed'] = speed
        stamina = extract_value(row2[2])
        if stamina:
            # Try to parse as int or keep formula like "2x your level"
            try:
                stats['stamina'] = int(stamina)
            except (ValueError, TypeError):
                stats['stamina'] = stamina
        stability = extract_value(row2[3])
        if stability:
            try:
                stats['stability'] = int(stability)
            except (ValueError, TypeError):
                stats['stability'] = stability
        free_strike = extract_value(row2[4])
        if free_strike:
            try:
                stats['free_strike'] = int(free_strike)
            except (ValueError, TypeError):
                stats['free_strike'] = free_strike
    
    # Row 3: Immunities | Movement | (blank) | With Captain | Weaknesses
    if len(row3) >= 5:
        immunities = extract_value(row3[0])
        if immunities:
            stats['immunities'] = immunities
        movement = extract_value(row3[1])
        if movement:
            stats['movement'] = movement
        with_captain = extract_value(row3[3])
        if with_captain:
            stats['with_captain'] = with_captain
        weaknesses = extract_value(row3[4])
        if weaknesses:
            stats['weaknesses'] = weaknesses
    
    # Row 4: Might | Agility | Reason | Intuition | Presence
    if len(row4) >= 5:
        characteristics = {}
        might = extract_value(row4[0])
        if might:
            try:
                characteristics['might'] = int(might)
            except (ValueError, TypeError):
                characteristics['might'] = might
        agility = extract_value(row4[1])
        if agility:
            try:
                characteristics['agility'] = int(agility)
            except (ValueError, TypeError):
                characteristics['agility'] = agility
        reason = extract_value(row4[2])
        if reason:
            try:
                characteristics['reason'] = int(reason)
            except (ValueError, TypeError):
                characteristics['reason'] = reason
        intuition = extract_value(row4[3])
        if intuition:
            try:
                characteristics['intuition'] = int(intuition)
            except (ValueError, TypeError):
                characteristics['intuition'] = intuition
        presence = extract_value(row4[4])
        if presence:
            try:
                characteristics['presence'] = int(presence)
            except (ValueError, TypeError):
                characteristics['presence'] = presence
        
        if characteristics:
            stats['characteristics'] = characteristics
    
    return stats

def extract_perk_group_from_type(type_value):
    """Extract the perk group name from the type field."""
    if not type_value or '/' not in type_value:
        return None
    # type format is "perk/groupname", extract the groupname
    return type_value.split('/', 1)[1]

def parse_perk_file(filepath, subdirectory):
    """Parse a single perk markdown file."""
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
    
    # Parse stat block if present (before removing HTML comments)
    stat_block = parse_stat_block(main_content)
    
    # Remove content after HTML comments (<!-- -->) which contain supplementary text
    # that is not part of the actual perk
    if '<!-- -->' in main_content:
        main_content = main_content.split('<!-- -->')[0].strip()
    
    # Strip markdown links from content
    main_content = strip_markdown_links(main_content)
    
    # Extract perk group from type field
    perk_group = extract_perk_group_from_type(frontmatter.get('type'))
    
    # Build the perk object
    perk = {
        'item_id': frontmatter.get('item_id'),
        'item_name': frontmatter.get('item_name'),
        'item_index': frontmatter.get('item_index'),
        'source': frontmatter.get('source'),
        'type': frontmatter.get('type'),
        'perk_group': perk_group,
        'content': main_content
    }
    
    # Add stat block if present
    if stat_block:
        perk['stat_block'] = stat_block
    
    return perk

def main():
    # Paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    perks_dir = os.path.join(project_root, 'Rules', 'Perks')
    output_file = os.path.join(project_root, 'data', 'perks.json')
    
    print(f"Parsing perks from {perks_dir}...")
    
    # Get all subdirectories (perk categories)
    subdirs = [d for d in os.listdir(perks_dir) 
               if os.path.isdir(os.path.join(perks_dir, d)) and not d.startswith('_')]
    
    perks = []
    for subdir in sorted(subdirs):
        subdir_path = os.path.join(perks_dir, subdir)
        print(f"\nProcessing {subdir}...")
        
        # Get all markdown files in this subdirectory
        perk_files = [f for f in os.listdir(subdir_path) 
                      if f.endswith('.md')]
        
        for filename in sorted(perk_files):
            filepath = os.path.join(subdir_path, filename)
            print(f"  Parsing {filename}...")
            perk = parse_perk_file(filepath, subdir)
            if perk:
                perks.append(perk)
    
    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    # Write to JSON file
    print(f"\nWriting {len(perks)} perks to {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(perks, f, indent=2, ensure_ascii=False)
    
    print(f"Done! Perks saved to {output_file}")

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Parse Draw Steel feature markdown files into structured JSON.

This script extracts class features from Rules/Features/{Class}/{Level} Features/*.md
and generates a JSON file with structured feature data.
"""

import json
import os
import re
try:
    import yaml
except Exception:
    yaml = None
from pathlib import Path
from typing import Dict, List, Any
try:
    from scripts.parse_helpers import parse_damage_clause, parse_frontmatter, parse_stat_block, strip_markdown_links
except Exception:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(__file__))
    from parse_helpers import parse_damage_clause, parse_frontmatter, parse_stat_block, strip_markdown_links



def parse_stat_table_fields(table: str) -> Dict[str, Any]:
    """Parse stat table into structured fields."""
    lines = table.strip().split('\n')
    if len(lines) < 5:  # Need at least header + separator + 3 data rows
        return {}
    
    # Helper to extract value from cell (gets bold text if present, strips HTML)
    def extract_value(cell: str) -> str:
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


def parse_ability_effects(content: str, has_power_roll: bool) -> Dict[str, Any]:
    """Parse Effect sections from ability content in features.
    
    Returns a dict with keys for different effect types:
    - 'trigger': Trigger condition for triggered abilities
    - 'before': Effect before power roll
    - 'effect': Main effect (for non-power-roll abilities)
    - 'after': Effect after power roll
    - 'mark_benefit': Mark benefit effect
    """
    effects = {}
    
    # Parse Trigger (for triggered abilities)
    trigger_match = re.search(r'\*\*Trigger:\*\*\s*(.+?)(?=\n\n\*\*|\n\*\*|\Z)', content, re.DOTALL)
    if trigger_match:
        effects['trigger'] = trigger_match.group(1).strip()
    
    if has_power_roll:
        # Look for Effect BEFORE power roll
        before_match = re.search(r'(?:\*\*🎯[^*]+\*\*|\*\*Trigger:\*\*[^\n]+).*?\n\n\*\*Effect:\*\*\s*(.+?)(?=\n\n\*\*Power Roll)', content, re.DOTALL)
        if before_match:
            effects['before'] = before_match.group(1).strip()
        
        # Look for Effect AFTER power roll
        after_match = re.search(r'\*\*Power Roll.+?\n(?:- \*\*[^*]+\*\*[^*]*\n)+.*?\n\n\*\*Effect:\*\*\s*(.+?)(?=\n\n\*\*Mark Benefit|\n\n\*\*Persistent|\n\n\*\*Spend|\Z)', content, re.DOTALL)
        if after_match:
            effects['after'] = after_match.group(1).strip()
        
        # If we have both before and after effects, keep them as separate keys
        # If we only have one effect, rename it to 'effect' for consistency
        if 'before' in effects and 'after' in effects:
            # Keep both as 'before' and 'after'
            pass
        elif 'before' in effects:
            # Only before effect - rename to 'effect'
            effects['effect'] = effects.pop('before')
        elif 'after' in effects:
            # Only after effect - rename to 'effect'
            effects['effect'] = effects.pop('after')
    else:
        # For abilities without power rolls - match until next heading or end, including lists and multiple paragraphs
        effect_match = re.search(r'\*\*Effect:\*\*\s*(.+?)(?=\n>\s*#{5,6}|\Z)', content, re.DOTALL)
        if effect_match:
            effects['effect'] = effect_match.group(1).strip()
    
    # Parse Mark Benefit (special effect type for tactician marks)
    mark_benefit_match = re.search(r'\*\*Mark Benefit:\*\*\s*(.+?)(?=\n\n\*\*Persistent|\n\n|$)', content, re.DOTALL)
    if mark_benefit_match:
        effects['mark_benefit'] = mark_benefit_match.group(1).strip()

    # Parse Strained section (some embedded abilities include a 'Strained' subsection)
    strained_match = re.search(r'\*\*Strained:\*\*\s*(.+?)(?=\n\n\*\*|\n\*\*|\Z)', content, re.DOTALL)
    if strained_match:
        effects['strained'] = strained_match.group(1).strip()

    return effects if effects else None


def parse_ability_power_roll(content: str) -> Dict[str, Any] | None:
    """Parse power roll from embedded ability content."""
    power_roll_match = re.search(r'\*\*Power Roll \+ ([^:]+):\*\*', content)
    if not power_roll_match:
        return None
    
    characteristic = power_roll_match.group(1).strip()
    
    # Parse tier results
    tiers = []
    tier_pattern = r'-\s*\*\*([^:]+):\*\*\s*(.+?)(?=\n-\s*\*\*|$)'
    tier_matches = re.finditer(tier_pattern, content, re.DOTALL)
    
    for match in tier_matches:
        range_text = match.group(1).strip()
        result_text = match.group(2).strip()
        
        # Determine tier
        if '≤11' in range_text or '11-' in range_text:
            tier = 'weak'
        elif '12-16' in range_text or '12–16' in range_text:
            tier = 'average'
        elif '17+' in range_text or '17–' in range_text:
            tier = 'strong'
        else:
            tier = 'unknown'
        
        # Parse damage and effects
        damage = None
        effects = []
        
        parts = result_text.split(';')
        for part in parts:
            part = part.strip()
            if 'damage' in part.lower():
                parsed = parse_damage_clause(part)
                if parsed:
                    damage = {'formula': parsed.get('formula'), 'type': parsed.get('type')}
                    if 'characteristics' in parsed:
                        damage['characteristics'] = parsed['characteristics']
                    # Fold single-letter type into formula if present (legacy behavior)
                    if damage.get('type') and len(damage['type']) == 1 and damage['type'].lower() in ['m', 'a', 'r', 'i', 'p']:
                        damage['formula'] = (damage['formula'] + ' ' + damage['type'].upper()).strip()
                        damage['type'] = None
                else:
                    effects.append(part)
                    continue
            elif part:
                effects.append(part)
        
        tiers.append({
            'tier': tier,
            'range': range_text,
            'damage': damage,
            'effects': effects
        })
    
    return {
        'characteristic': characteristic,
        'tiers': tiers
    } if tiers else None


def parse_embedded_ability(ability_text: str, ability_name: str) -> Dict[str, Any]:
    """Parse an embedded ability definition from markdown."""
    # Clean up ability text - remove blockquote markers from each line
    ability_text = re.sub(r'^>\s*', '', ability_text, flags=re.MULTILINE).strip()
    
    ability = {
        "name": ability_name,
        "flavor_text": None,
        "action_type": None,
        "keywords": [],
        "distance": None,
        "target": None,
        "cost_options": []
    }
    
    # Extract flavor text
    flavor_match = re.search(r'\*([^*]+)\*', ability_text)
    if flavor_match:
        ability["flavor_text"] = flavor_match.group(1).strip()
    
    # Parse power roll
    power_roll = parse_ability_power_roll(ability_text)
    if power_roll:
        ability["power_roll"] = power_roll
    
    # Parse effects
    effects = parse_ability_effects(ability_text, power_roll is not None)
    if effects:
        ability["effects"] = effects
    
    # Parse persistent
    persistent_match = re.search(r'\*\*Persistent (\d+):\*\*\s*(.+?)(?=\n\n|\Z)', ability_text, re.DOTALL)
    if persistent_match:
        ability["persistent"] = {
            'turns': int(persistent_match.group(1)),
            'description': persistent_match.group(2).strip()
        }
    
    # Parse cost options (Spend X Resource:)
    spend_pattern = r'\*\*Spend (\d+\+?) ([^:]+):\*\*\s*(.+?)(?=\n\n\*\*Spend|\Z)'
    for match in re.finditer(spend_pattern, ability_text, re.DOTALL):
        ability["cost_options"].append({
            "amount": match.group(1),
            "resource": match.group(2),
            "effect": match.group(3).strip()
        })
    
    # Parse table for action type, keywords, distance, target (robust for 2-col tables)
    # Robust table parsing: find all tables by line-by-line scanning
    lines = ability_text.split('\n')
    tables = []
    current_table = []
    
    for line in lines:
        line = line.strip()
        if line.startswith('|') and line.endswith('|'):
            current_table.append(line)
        else:
            if len(current_table) >= 3:  # At least header, separator, one data row
                tables.append(current_table)
            current_table = []
    
    # Check the last table if it wasn't added
    if len(current_table) >= 3:
        tables.append(current_table)
    
    # Process the first table with at least 3 rows
    for table in tables:
        if len(table) >= 3:
            # Parse header row (index 0) and data row (index 2)
            header_row = table[0]
            data_row = table[2]
            
            header_cols = [c.strip().replace('**', '') for c in header_row.split('|')[1:-1]]
            data_cols = [c.strip().replace('**', '').replace('📏', '').replace('🎯', '') for c in data_row.split('|')[1:-1]]
            
            if len(header_cols) == len(data_cols) and len(header_cols) >= 2:
                # For standard 2-column ability tables:
                # Column 0: keywords (from header), distance (from data)
                # Column 1: action_type (from header), target (from data)
                if len(header_cols) == 2:
                    # Column 0: Keywords and distance
                    header_0 = header_cols[0]
                    data_0 = data_cols[0]
                    if header_0:
                        # Keywords from header, split by comma
                        keywords = [k.strip() for k in header_0.split(',') if k.strip()]
                        if keywords:
                            ability['keywords'] = keywords
                    if data_0:
                        # Distance from data
                        ability['distance'] = data_0
                    
                    # Column 1: Action type and target
                    header_1 = header_cols[1]
                    data_1 = data_cols[1]
                    if header_1:
                        # Action type from header
                        ability['action_type'] = header_1
                    if data_1:
                        # Target from data
                        ability['target'] = data_1
                else:
                    # Fallback for other table formats - use the old logic
                    for i, header in enumerate(header_cols):
                        header_lower = header.lower()
                        data_value = data_cols[i] if i < len(data_cols) else None
                        
                        if not data_value:
                            continue
                            
                        # Check if header indicates keywords
                        if any(keyword in header_lower for keyword in ['area', 'magic', 'psionic', 'ranged', 'melee', 'strike', 'telepathy', 'force', 'fire', 'cold', 'lightning', 'poison', 'necrotic', 'radiant', 'weapon', 'spell', 'divine', 'martial']):
                            # This column contains keywords
                            if 'keywords' not in ability or not ability['keywords']:
                                ability['keywords'] = []
                            ability['keywords'].extend([k.strip() for k in data_value.split(',') if k.strip()])
                        
                        # Check if header indicates distance
                        elif 'distance' in header_lower or 'ranged' in header_lower or 'melee' in header_lower or 'reach' in header_lower:
                            ability['distance'] = data_value
                        
                        # Check if header indicates action type
                        elif any(action in header_lower for action in ['maneuver', 'main action', 'free action', 'reaction', 'bonus action', 'action']):
                            ability['action_type'] = data_value
                        
                        # Check if header indicates target
                        elif 'target' in header_lower:
                            ability['target'] = data_value
                
                break  # Only process the first valid table
    
    # Component order - determine the actual order from the ability text content
    components = []
    
    # Find the positions of different section types in the ability_text
    section_positions = {}
    
    # Look for section headings and their positions
    sections = [
        ('trigger', r'\*\*Trigger:\*\*'),
        ('effect', r'\*\*Effect:\*\*'),
        ('power_roll', r'\*\*Power Roll'),
        ('mark_benefit', r'\*\*Mark Benefit:\*\*'),
        ('strained', r'\*\*Strained:\*\*'),
        ('persistent', r'\*\*Persistent'),
        ('cost_options', r'\*\*Spend')
    ]
    
    for section_name, pattern in sections:
        match = re.search(pattern, ability_text)
        if match:
            section_positions[section_name] = match.start()
    
    # Sort sections by their position in the content
    sorted_sections = sorted(section_positions.items(), key=lambda x: x[1])
    
    # Parse effects to see what keys will be created
    parsed_effects = parse_ability_effects(ability_text, power_roll is not None)
    
    components = []
    added_components = set()
    
    for section_name, _ in sorted_sections:
        if section_name == 'trigger':
            # Include trigger if it's in the parsed effects
            if parsed_effects and 'trigger' in parsed_effects and 'trigger' not in added_components:
                components.append('trigger')
                added_components.add('trigger')
        elif section_name == 'effect':
            # Add the appropriate effect component name
            if parsed_effects:
                if 'before' in parsed_effects and 'after' in parsed_effects:
                    # Both before and after - this shouldn't happen in one section, but handle it
                    if 'before' not in added_components:
                        components.append('before')
                        added_components.add('before')
                    if 'after' not in added_components:
                        components.append('after')
                        added_components.add('after')
                elif 'before' in parsed_effects and 'before' not in added_components:
                    components.append('before')
                    added_components.add('before')
                elif 'after' in parsed_effects and 'after' not in added_components:
                    components.append('after')
                    added_components.add('after')
                elif 'effect' in parsed_effects and 'effect' not in added_components:
                    components.append('effect')
                    added_components.add('effect')
        elif section_name == 'power_roll' and 'power_roll' not in added_components:
            components.append('power_roll')
            added_components.add('power_roll')
        elif section_name == 'mark_benefit' and 'mark_benefit' not in added_components:
            components.append('mark_benefit')
            added_components.add('mark_benefit')
        elif section_name == 'strained' and 'strained' not in added_components:
            # Only add strained if parsed_effects contains it
            if parsed_effects and 'strained' in parsed_effects:
                components.append('strained')
                added_components.add('strained')
        elif section_name == 'persistent' and 'persistent' not in added_components:
            components.append('persistent')
            added_components.add('persistent')
        elif section_name == 'cost_options' and 'cost_options' not in added_components:
            components.append('cost_options')
            added_components.add('cost_options')
    
    if components:
        ability['component_order'] = components
    
    # Clean up None/empty values
    return {k: v for k, v in ability.items() if v is not None and v != [] and v != ""}


def extract_abilities_from_content(content: str) -> List[Dict[str, Any]]:
    """Extract all embedded ability definitions from feature content."""
    abilities = []
    
    # Match ability blocks (markdown blockquotes with headers)
    # Pattern: > ###### Ability Name
    ability_pattern = r'>\s*#{5,6}\s+([^\n]+)\n(.*?)(?=\n>\s*#{5,6}|\Z)'
    matches = re.finditer(ability_pattern, content, re.DOTALL)
    
    for match in matches:
        ability_name = match.group(1).strip()
        ability_text = match.group(2).strip()
        
        if ability_text:
            ability = parse_embedded_ability(ability_text, ability_name)
            abilities.append(ability)
    
    return abilities


def clean_content(content: str) -> str:
    """Clean feature content, removing ability blocks and tables."""
    # Remove ability blockquotes
    content = re.sub(r'>\s*#{5,6}\s+[^\n]+\n.*?(?=\n#{1,4}[^#]|\Z)', '', content, flags=re.DOTALL)
    
    # Remove tables (everything from table heading to end of content or next non-table heading)
    content = re.sub(r'#{4,6}\s+[^\n]*Table.*?(?=\n#{1,3}[^#]|\Z)', '', content, flags=re.DOTALL | re.IGNORECASE)
    
    # Remove HTML comments
    content = re.sub(r'<!--.*?-->', '', content, flags=re.DOTALL)
    
    # Remove markdown links [text](url) -> text
    content = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', content)
    
    # Clean up extra whitespace
    content = re.sub(r'\n{3,}', '\n\n', content)
    
    return content.strip()


def slugify(text: str) -> str:
    """Convert text to a slug format."""
    # Convert to lowercase and replace spaces/special chars with hyphens
    slug = text.lower()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[-\s]+', '-', slug)
    return slug.strip('-')


def normalize_stat_name(stat_name: str) -> str:
    """Normalize stat names to standard format."""
    import re
    stat_name = stat_name.lower().strip().rstrip('.')
    if stat_name in ['stamina', 'stam']:
        return 'stamina'
    elif stat_name in ['stability', 'stab']:
        return 'stability'
    elif stat_name in ['speed']:
        return 'speed'
    elif stat_name in ['damage', 'rolled damage']:
        return 'damage'
    elif stat_name in ['shift', 'shift distance']:
        return 'shift'
    else:
        return ''  # Not a recognized stat


def extract_grants(body: str, feature_name: str) -> Dict[str, Any]:
    """Extract what the feature grants (skills, perks, kits, abilities, bonuses, etc.)."""
    grants = {}
    
    # Normalize text for easier parsing
    text = body.lower()
    
    # Skills granted - must be explicit skill grant (not bonuses/edges)
    # Pattern must be "you gain/have [the] SKILL_NAME skill." with nothing between gain and the/skill
    skill_patterns = [
        (r'you gain (?:one|two|three|(\d+)) skills? of your choice', 'choice'),
        (r'you gain the ([A-Z][a-z]+(?: [A-Z][a-z]+)*) skill\.', 'specific'),
        (r'you have the ([A-Z][a-z]+(?: [A-Z][a-z]+)*) skill\.', 'specific')
    ]
    
    for pattern, pattern_type in skill_patterns:
        match = re.search(pattern, body, re.IGNORECASE | re.MULTILINE)
        if match:
            if 'skill' not in grants:
                grants['skill'] = {}
            
            if pattern_type == 'choice':
                # Count how many skills
                count_match = re.search(r'(one|two|three|\d+) skills?', text)
                if count_match:
                    count_word = count_match.group(1)
                    count_map = {'one': 1, 'two': 2, 'three': 3}
                    count = count_map.get(count_word, int(count_word) if count_word.isdigit() else 1)
                    grants['skill']['type'] = 'choice'
                    grants['skill']['count'] = count
                else:
                    grants['skill']['type'] = 'choice'
                    grants['skill']['count'] = 1
            else:  # specific
                # Specific skill named
                skill_name = match.group(1) if match.lastindex and match.lastindex >= 1 else None
                if skill_name and len(skill_name) > 2:  # Must be at least 3 chars to avoid false matches
                    grants['skill']['type'] = 'specific'
                    grants['skill']['name'] = skill_name
            break
    
    # Perks granted
    perk_patterns = [
        r'you gain (?:one|two|three|(\d+)) perks? of your choice',
        r'you gain a? (\w+) perk'
    ]
    
    for pattern in perk_patterns:
        match = re.search(pattern, body, re.IGNORECASE)
        if match:
            if 'perk' not in grants:
                grants['perk'] = {}
            
            if 'of your choice' in text or 'perk of your choice' in text:
                count_match = re.search(r'(one|two|three|\d+) perks?', text)
                if count_match:
                    count_word = count_match.group(1)
                    count_map = {'one': 1, 'two': 2, 'three': 3}
                    count = count_map.get(count_word, int(count_word) if count_word.isdigit() else 1)
                    grants['perk']['type'] = 'choice'
                    grants['perk']['count'] = count
                else:
                    grants['perk']['type'] = 'choice'
                    grants['perk']['count'] = 1
                
                # Check for perk type restrictions
                if 'crafting' in text or 'lore' in text or 'supernatural' in text:
                    restrictions = []
                    if 'crafting' in text:
                        restrictions.append('crafting')
                    if 'lore' in text:
                        restrictions.append('lore')
                    if 'supernatural' in text:
                        restrictions.append('supernatural')
                    grants['perk']['restrictions'] = restrictions
            break
    
    # Kits granted
    kit_patterns = [
        r'you can use and gain the benefits of (?:a |one |two |three |(\d+ ))?kits?',
        r'you gain (?:a |the )?([A-Z][a-z]+(?: [A-Z][a-z]+)*) kit'
    ]
    
    for pattern in kit_patterns:
        match = re.search(pattern, body, re.IGNORECASE)
        if match:
            if 'kit' not in grants:
                grants['kit'] = {}
            
            # Count kits
            count = 1
            if 'two kits' in text:
                count = 2
            elif 'three kits' in text:
                count = 3
            
            grants['kit']['count'] = count
            
            # Check if specific kit mentioned in Quick Build
            quick_build_match = re.search(r'\(\*Quick Build:\*\s*([^)]+)\)', body)
            if quick_build_match:
                grants['kit']['quick_build'] = quick_build_match.group(1).strip()
            break
    
    # Characteristic increases
    if 'characteristic increase' in feature_name.lower():
        char_patterns = [
            (r'each of your characteristic scores increases by (\d+)', 'all_by_amount'),
            (r'your (\w+) and (\w+) scores each increase to (\d+)', 'specific_to_value'),
            (r'your (\w+) score increases to (\d+)', 'single_to_value'),
            (r'characteristic scores increase by (\d+)', 'all_by_amount')
        ]
        
        for pattern, pattern_type in char_patterns:
            match = re.search(pattern, body, re.IGNORECASE)
            if match:
                if 'characteristic_increase' not in grants:
                    grants['characteristic_increase'] = {}
                
                if pattern_type == 'all_by_amount':
                    grants['characteristic_increase']['type'] = 'all'
                    grants['characteristic_increase']['amount'] = int(match.group(1))
                    if 'maximum of' in text:
                        max_match = re.search(r'maximum of (\d+)', body)
                        if max_match:
                            grants['characteristic_increase']['maximum'] = int(max_match.group(1))
                elif pattern_type == 'specific_to_value':
                    grants['characteristic_increase']['type'] = 'specific'
                    grants['characteristic_increase']['characteristics'] = [match.group(1), match.group(2)]
                    grants['characteristic_increase']['to_value'] = int(match.group(3))
                elif pattern_type == 'single_to_value':
                    grants['characteristic_increase']['type'] = 'specific'
                    grants['characteristic_increase']['characteristics'] = [match.group(1)]
                    grants['characteristic_increase']['to_value'] = int(match.group(2))
                break
    
    # Stat bonuses (for features like "Enchantment of" that grant bonuses to basic stats)
    if 'enchantment of' in feature_name.lower():
        stat_bonus_patterns = [
            r'you gain a \+(\d+) bonus to (\w+)',
            r'you have a \+(\d+) bonus to (\w+)',
            r'you gain \+(\d+) (\w+)'
        ]
        
        stat_bonuses = {}
        for pattern in stat_bonus_patterns:
            matches = re.findall(pattern, body, re.IGNORECASE)
            for match in matches:
                if len(match) == 2:
                    bonus_amount = int(match[0])
                    stat_name = match[1].lower()
                    
                    # Normalize stat names
                    if stat_name == 'stamina':
                        stat_name = 'stamina'
                    elif stat_name == 'stability':
                        stat_name = 'stability'
                    elif stat_name == 'speed':
                        stat_name = 'speed'
                    else:
                        continue  # Skip if not a recognized stat
                    
                    if stat_name not in stat_bonuses:
                        stat_bonuses[stat_name] = {'base': bonus_amount}
                    else:
                        # Take the highest bonus if multiple mentions
                        stat_bonuses[stat_name]['base'] = max(stat_bonuses[stat_name]['base'], bonus_amount)
        
        # Check for level scaling (e.g., "and that bonus increases by 3 at 4th, 7th, and 10th levels")
        scaling_pattern = r'(?:that|this) bonus increases by (\d+) at (\d+)(?:th|st|nd|rd),? (\d+)(?:th|st|nd|rd),? and (\d+)(?:th|st|nd|rd) levels'
        scaling_match = re.search(scaling_pattern, body, re.IGNORECASE)
        if scaling_match:
            increase_amount = int(scaling_match.group(1))
            level_1 = int(scaling_match.group(2))
            level_2 = int(scaling_match.group(3))
            level_3 = int(scaling_match.group(4))
            
            # Apply scaling to all stats that have bonuses
            # For now, assume scaling applies to the first stat mentioned (usually stamina)
            for stat_name in stat_bonuses:
                if 'scaling' not in stat_bonuses[stat_name]:
                    stat_bonuses[stat_name]['scaling'] = {
                        'amount': increase_amount,
                        'levels': [level_1, level_2, level_3]
                    }
                break  # Only apply to the first stat that doesn't already have scaling
        
        if stat_bonuses:
            grants['stat_bonuses'] = stat_bonuses
    
    # General stat bonuses (for features like augmentations)
    stat_bonus_patterns = [
        r'you gain a \+(\d+) bonus to (\w+)',
        r'you have a \+(\d+) bonus to (\w+)',
        r'you gain \+(\d+) (\w+)',
        r'you gain a \+(\d+) bonus to (\w+) and (\w+)',
        r'you gain a \+(\d+) bonus to (\w+), and this bonus increases by (\d+) at (\d+)(?:th|st|nd|rd),? (\d+)(?:th|st|nd|rd),? and (\d+)(?:th|st|nd|rd) levels',
        r'abilities gain a \+(\d+) bonus to (.+?)'
    ]
    
    general_stat_bonuses = {}
    for pattern in stat_bonus_patterns:
        matches = re.findall(pattern, body, re.IGNORECASE)
        for match in matches:
            if len(match) >= 2:
                if len(match) == 2:
                    # Patterns like 'you gain a +X bonus to Y' -> (bonus, stat)
                    bonus_amount = int(match[0])
                    stat_name = match[1].lower()
                    stat_name = normalize_stat_name(stat_name)
                    if stat_name:
                        if stat_name not in general_stat_bonuses:
                            general_stat_bonuses[stat_name] = {'base': bonus_amount}
                        else:
                            general_stat_bonuses[stat_name]['base'] = max(general_stat_bonuses[stat_name]['base'], bonus_amount)
                elif len(match) == 3:
                    if 'abilities' in pattern:
                        # Patterns like 'X abilities gain a +Y bonus to Z' -> (type, bonus, stat)
                        bonus_amount = int(match[1])
                        stat_name = match[2].lower()
                        stat_name = normalize_stat_name(stat_name)
                        if stat_name:
                            if stat_name not in general_stat_bonuses:
                                general_stat_bonuses[stat_name] = {'base': bonus_amount}
                            else:
                                general_stat_bonuses[stat_name]['base'] = max(general_stat_bonuses[stat_name]['base'], bonus_amount)
                    else:
                        # Pattern 'you gain a +X bonus to Y and Z' -> (bonus, stat1, stat2)
                        bonus_amount = int(match[0])
                        stat_name1 = match[1].lower()
                        stat_name2 = match[2].lower()
                        stat_name1 = normalize_stat_name(stat_name1)
                        stat_name2 = normalize_stat_name(stat_name2)
                        if stat_name1:
                            if stat_name1 not in general_stat_bonuses:
                                general_stat_bonuses[stat_name1] = {'base': bonus_amount}
                            else:
                                general_stat_bonuses[stat_name1]['base'] = max(general_stat_bonuses[stat_name1]['base'], bonus_amount)
                        if stat_name2:
                            if stat_name2 not in general_stat_bonuses:
                                general_stat_bonuses[stat_name2] = {'base': bonus_amount}
                            else:
                                general_stat_bonuses[stat_name2]['base'] = max(general_stat_bonuses[stat_name2]['base'], bonus_amount)
                elif len(match) == 6:
                    # Scaling pattern -> (bonus, stat, increase, level1, level2, level3)
                    bonus_amount = int(match[0])
                    stat_name = match[1].lower()
                    stat_name = normalize_stat_name(stat_name)
                    increase_amount = int(match[2])
                    level_1 = int(match[3])
                    level_2 = int(match[4])
                    level_3 = int(match[5])
                    if stat_name:
                        if stat_name not in general_stat_bonuses:
                            general_stat_bonuses[stat_name] = {'base': bonus_amount, 'scaling': {'amount': increase_amount, 'levels': [level_1, level_2, level_3]}}
                        else:
                            general_stat_bonuses[stat_name]['base'] = max(general_stat_bonuses[stat_name]['base'], bonus_amount)
                            if 'scaling' not in general_stat_bonuses[stat_name]:
                                general_stat_bonuses[stat_name]['scaling'] = {'amount': increase_amount, 'levels': [level_1, level_2, level_3]}
    
    # Check for scaling separately if not captured
    scaling_pattern = r'(?:that|this) bonus increases by (\d+) at (\d+)(?:th|st|nd|rd),? (\d+)(?:th|st|nd|rd),? and (\d+)(?:th|st|nd|rd) levels'
    scaling_match = re.search(scaling_pattern, body, re.IGNORECASE)
    if scaling_match and general_stat_bonuses:
        increase_amount = int(scaling_match.group(1))
        level_1 = int(scaling_match.group(2))
        level_2 = int(scaling_match.group(3))
        level_3 = int(scaling_match.group(4))
        
        # Check if any stat already has scaling
        has_scaling = any('scaling' in bonuses for bonuses in general_stat_bonuses.values())
        if not has_scaling:
            # Apply scaling to all stats that have bonuses
            for stat_name in general_stat_bonuses:
                if 'scaling' not in general_stat_bonuses[stat_name]:
                    general_stat_bonuses[stat_name]['scaling'] = {
                        'amount': increase_amount,
                        'levels': [level_1, level_2, level_3]
                    }
    
    if general_stat_bonuses:
        grants['stat_bonuses'] = general_stat_bonuses
    
    return grants


def extract_subclass_options(body: str) -> List[Dict[str, Any]]:
    """Extract subclass options from features like Primordial Aspect."""
    options = []
    
    # Look for bullet points with bold aspect names
    # Pattern: - **Aspect Name:** description. You have the Skill skill.
    option_pattern = r'-\s*\*\*([^*]+)\*\*:\s*(.+?)\s*You have the ([A-Z][a-z]+(?: [A-Z][a-z]+)*) skill\.?'
    
    matches = re.findall(option_pattern, body, re.IGNORECASE | re.DOTALL)
    for match in matches:
        aspect_name = match[0].strip()
        description = match[1].strip()
        skill_name = match[2].strip()
        
        option = {
            'name': aspect_name,
            'description': description,
            'grants': {
                'skill': {
                    'type': 'specific',
                    'name': skill_name
                }
            }
        }
        options.append(option)
    
    # Parse table for additional features (for Shadow College)
    # Look for table with College and Feature columns
    table_pattern = r'\| College\s*\| Feature\s*\|[\s\S]*?\| (Black Ash|Caustic Alchemy|Harlequin Mask)\s*\| ([^\|]+)\s*\|'
    table_matches = re.findall(table_pattern, body, re.IGNORECASE | re.MULTILINE)
    
    college_features = {}
    for match in table_matches:
        college = match[0].strip()
        features_str = match[1].strip()
        features = [f.strip() for f in features_str.split(',')]
        college_features[college] = features
    
    # Add features to options
    for option in options:
        college_name = option['name']
        # Remove "College of " prefix
        short_name = re.sub(r'^College of (?:the )?', '', college_name, re.IGNORECASE).strip()
        if short_name in college_features:
            option['features'] = college_features[short_name]
    
    return options


def extract_tables(content: str) -> List[Dict[str, Any]]:
    """Extract tables from feature content and return as structured data."""
    tables = []
    
    # Pattern to find table headings (#### or ###### Table Name)
    table_heading_pattern = r'^#{4,6}\s+(.+?)\s*$'
    
    # Split content into sections by table headings
    sections = re.split(r'(#{4,6}\s+.+\s*$)', content, flags=re.MULTILINE)
    
    for i in range(1, len(sections), 2):  # Skip first section, process heading + content pairs
        heading = sections[i].strip()
        table_content = sections[i + 1] if i + 1 < len(sections) else ""
        
        # Extract table name from heading
        heading_match = re.match(r'#{4,6}\s+(.+)', heading)
        if not heading_match:
            continue
        table_name = heading_match.group(1).strip()
        
        # Find the table in the content (look for | separated rows)
        table_lines = []
        in_table = False
        
        for line in table_content.split('\n'):
            line = line.strip()
            if '|' in line and not line.startswith('>'):  # Table row, not blockquote
                table_lines.append(line)
                in_table = True
            elif in_table and line == "":  # Empty line ends table
                break
        
        if not table_lines or len(table_lines) < 2:  # Need at least header + separator
            continue
        
        # Parse table rows
        rows = []
        for line in table_lines:
            # Split by | and strip whitespace
            cells = [cell.strip() for cell in line.split('|')[1:-1]]  # Skip first and last empty cells
            if cells:
                rows.append(cells)
        
        if len(rows) < 2:  # Need header + at least one data row
            continue
        
        # First row is header
        headers = rows[0]
        
        # Skip separator row (usually index 1)
        data_rows = rows[2:] if len(rows) > 2 and all('-' in cell or cell == '' for cell in rows[1]) else rows[1:]
        
        # Convert to structured data
        table_data = []
        for row in data_rows:
            if len(row) == len(headers):
                row_dict = {}
                for j, cell in enumerate(row):
                    header = headers[j] if j < len(headers) else f"col_{j}"
                    row_dict[header] = cell
                table_data.append(row_dict)
        
        if table_data:
            tables.append({
                'name': table_name,
                'headers': headers,
                'data': table_data
            })
    
    return tables


def parse_elemental_specialization_table(rules_dir: Path) -> Dict[str, str]:
    """Parse the 1st-Level Elemental Specialization Features table from elementalist.md."""
    elementalist_file = rules_dir / 'Classes' / 'Elementalist.md'
    
    if not elementalist_file.exists():
        return {}
    
    with open(elementalist_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the 1st-Level Elemental Specialization Features Table
    table_pattern = r'###### 1st-Level Elemental Specialization Features Table\s*\n\s*\|[^\n]+\|[^\n]+\|\s*\n\s*\|[:\-\s|]+\|\s*\n((?:\s*\|[^\n]+\|[^\n]+\|\s*\n)+)'
    table_match = re.search(table_pattern, content, re.MULTILINE)
    
    if not table_match:
        return {}
    
    table_content = table_match.group(1)
    specialization_map = {}
    
    # Parse each row
    for line in table_content.strip().split('\n'):
        if '|' in line:
            cells = [cell.strip() for cell in line.split('|')[1:-1]]
            if len(cells) >= 2:
                specialization = cells[0].lower()
                feature_name = cells[1]
                
                # Convert feature name to id
                feature_id = slugify(feature_name)
                
                specialization_map[feature_id] = specialization.title()  # Capitalize first letter
    
    return specialization_map


def parse_class_level_tables(rules_dir: Path) -> Dict[str, str]:
    """Scan class markdown files for tables that map subclass/school/tradition -> feature.

    Returns a mapping of feature_slug -> subclass_short_name.
    """
    mapping: Dict[str, str] = {}

    classes_dir = rules_dir / 'Classes'
    if not classes_dir.exists():
        return mapping

    subclass_keywords = ['college', 'school', 'tradition', 'subclass', 'specialization', 'discipline', 'order']
    feature_keywords = ['feature', 'ability', 'ability name', 'feature name', 'features']

    for class_file in classes_dir.glob('*.md'):
        try:
            with open(class_file, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception:
            continue

        tables = extract_tables(content)
        for t in tables:
            # Quick check whether table name or headers mention subclass-like keywords
            table_name = (t.get('name') or '').lower()
            headers = t.get('headers') or []
            lower_headers = ' '.join(h.lower() for h in headers)

            if not (any(k in table_name for k in subclass_keywords) or any(k in lower_headers for k in subclass_keywords)):
                continue

            for row in t.get('data', []):
                # Determine keys
                subclass_key = None
                feature_key = None
                for k in row.keys():
                    lk = k.lower()
                    if any(sk in lk for sk in subclass_keywords) and not subclass_key:
                        subclass_key = k
                    if any(fk in lk for fk in feature_keywords) and not feature_key:
                        feature_key = k

                # fallback to positional
                keys = list(row.keys())
                if not subclass_key and len(keys) >= 1:
                    subclass_key = keys[0]
                if not feature_key and len(keys) >= 2:
                    feature_key = keys[1]

                if not subclass_key or not feature_key:
                    continue

                subclass_name = row.get(subclass_key, '').strip()
                features_str = row.get(feature_key, '').strip()
                if not features_str:
                    continue

                # features may be comma/semicolon separated
                feature_names = [f.strip() for f in re.split(r',|;|/|\\n', features_str) if f.strip()]

                # Normalize subclass short name
                short = re.sub(r'(?i)^college of (?:the )?', '', subclass_name).strip()

                for feat in feature_names:
                    slug = slugify(feat)
                    if slug:
                        mapping[slug] = short

    return mapping


def parse_class_level_option_tables(rules_dir: Path) -> Dict[str, List[Dict[str, Any]]]:
    """Parse class markdown files for tables that map subclass/school/tradition -> feature

    Returns a mapping keyed by the lowercase class name (e.g., 'talent') to a list of
    table dicts as returned by `extract_tables` filtered to only include likely
    subclass->feature tables.
    """
    result: Dict[str, List[Dict[str, Any]]] = {}

    classes_dir = rules_dir / 'Classes'
    if not classes_dir.exists():
        return result

    subclass_keywords = ['college', 'school', 'tradition', 'subclass', 'specialization', 'discipline', 'order']
    feature_keywords = ['feature', 'ability', 'ability name', 'feature name', 'features']

    for class_file in classes_dir.glob('*.md'):
        try:
            with open(class_file, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception:
            continue

        tables = extract_tables(content)
        filtered = []
        for t in tables:
            table_name = (t.get('name') or '').lower()
            headers = t.get('headers') or []
            lower_headers = [h.lower() for h in headers]

            # Only keep tables that visibly pair a subclass-like column (e.g., "Tradition", "College")
            # with a features/ability column. Exclude tables that mention subclass keywords only as
            # part of an "... Abilities" header (those are usually advancement/summary tables).
            has_subclass_header = any(any(sk in h and 'abilit' not in h for sk in subclass_keywords) for h in lower_headers)
            has_feature_header = any(any(fk in h for fk in feature_keywords) for h in lower_headers)

            if has_subclass_header and has_feature_header:
                filtered.append(t)

        if filtered:
            class_name = class_file.stem.lower()
            result[class_name] = filtered

    return result


def parse_feature_file(file_path: Path, elemental_specialization_map: Dict[str, str] = None) -> List[Dict[str, Any]]:
    """Parse a single feature markdown file. Returns a list of features (may be multiple if abilities are split)."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return []
    
    frontmatter, body = parse_frontmatter(content)
    
    if not frontmatter:
        print(f"No frontmatter in {file_path}")
        return []
    
    # Extract embedded abilities
    abilities = extract_abilities_from_content(body)
    
    # Extract stat block if present
    stat_block = parse_stat_block(body)
    
    # Extract what the feature grants
    grants = extract_grants(body, frontmatter.get('item_name', ''))
    
    # Extract subclass options if this is a subclass selection feature
    subclass_options = extract_subclass_options(body)
    
    # Extract tables from the content
    tables = extract_tables(body)

    # If no subclass options found, try to construct them from a table that pairs
    # a subclass-like column (college/school/tradition/discipline/specialization) with
    # a feature/ability column. This generalizes the earlier College/Feature logic.
    if not subclass_options and tables:
        subclass_keywords = ['college', 'school', 'tradition', 'subclass', 'specialization', 'discipline', 'order']
        feature_keywords = ['feature', 'ability', 'ability name', 'feature name', 'features']

        for t in tables:
            headers = t.get('headers', []) or []
            lower_headers = [h.lower() for h in headers]

            # Quick check: if the table name mentions a subclass concept, prefer it
            table_name = (t.get('name') or '').lower()
            likely_subclass_table = any(k in table_name for k in subclass_keywords) or any(k in ' '.join(lower_headers) for k in subclass_keywords)

            if not likely_subclass_table:
                # Skip tables that are unlikely to be subclass-feature tables
                continue

            constructed = []
            for row in t.get('data', []):
                college_key = None
                feature_key = None

                # Find the header keys by fuzzy contains matching
                for k in row.keys():
                    lk = k.lower()
                    if any(sk in lk for sk in subclass_keywords) and not college_key:
                        college_key = k
                    if any(fk in lk for fk in feature_keywords) and not feature_key:
                        feature_key = k

                # If we still don't have explicit keys, try positional fallback (first=class, second=feature)
                if not college_key or not feature_key:
                    keys = list(row.keys())
                    if len(keys) >= 2:
                        if not college_key:
                            college_key = keys[0]
                        if not feature_key:
                            feature_key = keys[1]

                if not college_key or not feature_key:
                    continue

                college_name = row.get(college_key, '').strip()
                features_str = row.get(feature_key, '').strip()

                # Features column may be a comma-separated list or a single feature
                features_list = [f.strip() for f in re.split(r',|;|/|\\n', features_str) if f.strip()]

                # Normalize option name to match other subclass option formats
                opt_name = college_name
                if opt_name and not re.search(r'(?i)college|school|tradition|specialization|discipline|subclass', opt_name):
                    opt_name = f"College of {opt_name}"

                option = {
                    'name': opt_name,
                    'features': features_list
                }
                constructed.append(option)

            if constructed:
                subclass_options = constructed
                break
    
    # Clean content (remove ability blocks)
    description = clean_content(body)
    
    # If there are multiple abilities, create separate feature objects for each
    if len(abilities) > 1:
        features = []
        for ability in abilities:
            # Create a new feature for each ability
            feature = dict(frontmatter)
            
            # Update identifiers based on ability name
            ability_slug = slugify(ability['name'])
            feature["item_id"] = ability_slug
            feature["item_name"] = ability['name']
            
            # Update type and scc/scdc if present
            if 'type' in feature:
                # Replace the last component with the new slug
                type_parts = feature['type'].rsplit(':', 1)
                if len(type_parts) == 2:
                    feature['type'] = f"{type_parts[0]}:{ability_slug}"
                else:
                    feature['type'] = feature['type'].rsplit('/', 1)[0] + '/' + ability_slug
            
            if 'scc' in feature and isinstance(feature['scc'], list):
                updated_scc = []
                for scc_item in feature['scc']:
                    parts = scc_item.rsplit(':', 1)
                    if len(parts) == 2:
                        updated_scc.append(f"{parts[0]}:{ability_slug}")
                    else:
                        updated_scc.append(scc_item)
                feature['scc'] = updated_scc
            
            # Set description to just the intro text (before abilities)
            feature["description"] = description
            
            # Add the single ability
            feature["abilities"] = [ability]
            
            # Add grants information
            if grants:
                feature["grants"] = grants
            
            # Add tables if present
            if tables:
                feature["tables"] = tables
            
            # Add subclass options if present
            if subclass_options:
                feature["subclass_options"] = subclass_options
            
            # Add stat block if present
            if stat_block:
                feature["stat_block"] = stat_block
            
            # Add subclass for elementalist features
            if elemental_specialization_map and feature.get('class') == 'elementalist':
                feature_id = feature.get('item_id')
                if feature_id in elemental_specialization_map:
                    feature['subclass'] = elemental_specialization_map[feature_id]
            
            features.append(feature)
        
        return features
    else:
        # Single ability or no abilities - return as-is
        feature = dict(frontmatter)
        feature["description"] = description
        
        if abilities:
            feature["abilities"] = abilities
        
        # Add grants information
        if grants:
            feature["grants"] = grants
        
        # Add tables if present
        if tables:
            feature["tables"] = tables
        
        # Add subclass options if present
        if subclass_options:
            feature["subclass_options"] = subclass_options
        
        # Add stat block if present
        if stat_block:
            feature["stat_block"] = stat_block
        
        # Add subclass for elementalist features
        if elemental_specialization_map and feature.get('class') == 'elementalist':
            feature_id = feature.get('item_id')
            if feature_id in elemental_specialization_map:
                feature['subclass'] = elemental_specialization_map[feature_id]
        
        return [feature]


def parse_all_features(rules_dir: Path) -> List[Dict[str, Any]]:
    """Parse all feature files from Rules/Features directory."""
    features_dir = rules_dir / 'Features'
    features = []
    
    # Get elemental specialization mapping for subclass assignment
    elemental_specialization_map = parse_elemental_specialization_table(rules_dir)
    # Also scan class-level markdown files for other subclass/feature tables
    class_table_map = parse_class_level_tables(rules_dir)
    # Also extract class-level option tables (e.g., Tradition/College tables) so
    # we can attach `subclass_options` to selector features like "Talent Tradition".
    class_table_options = parse_class_level_option_tables(rules_dir)

    # Merge maps (class_table_map keys are slugs)
    # We will keep elemental_specialization_map keyed by item_id (slug) and
    # class_table_map keyed by slug too — merge them by slug into a single map
    if elemental_specialization_map is None:
        elemental_specialization_map = {}
    # Convert elemental map keys to slugs if they aren't already (they should be slugs)
    merged_map = dict(elemental_specialization_map)
    for slug, subclass in class_table_map.items():
        # Do not overwrite existing mapping unless absent
        if slug not in merged_map:
            merged_map[slug] = subclass

    elemental_specialization_map = merged_map
    
    # Iterate through class directories
    for class_dir in sorted(features_dir.iterdir()):
        if not class_dir.is_dir():
            continue
        
        class_name = class_dir.name
        print(f"\nParsing {class_name} features...")
        
        # Iterate through level directories
        for level_dir in sorted(class_dir.iterdir()):
            if not level_dir.is_dir():
                continue
            
            level_name = level_dir.name
            
            # Skip Index.md files
            feature_files = [f for f in level_dir.glob('*.md') if f.name != 'Index.md']
            
            for feature_file in sorted(feature_files):
                parsed_features = parse_feature_file(feature_file, elemental_specialization_map)
                if parsed_features:
                    features.extend(parsed_features)
                    if len(parsed_features) > 1:
                        print(f"  ✓ {level_name}/{feature_file.name} ({len(parsed_features)} abilities)")
                    else:
                        print(f"  ✓ {level_name}/{feature_file.name}")
    
    # After parsing all features, attach subclass options found in class markdown
    # to the corresponding selector feature objects. For example, the Talent
    # class has a "1st-Level Tradition Features Table" in `Classes/Talent.md`;
    # attach those rows as `subclass_options` on the `Talent Tradition` feature.
    subclass_keywords = ['college', 'school', 'tradition', 'subclass', 'specialization', 'discipline', 'order']
    feature_keywords = ['feature', 'ability', 'features']

    for feature in features:
        cls = feature.get('class')
        if not cls:
            continue
        cls_lower = cls.lower()
        tables_for_class = class_table_options.get(cls_lower) or []
        if not tables_for_class:
            continue

        # Only attempt to attach options to likely selector features (e.g., "Talent Tradition")
        name_lower = (feature.get('item_name') or '').lower()
        if not any(k in name_lower for k in subclass_keywords):
            continue

        constructed_options = []
        for t in tables_for_class:
            headers = t.get('headers', []) or []
            for row in t.get('data', []):
                # determine subclass and feature columns
                subclass_key = None
                feature_key = None
                for k in row.keys():
                    lk = k.lower()
                    if any(sk in lk for sk in subclass_keywords) and not subclass_key:
                        subclass_key = k
                    if any(fk in lk for fk in feature_keywords) and not feature_key:
                        feature_key = k

                # positional fallback
                keys = list(row.keys())
                if not subclass_key and len(keys) >= 1:
                    subclass_key = keys[0]
                if not feature_key and len(keys) >= 2:
                    feature_key = keys[1]

                if not subclass_key or not feature_key:
                    continue

                subclass_name = row.get(subclass_key, '').strip()
                features_str = row.get(feature_key, '').strip()
                if not subclass_name or not features_str:
                    continue

                features_list = [f.strip() for f in re.split(r',|;|/|\\n', features_str) if f.strip()]

                option = {
                    'name': subclass_name,
                    'features': features_list
                }
                constructed_options.append(option)

        if constructed_options and not feature.get('subclass_options'):
            feature['subclass_options'] = constructed_options

    return features


def main():
    """Main function to parse features and generate JSON."""
    # Get the repository root (parent of scripts directory)
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    rules_dir = repo_root / 'Rules'
    output_dir = repo_root / 'data'
    
    # Ensure output directory exists
    output_dir.mkdir(exist_ok=True)
    
    print("Parsing Draw Steel features...")
    print(f"Rules directory: {rules_dir}")
    
    # Parse all features
    features = parse_all_features(rules_dir)
    
    # Build mapping from feature name -> subclass (college) using any parsed subclass_options
    # This lets us add `subclass` on the actual feature records (e.g., Black Ash Teleport -> "Black Ash").
    import re as _re
    name_to_subclass = {}
    for f in features:
        opts = f.get('subclass_options') or []
        for opt in opts:
            college_name = opt.get('name', '')
            # Normalize to short form (remove leading "College of " if present)
            short = _re.sub(r'(?i)^college of (?:the )?', '', college_name).strip()
            for feat_name in opt.get('features', []):
                if feat_name:
                    name_to_subclass[feat_name] = short

    # Apply subclass assignments to any feature whose `item_name` matches a name in the table
    for f in features:
        item_name = f.get('item_name')
        if item_name and item_name in name_to_subclass:
            # Only set if not already present
            if not f.get('subclass'):
                f['subclass'] = name_to_subclass[item_name]

    # Quick fallback: slug-match table feature names to `item_id`s when exact names don't match.
    # Build slug -> feature object map
    slug_map = {}
    for f in features:
        fid = f.get('item_id') or f.get('item_name')
        if fid:
            slug_map[slugify(f.get('item_name', fid))] = f

    # For any subclass_options we parsed, attempt slug lookup and assign subclass
    for f in features:
        opts = f.get('subclass_options') or []
        for opt in opts:
            college_name = opt.get('name', '')
            short = _re.sub(r'(?i)^college of (?:the )?', '', college_name).strip()
            for feat_name in opt.get('features', []):
                if not feat_name:
                    continue
                feat_slug = slugify(feat_name)
                target = slug_map.get(feat_slug)
                if target and not target.get('subclass'):
                    target['subclass'] = short
    
    print(f"\n✓ Parsed {len(features)} features")
    
    # Count by class
    class_counts = {}
    for feature in features:
        class_name = feature.get('class', 'unknown')
        class_counts[class_name] = class_counts.get(class_name, 0) + 1
    
    print("\nFeatures by class:")
    for class_name, count in sorted(class_counts.items()):
        print(f"  {class_name}: {count}")
    
    # Write JSON output
    output_file = output_dir / 'features.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(features, f, indent=2, ensure_ascii=False)
    
    print(f"\n✓ Generated {output_file}")
    print(f"\nTotal features: {len(features)}")
    
    # Count features with embedded abilities
    features_with_abilities = sum(1 for f in features if 'abilities' in f)
    total_abilities = sum(len(f.get('abilities', [])) for f in features)
    print(f"Features with embedded abilities: {features_with_abilities}")
    print(f"Total embedded abilities: {total_abilities}")


if __name__ == '__main__':
    main()

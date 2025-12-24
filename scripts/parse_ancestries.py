#!/usr/bin/env python3
"""
Parse ancestry markdown files from Rules/Ancestries into JSON format.
Extracts front matter, description, lore, and structured trait information.
Outputs to data/ancestries.json
"""

import os
import json
import re
try:
    import yaml
except Exception:
    yaml = None
from pathlib import Path
from typing import Dict, List, Optional, Any
try:
    from scripts.parse_helpers import parse_damage_clause, parse_frontmatter, strip_markdown_links, parse_stat_block
except Exception:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(__file__))
    from parse_helpers import parse_damage_clause, parse_frontmatter, strip_markdown_links, parse_stat_block

def parse_ancestry_power_roll(text: str) -> Optional[Dict[str, Any]]:
    """Parse power roll table from ancestry ability content."""
    # Look for "Power Roll + [Characteristic]:"
    power_roll_match = re.search(r'\*\*Power Roll \+ ([^:]+):\*\*', text)
    if not power_roll_match:
        return None
    
    characteristic = power_roll_match.group(1).strip()
    
    # Parse tier results
    tiers = []
    
    # Pattern for tier results: - **≤11:** 2 damage
    tier_pattern = r'-\s*\*\*([^:]+):\*\*\s*(.+?)(?=\n-\s*\*\*|$)'
    tier_matches = re.finditer(tier_pattern, text, re.DOTALL)
    
    for match in tier_matches:
        range_text = match.group(1).strip()
        result_text = match.group(2).strip()
        
        # Determine tier
        if '≤11' in range_text or '<11' in range_text:
            tier = 'weak'
        elif '12-16' in range_text:
            tier = 'average'
        elif '17+' in range_text:
            tier = 'strong'
        else:
            tier = 'unknown'
        
        # Parse damage and effects
        damage = None
        effects = []
        
        # Split by semicolons to separate damage and effects
        parts = result_text.split(';')
        
        for part in parts:
            part = part.strip()
            if 'damage' in part.lower():
                parsed = parse_damage_clause(part)
                if parsed:
                    damage = {'formula': parsed.get('formula'), 'type': parsed.get('type')}
                    if 'characteristics' in parsed:
                        damage['characteristics'] = parsed['characteristics']
                    # Fold single-letter type into formula if present
                    if damage.get('type') and len(damage['type']) == 1 and damage['type'].lower() in ['m', 'a', 'r', 'i', 'p']:
                        damage['formula'] = (damage['formula'] + ' ' + damage['type'].upper()).strip()
                        damage['type'] = None
                else:
                    if part:
                        effects.append(part)
            else:
                if part:
                    effects.append(part)
        
        tiers.append({
            'tier': tier,
            'range': range_text,
            'damage': damage,
            'effects': effects
        })
    
        





def parse_ability_stat_block(text):
    """
    Parse an ability stat block (like Shadowmeld or Detonate Sigil).
    Returns a structured ability object.
    """
    # Extract ability name (in ###### header)
    name_match = re.search(r'^#{6}\s+(.+?)$', text, re.MULTILINE)
    ability_name = name_match.group(1).strip() if name_match else ""
    
    # Extract flavor text (italic line after name)
    flavor_match = re.search(r'\*([^*]+)\*', text)
    flavor = flavor_match.group(1).strip() if flavor_match else ""
    
    # Extract table data - can be in multiple rows
    # Find all table rows
    table_rows = re.findall(r'\|(.*?)\|(.*?)\|', text)
    keywords = []
    action_type = ""
    distance = ""
    target = ""
    
    for first_col, second_col in table_rows:
        first_col = first_col.strip()
        second_col = second_col.strip()
        
        # Skip separator rows
        if '---' in first_col or '---' in second_col:
            continue
        
        # Extract keywords from first column (e.g., "**Magic, Ranged, Strike**")
        if not keywords and '**' in first_col:
            keywords_text = re.sub(r'\*\*|\📏|\🎯', '', first_col).strip()
            if keywords_text and not keywords_text.lower().startswith(('self', 'melee', 'ranged')):
                keywords = [k.strip() for k in keywords_text.split(',') if k.strip()]
        
        # Check if first column has distance
        if not distance:
            distance_match = re.search(r'📏\s*(.+?)(?:\*\*|$)', first_col)
            if distance_match:
                distance = distance_match.group(1).strip()
        
        # Extract action type from second column
        if not action_type:
            action_match = re.search(r'\*\*(.+?)\*\*', second_col)
            if action_match:
                action_type = action_match.group(1).strip()
        
        # Extract target from second column
        if not target:
            target_match = re.search(r'🎯\s*(.+?)(?:\*\*|$)', second_col)
            if target_match:
                target = target_match.group(1).strip()
    
    # Extract power roll outcomes
    power_roll = parse_ancestry_power_roll(text)
    
    # Extract effect text
    effect = ""
    effect_match = re.search(r'\*\*Effect:\*\*\s*(.+?)(?=\n\n|$)', text, re.DOTALL)
    if effect_match:
        effect = effect_match.group(1).strip()
    
    ability = {
        "name": ability_name,
        "flavor": flavor,
        "keywords": keywords,
        "action_type": action_type,
        "distance": distance,
        "target": target
    }
    
    if power_roll:
        ability["power_roll"] = power_roll
    
    if effect:
        ability["effect"] = effect
    
    # Component order - determine ordering based on original markdown headings
    parsed_effects = {}
    if effect:
        # Normalize to the same keys used elsewhere: could be 'effect' or before/after
        parsed_effects['effect'] = effect

    section_positions = {}
    sections = [
        ('trigger', r'\*\*Trigger:\*\*'),
        ('effect', r'\*\*Effect:\*\*'),
        ('power_roll', r'\*\*Power Roll'),
        ('persistent', r'\*\*Persistent')
    ]
    for name, pattern in sections:
        m = re.search(pattern, text)
        if m:
            section_positions[name] = m.start()

    sorted_sections = sorted(section_positions.items(), key=lambda x: x[1])
    components = []
    for name, _pos in sorted_sections:
        if name == 'trigger' and 'trigger' in parsed_effects and 'trigger' not in components:
            components.append('trigger')
        elif name == 'effect' and parsed_effects:
            # For ancestry ability parsing we usually only have 'effect'
            if 'effect' not in components:
                components.append('effect')
        elif name == 'power_roll' and power_roll and 'power_roll' not in components:
            components.append('power_roll')
        elif name == 'persistent' and 'persistent' in locals() and persistent_match:
            components.append('persistent')

    # Fallback: if nothing detected, keep existing simple ordering
    if not components:
        if effect and not power_roll:
            components.append('effect')
        if effect and power_roll:
            components.append('effect')
        if power_roll:
            components.append('power_roll')

    if components:
        ability['component_order'] = components
    
    return ability


def parse_stat_bonuses(text):
    """
    Parse stat bonuses from trait text.
    Returns a list of stat bonus objects.
    """
    bonuses = []
    
    # First check for stamina with scaling (more specific pattern)
    stamina_pattern = r'you (?:have|gain) a ([+-]?\d+)\s+bonus to stamina.*?bonus increases by (\d+) at (\d+)(?:th|rd|st|nd), (\d+)(?:th|rd|st|nd), and (\d+)(?:th|rd|st|nd) levels'
    stamina_match = re.search(stamina_pattern, text, re.IGNORECASE | re.DOTALL)
    if stamina_match:
        base_value = int(stamina_match.group(1))
        increase = int(stamina_match.group(2))
        level1 = int(stamina_match.group(3))
        level2 = int(stamina_match.group(4))
        level3 = int(stamina_match.group(5))
        
        bonuses.append({
            "stat": "stamina",
            "value": base_value,
            "scaling": {
                "increase": increase,
                "levels": [level1, level2, level3]
            }
        })

    # Pattern for explicit size set like "Your size is 1S." or "Your size is 1L."
    size_pattern = r'your size is\s*([0-9]+\s*[SL])'
    size_match = re.search(size_pattern, text, re.IGNORECASE)
    if size_match:
        size_value = size_match.group(1).replace(' ', '')
        bonuses.append({
            "stat": "size",
            "value": size_value,
            "type": "set"
        })
    
    # Pattern for disengage bonuses like "+1 bonus to the distance you can shift when you take the Disengage move action"
    disengage_pattern = r'you gain a ([+-]?\d+)\s+bonus to the distance you can shift when you take the disengage'
    disengage_match = re.search(disengage_pattern, text, re.IGNORECASE)
    if disengage_match:
        value = int(disengage_match.group(1))
        bonuses.append({
            "stat": "disengage",
            "value": value
        })
    else:
        # Also try a more flexible pattern
        disengage_pattern2 = r'you gain a ([+-]?\d+)\s+bonus to the distance you can shift'
        disengage_match2 = re.search(disengage_pattern2, text, re.IGNORECASE)
        if disengage_match2 and 'disengage' in text.lower():
            value = int(disengage_match2.group(1))
            bonuses.append({
                "stat": "disengage",
                "value": value
            })
    
    # Pattern for speed bonuses like "you have speed 6"
    speed_set_pattern = r'you have speed (\d+)'
    speed_match = re.search(speed_set_pattern, text, re.IGNORECASE)
    if speed_match:
        value = int(speed_match.group(1))
        bonuses.append({
            "stat": "speed",
            "value": value,
            "type": "set"  # indicates this sets the value rather than adding a bonus
        })

    # Also allow "Your speed is X." phrasing
    speed_set_pattern2 = r'your speed is\s*([+-]?\d+)'
    speed_match2 = re.search(speed_set_pattern2, text, re.IGNORECASE)
    if speed_match2:
        try:
            value = int(speed_match2.group(1))
            bonuses.append({
                "stat": "speed",
                "value": value,
                "type": "set"
            })
        except Exception:
            pass

    # Pattern for phrasing like "your speed increases by 1" or "increase your speed by 1"
    speed_incr_pattern = r'(?:your speed (?:increases|is increased) by|increase your speed by)\s*([+-]?\d+)'
    speed_incr_match = re.search(speed_incr_pattern, text, re.IGNORECASE)
    if speed_incr_match:
        try:
            val = int(speed_incr_match.group(1))
            bonuses.append({
                "stat": "speed",
                "value": val
            })
        except Exception:
            pass

    # Pattern for inline "+1 speed" shorthand
    speed_plus_pattern = r'speed\s*\+\s*([+-]?\d+)'
    speed_plus_match = re.search(speed_plus_pattern, text, re.IGNORECASE)
    if speed_plus_match:
        try:
            val = int(speed_plus_match.group(1))
            bonuses.append({
                "stat": "speed",
                "value": val
            })
        except Exception:
            pass
    
    # Pattern for basic stat bonuses like "+1 bonus to stability" or "gain a +2 bonus to speed"
    # Exclude patterns that contain "distance" and "shift" (disengage bonuses)
    # Detect skill-related bonuses (e.g., "+2 bonus to the roll" for crafting projects)
    skill_bonus_pattern = r'you (?:gain|have) a ([+-]?\d+)\s+bonus to (?:the )?(?:project )?roll'
    skill_bonus_match = re.search(skill_bonus_pattern, text, re.IGNORECASE)
    skill_bonuses = []
    if skill_bonus_match:
        try:
            val = int(skill_bonus_match.group(1))
            # Determine if this references crafting/crafting projects
            group = None
            if re.search(r'craft', text, re.IGNORECASE):
                group = 'crafting'
            skill_bonuses.append({
                'group': group,
                'value': val,
                'context': 'project_roll'
            })
        except Exception:
            pass

    basic_pattern = r'you (?:have|gain) a ([+-]?\d+)\s+bonus to (\w+)'
    for match in re.finditer(basic_pattern, text, re.IGNORECASE):
        value = int(match.group(1))
        stat_raw = match.group(2).lower()

        # Skip if this looks like a skill/project roll bonus we already captured
        if re.search(r'\bto (?:the )?(?:project )?roll\b', match.group(0), re.IGNORECASE):
            continue

        # Skip if this is a disengage bonus (contains distance and shift)
        if 'distance' in text.lower() and 'shift' in text.lower():
            continue

        # Skip stamina if we already parsed stamina with scaling
        if stat_raw == 'stamina' and any(b.get('scaling') for b in bonuses if b.get('stat') == 'stamina'):
            continue

        # Normalize stat names - only accept known stat tokens
        stat_map = {
            'stamina': 'stamina', 'stam': 'stamina',
            'stability': 'stability', 'stab': 'stability',
            'speed': 'speed',
            'size': 'size',
            'might': 'might',
            'agility': 'agility',
            'reason': 'reason',
            'intuition': 'intuition',
            'presence': 'presence',
            'disengage': 'disengage'
        }

        if stat_raw not in stat_map:
            # Not a recognized stat (false positive like 'the' from 'to the roll')
            continue

        stat = stat_map[stat_raw]
        bonuses.append({
            "stat": stat,
            "value": value
        })
    
    # If the trait text indicates conditional triggers (combat, on damage, round-limited, etc.),
    # attach a 'context' field to stat bonuses so UI can filter them.
    ctxs = detect_bonus_context(text)
    if ctxs and bonuses:
        for b in bonuses:
            if isinstance(b, dict) and 'context' not in b:
                b['context'] = ctxs[0] if len(ctxs) == 1 else ctxs

    return bonuses


def parse_skill_info(text):
    """
    Parse skill-related grants and bonuses from trait text.
    Returns a dict with keys 'skill_grants' and 'skill_bonuses'.
    """
    info = {
        'skill_grants': [],
        'skill_bonuses': []
    }

    # Choice of skills from a skill group: "choose two skills from the crafting skill group"
    choice_pattern = r'choose\s+(one|two|three|[0-9]+)\s+skills?\s+from\s+the\s+([a-zA-Z]+)\s+skill\s+group'
    m = re.search(choice_pattern, text, re.IGNORECASE)
    if m:
        count_word = m.group(1).lower()
        count_map = {'one': 1, 'two': 2, 'three': 3}
        count = count_map.get(count_word, int(count_word) if count_word.isdigit() else 1)
        group = m.group(2).lower()
        info['skill_grants'].append({'type': 'choice', 'count': count, 'group': group})

    # Skill-related bonus to project/skill rolls (e.g., +2 to the roll for crafting projects)
    skill_bonus_pattern = r'you (?:gain|have) a ([+-]?\d+)\s+bonus to (?:the )?(?:project )?roll'
    m2 = re.search(skill_bonus_pattern, text, re.IGNORECASE)
    if m2:
        try:
            val = int(m2.group(1))
            group = None
            if re.search(r'craft', text, re.IGNORECASE):
                group = 'crafting'
            info['skill_bonuses'].append({'group': group, 'value': val, 'context': 'project_roll'})
        except Exception:
            pass

    return info


def detect_bonus_context(text: str) -> list:
    """Detect conditional contexts for bonuses from trait text.

    Returns a list of context strings like 'combat', 'on_damage', 'round', etc.
    """
    contexts = []
    lowered = text.lower()

    # Combat-related
    if re.search(r'\bin combat\b|during combat|heat of battle', lowered):
        contexts.append('combat')

    # Damage-related triggers
    if re.search(r'when you take damage|whenever you take damage|when .* takes damage|you take damage', lowered):
        contexts.append('on_damage')

    # First time / once-per-round semantics
    if re.search(r'first time', lowered) or re.search(r'once per (round|combat)', lowered):
        contexts.append('first_time')

    # Round/end-of-round limited effects
    if re.search(r'until the end of the round|end of the round|until the end of the combat|end of combat', lowered):
        contexts.append('round')

    # Generic conditional markers
    if re.search(r'\bwhen\b|\bwhenever\b|\bwhile\b', lowered) and not contexts:
        contexts.append('conditional')

    return contexts


def parse_signature_trait(trait_text):
    """
    Parse a signature trait section.
    Returns a trait object with type and content.
    """
    stat_bonuses = parse_stat_bonuses(trait_text)
    # Parse skill-related grants and bonuses
    skill_info = parse_skill_info(trait_text)
    
    # Check if this contains an ability stat block (has ######)
    if re.search(r'^#{6}', trait_text, re.MULTILINE):
        # Extract the intro text before the ability
        intro_match = re.match(r'^(.*?)(?=#{6})', trait_text, re.DOTALL)
        intro_text = intro_match.group(1).strip() if intro_match else ""
        
        # Parse the ability
        ability = parse_ability_stat_block(trait_text)
        
        result = {
            "type": "ability_with_stat_block",
            "text": intro_text,
            "ability": ability
        }
        if stat_bonuses:
            result["stat_bonuses"] = stat_bonuses
        if skill_info.get('skill_grants'):
            result['skill_grants'] = skill_info['skill_grants']
        if skill_info.get('skill_bonuses'):
            result['skill_bonuses'] = skill_info['skill_bonuses']
        return result
    
    # Check if it's a choice trait
    if re.search(r'\bchoose\b', trait_text, re.IGNORECASE):
        result = {
            "type": "choice",
            "text": trait_text
        }
        if stat_bonuses:
            result["stat_bonuses"] = stat_bonuses
        if skill_info.get('skill_grants'):
            result['skill_grants'] = skill_info['skill_grants']
        if skill_info.get('skill_bonuses'):
            result['skill_bonuses'] = skill_info['skill_bonuses']
        return result
    
    # Check if it's an ability (has maneuver, action references)
    if re.search(r'\b(maneuver|action|triggered action|free action)\b', trait_text, re.IGNORECASE):
        result = {
            "type": "ability",
            "text": trait_text
        }
        if stat_bonuses:
            result["stat_bonuses"] = stat_bonuses
        if skill_info.get('skill_grants'):
            result['skill_grants'] = skill_info['skill_grants']
        if skill_info.get('skill_bonuses'):
            result['skill_bonuses'] = skill_info['skill_bonuses']
        return result
    
    # Default to passive trait
    result = {
        "type": "trait",
        "text": trait_text
    }
    if stat_bonuses:
        result["stat_bonuses"] = stat_bonuses
    if skill_info.get('skill_grants'):
        result['skill_grants'] = skill_info['skill_grants']
    if skill_info.get('skill_bonuses'):
        result['skill_bonuses'] = skill_info['skill_bonuses']
    return result


def parse_purchased_trait(trait_text):
    """
    Parse a purchased trait option.
    Returns a trait object with name, cost, text, and any embedded abilities.
    """
    # Extract name and cost from header (e.g., "##### Can't Take Hold (1 Point)")
    header_match = re.match(r'^#{5}\s+(.+?)\s+\((\d+)\s+Points?\)', trait_text, re.MULTILINE)
    
    if not header_match:
        return None
    
    name = header_match.group(1).strip()
    cost = int(header_match.group(2))
    
    # Remove the header from text
    text_content = re.sub(r'^#{5}\s+.+?\n', '', trait_text, count=1).strip()
    
    stat_bonuses = parse_stat_bonuses(text_content)
    skill_info = parse_skill_info(text_content)
    
    # Check if this trait grants an ability (has a ###### subheader)
    embedded_ability = None
    if re.search(r'^#{6}', text_content, re.MULTILINE):
        # Split into description and ability
        parts = re.split(r'(?=^#{6})', text_content, maxsplit=1, flags=re.MULTILINE)
        description = parts[0].strip()
        
        if len(parts) > 1:
            embedded_ability = parse_ability_stat_block(parts[1])
        
        result = {
            "name": name,
            "cost": cost,
            "text": description,
            "grants_ability": embedded_ability
        }
        if stat_bonuses:
            result["stat_bonuses"] = stat_bonuses
        if skill_info.get('skill_grants'):
            result['skill_grants'] = skill_info['skill_grants']
        if skill_info.get('skill_bonuses'):
            result['skill_bonuses'] = skill_info['skill_bonuses']
        return result
    
    result = {
        "name": name,
        "cost": cost,
        "text": text_content
    }
    if stat_bonuses:
        result["stat_bonuses"] = stat_bonuses
    if skill_info.get('skill_grants'):
        result['skill_grants'] = skill_info['skill_grants']
    if skill_info.get('skill_bonuses'):
        result['skill_bonuses'] = skill_info['skill_bonuses']
    return result


def parse_ancestry_content(content, ancestry_name):
    """
    Parse the markdown content to extract description, lore, and traits.
    Returns dict with structured ancestry data.
    """
    # Remove the main header (## Ancestry Name)
    content = re.sub(r'^##\s+' + re.escape(ancestry_name) + r'\s*$', '', content, flags=re.MULTILINE).strip()
    
    # Split into sections
    sections = re.split(r'^###\s+', content, flags=re.MULTILINE)
    
    # First section is description (before "On [Ancestry]")
    description = sections[0].strip() if sections else ""
    
    # Find "On [Ancestry]" section for lore
    lore = ""
    traits_section_text = ""
    
    for i, section in enumerate(sections[1:], 1):
        if section.startswith('On '):
            # Extract lore content (everything before the next ### section)
            lore_match = re.match(r'On\s+.+?\n\n(.+?)(?=\n###|$)', section, re.DOTALL)
            lore = lore_match.group(1).strip() if lore_match else ""
        elif 'Traits' in section.split('\n')[0]:
            # This is the traits section - gather this and all remaining sections
            traits_section_text = '### ' + section
            # Add all remaining sections too
            for remaining_section in sections[i+1:]:
                traits_section_text += '\n### ' + remaining_section
            break
    
    # Parse traits section
    signature_traits = []
    purchased_traits = {
        "points": 0,
        "quick_build": [],
        "options": []
    }
    
    if traits_section_text:
        # Find all signature traits (can be ### or ####)
        sig_trait_pattern = r'^(###|####)\s+Signature Trait:\s+(.+?)$'
        for match in re.finditer(sig_trait_pattern, traits_section_text, re.MULTILINE):
            trait_name = match.group(2).strip()
            # Extract content until next header of same or higher level
            start_pos = match.end()
            # Look for next ###, ####, or ##### header
            next_header = re.search(r'\n(#{3,5})\s+', traits_section_text[start_pos:])
            if next_header:
                end_pos = start_pos + next_header.start()
            else:
                end_pos = len(traits_section_text)
            
            trait_content = traits_section_text[start_pos:end_pos].strip()
            trait_obj = parse_signature_trait(trait_content)
            trait_obj["name"] = trait_name
            signature_traits.append(trait_obj)
        
        # Find purchased traits section (#### or ##### Purchased [Ancestry] Traits)
        purchased_match = re.search(r'^#{4,5}\s+Purchased\s+.+?Traits\s*\n(.+)$', traits_section_text, re.MULTILINE | re.DOTALL)
        if purchased_match:
            subsection = purchased_match.group(1)
            
            # Extract points and quick build info
            points_match = re.search(r'You have (\d+) ancestry points?', subsection)
            if points_match:
                purchased_traits["points"] = int(points_match.group(1))
            
            # Check for conditional points
            conditional_match = re.search(r'or (\d+) ancestry points? if (.+?)\.', subsection)
            if conditional_match:
                purchased_traits["points_conditional"] = f"or {conditional_match.group(1)} ancestry points if {conditional_match.group(2)}"
            
            # Extract quick build
            qb_match = re.search(r'\(\*Quick Build:\*\s*(.+?)\)', subsection)
            if qb_match:
                qb_text = qb_match.group(1)
                # Parse the quick build list
                purchased_traits["quick_build"] = [item.strip() for item in qb_text.split(',')]
            
            # Extract individual trait options (##### headers)
            trait_options = re.split(r'(?=^#{5}\s+\w)', subsection, flags=re.MULTILINE)
            
            for trait_option in trait_options:
                if trait_option.strip() and trait_option.strip().startswith('#####'):
                    parsed_trait = parse_purchased_trait(trait_option)
                    if parsed_trait:
                        purchased_traits["options"].append(parsed_trait)
    
    return {
        "description": description,
        "lore": lore,
        "traits": {
            "signature": signature_traits,
            "purchased": purchased_traits
        }
    }


def parse_ancestry_file(filepath):
    """
    Parse a single ancestry markdown file.
    Returns a dictionary with all ancestry data.
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    frontmatter, markdown_content = parse_frontmatter(content)
    
    # Strip markdown links from content
    clean_content = strip_markdown_links(markdown_content)
    
    # Get ancestry name from frontmatter
    ancestry_name = frontmatter.get('item_name', '')
    
    # Parse the content structure
    parsed_content = parse_ancestry_content(clean_content, ancestry_name)
    
    # Build the ancestry object
    ancestry = {
        **frontmatter,
        "name": ancestry_name,
        "description": parsed_content['description'],
        "lore": parsed_content['lore'],
        "traits": parsed_content['traits']
    }
    
    return ancestry


def parse_all_ancestries(ancestries_dir):
    """
    Parse all ancestry files in the directory.
    Returns a list of ancestry dictionaries.
    """
    ancestries = []
    
    # Get all markdown files except _Index.md
    md_files = [f for f in os.listdir(ancestries_dir) 
                if f.endswith('.md') and f != '_Index.md']
    
    for filename in sorted(md_files):
        filepath = os.path.join(ancestries_dir, filename)
        print(f"Parsing {filename}...")
        
        try:
            ancestry = parse_ancestry_file(filepath)
            ancestries.append(ancestry)
        except Exception as e:
            print(f"Error parsing {filename}: {e}")
            import traceback
            traceback.print_exc()
    
    return ancestries


def main():
    # Set up paths
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    ancestries_dir = project_root / 'Rules' / 'Ancestries'
    data_dir = project_root / 'data'
    output_file = data_dir / 'ancestries.json'
    
    # Create data directory if it doesn't exist
    data_dir.mkdir(exist_ok=True)
    
    # Parse all ancestries
    print(f"Parsing ancestries from {ancestries_dir}...")
    ancestries = parse_all_ancestries(ancestries_dir)
    
    # Write to JSON file
    print(f"\nWriting {len(ancestries)} ancestries to {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(ancestries, f, indent=2, ensure_ascii=False)
    
    print(f"Done! Ancestries saved to {output_file}")


if __name__ == '__main__':
    main()

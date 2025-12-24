#!/usr/bin/env python3
"""
Parse ability markdown files from Rules/Abilities into structured JSON.

This script processes abilities for all classes, kits, and common actions,
extracting power rolls, effects, costs, and other game mechanics into
a structured format suitable for programmatic use.
"""

import os
import re
import json
try:
    import yaml
except Exception:
    yaml = None
from pathlib import Path
from typing import Dict, List, Optional, Any
try:
    from scripts.parse_helpers import parse_damage_clause, parse_stat_block, parse_frontmatter, strip_markdown_links
except Exception:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(__file__))
    from parse_helpers import parse_damage_clause, parse_stat_block, parse_frontmatter, strip_markdown_links


def slugify(text: str) -> str:
    """Convert text to a slug format."""
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text.strip('-')


_parse_damage_clause = parse_damage_clause


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


def extract_frontmatter(content: str) -> tuple[Dict[str, Any], str]:
    """Extract YAML frontmatter from markdown content."""
    frontmatter_pattern = r'^---\s*\n(.*?)\n---\s*\n(.*)$'
    match = re.match(frontmatter_pattern, content, re.DOTALL)
    
    if match:
        frontmatter_text = match.group(1)
        body = match.group(2)
        try:
            if yaml:
                frontmatter = yaml.safe_load(frontmatter_text)
                return frontmatter or {}, body
            # Fallback basic YAML-ish parser that handles simple key: val and list entries (- item)
            frontmatter = {}
            current_key = None
            for raw in frontmatter_text.splitlines():
                line = raw.rstrip()
                if not line:
                    continue
                # List item
                m_list = re.match(r'^\s*-\s+(.*)$', line)
                if m_list and current_key:
                    frontmatter.setdefault(current_key, [])
                    frontmatter[current_key].append(m_list.group(1).strip().strip('"\''))
                    continue
                # Key: value
                if ':' in line:
                    key, val = line.split(':', 1)
                    key = key.strip()
                    val = val.strip()
                    if val == '':
                        # start of a list or empty value
                        current_key = key
                        frontmatter.setdefault(key, [])
                    else:
                        # scalar value
                        frontmatter[key] = val.strip('"\'')
                        current_key = None
                    continue
            return frontmatter, body
        except Exception as e:
            print(f"Error parsing frontmatter: {e}")
            return {}, content
    
    return {}, content


def parse_power_roll_table(content: str) -> Optional[Dict[str, Any]]:
    """Parse power roll table from ability content."""
    # Look for "Power Roll + [Characteristic]:"
    power_roll_match = re.search(r'\*\*Power Roll \+ ([^:]+):\*\*', content)
    if not power_roll_match:
        return None
    
    characteristic = power_roll_match.group(1).strip()
    
    # Check if there's a conditional (e.g., "If you target an enemy")
    conditional_match = re.search(r'\*\*Effect:\*\*\s*([^.]+)\.\s*(?:If you target an enemy|Otherwise),?\s*you make a power roll', content, re.IGNORECASE)
    conditional = conditional_match.group(1) if conditional_match else None
    
    # Extract just the power roll section (from "Power Roll" to next section)
    power_roll_start = power_roll_match.end()
    
    # Find where the power roll section ends (next ** heading that's not a tier)
    next_section_match = re.search(r'\n\*\*[^*]+\*\*', content[power_roll_start:])
    if next_section_match:
        power_roll_content = content[power_roll_start:power_roll_start + next_section_match.start()].strip()
    else:
        # If no next section, take everything until end
        power_roll_content = content[power_roll_start:].strip()
    
    # Parse tier results from the extracted power roll content
    tiers = []
    
    # Pattern for tier results: - **≤11:** damage; effects
    # Handle optional blockquote markers (> ) before the dash
    tier_pattern = r'(?:>\s*)?-\s*\*\*([^:]+):\*\*\s*(.+?)(?=(?:\n(?:>\s*)?-\s*\*\*|\n\*\*|\Z))'
    tier_matches = re.finditer(tier_pattern, power_roll_content, re.DOTALL)
    
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
        
        # Split by semicolons to separate damage and effects
        parts = result_text.split(';')
        
        for part in parts:
            part = part.strip()
            
            # Check if this part is damage (contains "damage" keyword)
            if 'damage' in part.lower():
                # Extract damage formula and type
                # Patterns like "6 + M holy damage" or "8 + **A** psychic damage" or "5 damage"
                # Match damage formulas including dice (e.g., 2d6), numeric expressions, and characteristic letters (A, M, R, etc.)
                # Also capture an optional damage type (e.g., psychic, fire)
                damage_match = re.search(r'([0-9dD\s+\-\*\/A-Za-z\(\)]+?)(?:\s+([a-zA-Z]+(?:\s+[a-zA-Z]+)*))?\s+damage', part, re.IGNORECASE)
                if damage_match:
                    # Use helper to robustly parse damage clauses
                    parsed = _parse_damage_clause(part)
                    if parsed:
                        damage = {'formula': parsed.get('formula'), 'type': parsed.get('type')}
                        # Preserve characteristics list if present (non-standard field)
                        if 'characteristics' in parsed:
                            damage['characteristics'] = parsed['characteristics']
                    else:
                        # Not a real damage formula; preserve as an effect
                        effects.append(part)
                        continue
            else:
                # This is an effect
                if part:
                    effects.append(part)
        
        tiers.append({
            'tier': tier,
            'range': range_text,
            'damage': damage,
            'effects': effects
        })
    
    if not tiers:
        return None
    
    return {
        'characteristic': characteristic,
        'conditional': conditional,
        'tiers': tiers
    }


def parse_persistent(content: str) -> Optional[Dict[str, Any]]:
    """Parse Persistent mechanic from ability content."""
    persistent_match = re.search(r'\*\*Persistent (\d+):\*\*\s*(.+?)(?=\n\n|\Z)', content, re.DOTALL)
    if persistent_match:
        turns = int(persistent_match.group(1))
        description = persistent_match.group(2).strip()
        return {
            'turns': turns,
            'description': description
        }
    return None


def parse_effects(content: str, has_power_roll: bool) -> Dict[str, Any]:
    """Parse Effect sections from ability content.
    
    Returns a dict with keys for different effect types:
    - 'before': Effect before power roll
    - 'after': Effect after power roll  
    - 'trigger': Trigger condition for triggered abilities
    - 'mark_benefit': Mark benefit effect
    - Other special effects as discovered
    """
    effects = {}
    
    # Parse Trigger (for triggered abilities)
    trigger_match = re.search(r'\*\*Trigger:\*\*\s*(.+?)(?=\n\n\*\*|\n\*\*|\Z)', content, re.DOTALL)
    if trigger_match:
        effects['trigger'] = trigger_match.group(1).strip()
    
    if has_power_roll:
        # Look for Effect BEFORE power roll (between targeting/trigger and Power Roll heading)
        # Pattern: targeting/trigger table -> optional effect -> Power Roll
        before_match = re.search(r'(?:\*\*🎯[^*]+\*\*|\*\*Trigger:\*\*[^\n]+).*?\n\n\*\*Effect:\*\*\s*(.+?)(?=\n\n\*\*Power Roll)', content, re.DOTALL)
        if before_match:
            effects['before'] = before_match.group(1).strip()
        
        # Look for Effect AFTER power roll (after the power roll section)
        after_match = re.search(r'\*\*Power Roll.+?\n(?:- \*\*[^*]+\*\*[^*]*\n)+.*?\n\n\*\*Effect:\*\*\s*(.+?)(?=\n\n\*\*Mark Benefit|\n\n\*\*Persistent|\n\n|$)', content, re.DOTALL)
        if after_match:
            effects['after'] = after_match.group(1).strip()
        
        # If we have both before and after effects, keep them as separate keys
        # If we only have one effect, rename it to 'effect' for consistency with component_order
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
        # For abilities without power rolls, look for Effect (may be after Trigger)
        # Match until next major heading or end, including lists and multiple paragraphs
        effect_match = re.search(r'\*\*Effect:\*\*\s*(.+?)(?=\n#{5,6}|\Z)', content, re.DOTALL)
        if effect_match:
            effects['effect'] = effect_match.group(1).strip()
    
    # Parse Mark Benefit (special effect type for tactician marks)
    mark_benefit_match = re.search(r'\*\*Mark Benefit:\*\*\s*(.+?)(?=\n\n\*\*Persistent|\n\n|$)', content, re.DOTALL)
    if mark_benefit_match:
        effects['mark_benefit'] = mark_benefit_match.group(1).strip()
    
    # Parse Strained section (some abilities include a 'Strained' subsection)
    strained_match = re.search(r'\*\*Strained:\*\*\s*(.+?)(?=\n\n\*\*|\n\*\*|\Z)', content, re.DOTALL)
    if strained_match:
        effects['strained'] = strained_match.group(1).strip()
    
    return effects if effects else None


def parse_targeting_table(content: str) -> Optional[Dict[str, str]]:
    """Parse the targeting table (distance and target)."""
    # Look for the table with distance and target
    # Pattern: | **Keywords** | **Action** |
    #          | ------------ | ---------: |
    #          | **📏 Distance** | **🎯 Target** |
    
    distance_match = re.search(r'\*\*📏\s*([^*]+?)\*\*', content)
    target_match = re.search(r'\*\*🎯\s*([^*]+?)\*\*', content)
    
    if distance_match or target_match:
        return {
            'distance': distance_match.group(1).strip() if distance_match else None,
            'target': target_match.group(1).strip() if target_match else None
        }
    return None


def parse_ability_file(file_path: Path, base_path: Path) -> Optional[Dict[str, Any]]:
    """Parse a single ability markdown file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return None
    
    # Extract frontmatter
    frontmatter, body = extract_frontmatter(content)
    
    if not frontmatter:
        print(f"No frontmatter found in {file_path}")
        return None
    
    # Extract flavor text (text in italics after the ability name)
    flavor_match = re.search(r'#+ .+?\n\n\*(.+?)\*', body)
    flavor = flavor_match.group(1).strip() if flavor_match else frontmatter.get('flavor')
    
    # Parse power roll
    power_roll = parse_power_roll_table(body)
    
    # Parse targeting
    targeting = parse_targeting_table(body)
    
    # Parse effects (before and after power roll)
    effects = parse_effects(body, power_roll is not None)
    
    # Parse persistent
    persistent = parse_persistent(body)
    
    # Parse stat block if present
    stat_block = parse_stat_block(body)
    
    # Build the ability object
    item_id = frontmatter.get('item_id')
    
    # Create base_id by removing cost suffix (e.g., "arrest-5-wrath" -> "arrest")
    base_id = item_id
    if item_id:
        # Remove patterns like "-5-wrath", "-3-clarity", etc.
        base_id = re.sub(r'-\d+-\w+$', '', item_id)
    
    ability = {
        'item_id': item_id,
        'base_id': base_id,
        'item_name': frontmatter.get('item_name'),
        'item_index': frontmatter.get('item_index'),
        'source': frontmatter.get('source', 'mcdm.heroes.v1'),
        'type': frontmatter.get('type', 'ability'),
        'class': frontmatter.get('class'),
        'level': frontmatter.get('level'),
        'ability_type': frontmatter.get('ability_type'),  # Signature or None
        'feature_type': frontmatter.get('feature_type'),
    }
    
    # Action information
    action_type = frontmatter.get('action_type')
    keywords = frontmatter.get('keywords', [])
    
    if action_type or keywords:
        ability['action'] = {
            'type': action_type,
            'keywords': keywords
        }
    
    # Cost information
    cost_amount = frontmatter.get('cost_amount')
    cost_resource = frontmatter.get('cost_resource')
    
    if cost_amount and cost_resource:
        ability['cost'] = {
            'amount': cost_amount,
            'resource': cost_resource
        }
    else:
        ability['cost'] = None
    
    # Targeting
    if targeting:
        ability['targeting'] = targeting
    else:
        ability['targeting'] = None
    
    # Flavor text
    ability['flavor'] = flavor
    
    # Power roll
    ability['power_roll'] = power_roll
    
    # Effects (includes trigger, before, after, mark_benefit, etc.)
    ability['effects'] = effects
    
    # Persistent
    ability['persistent'] = persistent
    
    # Component order - determine actual ordering from the original markdown
    parsed_effects = parse_effects(body, power_roll is not None)

    # Find positions of section headings in the body so we preserve original order
    section_positions = {}
    sections = [
        ('trigger', r'\*\*Trigger:\*\*'),
        ('effect', r'\*\*Effect:\*\*'),
        ('power_roll', r'\*\*Power Roll'),
        ('mark_benefit', r'\*\*Mark Benefit:\*\*'),
        ('strained', r'\*\*Strained:\*\*'),
        ('persistent', r'\*\*Persistent'),
        ('cost_options', r'\*\*Spend')
    ]

    for name, pattern in sections:
        m = re.search(pattern, body)
        if m:
            section_positions[name] = m.start()

    sorted_sections = sorted(section_positions.items(), key=lambda x: x[1])
    components = []

    for name, _pos in sorted_sections:
        if name == 'trigger' and parsed_effects and 'trigger' in parsed_effects and 'trigger' not in components:
            components.append('trigger')
        elif name == 'effect' and parsed_effects:
            # Respect available parsed effect keys; add them in logical order
            if 'before' in parsed_effects and 'before' not in components:
                components.append('before')
            elif 'after' in parsed_effects and 'after' not in components:
                components.append('after')
            elif 'effect' in parsed_effects and 'effect' not in components:
                components.append('effect')
        elif name == 'power_roll' and power_roll is not None and 'power_roll' not in components:
            components.append('power_roll')
        elif name == 'mark_benefit' and parsed_effects and 'mark_benefit' in parsed_effects and 'mark_benefit' not in components:
            components.append('mark_benefit')
        elif name == 'strained' and parsed_effects and 'strained' in parsed_effects and 'strained' not in components:
            components.append('strained')
        elif name == 'persistent' and persistent is not None and 'persistent' not in components:
            components.append('persistent')
        elif name == 'cost_options' and ability.get('cost') and 'cost' not in components:
            components.append('cost')

    # Fallback: if no headings found, build a conservative ordering
    if not components:
        fallback = []
        if parsed_effects and 'trigger' in parsed_effects:
            fallback.append('trigger')
        if parsed_effects and 'before' in parsed_effects:
            fallback.append('before')
        if power_roll is not None:
            fallback.append('power_roll')
        if parsed_effects and 'after' in parsed_effects:
            fallback.append('after')
        if parsed_effects and 'mark_benefit' in parsed_effects:
            fallback.append('mark_benefit')
        if persistent is not None:
            fallback.append('persistent')
        if parsed_effects and 'effect' in parsed_effects:
            fallback.append('effect')
        components = fallback

    if components:
        ability['component_order'] = components
    
    # Stat block (for summoned creatures, companions, etc.)
    if stat_block:
        ability['stat_block'] = stat_block
    
    # Subclass (for subclass-specific abilities)
    if 'subclass' in frontmatter:
        ability['subclass'] = frontmatter['subclass']
    
    return ability


def parse_abilities_directory(abilities_dir: Path) -> List[Dict[str, Any]]:
    """Parse all ability files in the abilities directory."""
    abilities = []
    
    # Walk through all subdirectories
    for root, dirs, files in os.walk(abilities_dir):
        for file in files:
            if file.endswith('.md'):
                file_path = Path(root) / file
                ability = parse_ability_file(file_path, abilities_dir)
                if ability:
                    abilities.append(ability)
    
    return abilities


def main():
    # Get the repository root (parent of scripts directory)
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    
    abilities_dir = repo_root / 'Rules' / 'Abilities'
    output_file = repo_root / 'data' / 'abilities.json'
    
    print(f"Parsing abilities from {abilities_dir}...")
    
    if not abilities_dir.exists():
        print(f"Error: Abilities directory not found at {abilities_dir}")
        return
    
    # Parse all abilities
    abilities = parse_abilities_directory(abilities_dir)
    
    # Sort by class, level, and name for consistency
    abilities.sort(key=lambda x: (
        x.get('class') or '',
        x.get('level') or 0,
        x.get('item_name') or ''
    ))
    
    # Create output directory if it doesn't exist
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Write to JSON file
    print(f"\nWriting {len(abilities)} abilities to {output_file}...")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(abilities, f, indent=2, ensure_ascii=False)
    
    print(f"Done! Abilities saved to {output_file}")
    
    # Print summary statistics
    class_counts = {}
    for ability in abilities:
        class_name = ability.get('class', 'Unknown')
        class_counts[class_name] = class_counts.get(class_name, 0) + 1
    
    print("\nAbilities by class:")
    for class_name in sorted(class_counts.keys()):
        print(f"  {class_name}: {class_counts[class_name]}")


if __name__ == '__main__':
    main()

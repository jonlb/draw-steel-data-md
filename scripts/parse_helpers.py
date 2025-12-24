#!/usr/bin/env python3
"""Shared parsing helpers for the Draw Steel markdown parsers.

Provides:
- parse_damage_clause(part)
- parse_frontmatter(content)
- strip_markdown_links(text)
- parse_stat_block(content)
"""
from typing import Optional, Dict, Any
import re
try:
    import yaml
except Exception:
    yaml = None


def parse_damage_clause(part: str) -> Optional[Dict[str, Any]]:
    """Parse a text part that may describe damage and return structured dict.

    Returns None if the part shouldn't be treated as a damage clause.
    """
    if not part or 'damage' not in part.lower():
        return None

    m = re.search(r'([0-9dD\w\s+\-\*\/\(\),]+?)(?:\s+([a-zA-Z]+(?:\s+[a-zA-Z]+)*))?\s+damage', part, re.IGNORECASE)
    if m:
        raw = m.group(1).strip().rstrip(',')
        damage_type = m.group(2).lower() if m.group(2) else None
        tokens = re.split(r',|\bor\b', raw, flags=re.IGNORECASE)
        tokens = [t.strip() for t in tokens if t.strip()]
        formula_candidate = tokens[0] if tokens else raw
        char_list = None
        if len(tokens) > 1 and all(len(t) == 1 and t.isalpha() for t in tokens[1:]):
            char_list = [t.upper() for t in tokens[1:]]

        if re.search(r'\d|\d+d\d+|\b[AaMmRrPpIi]\b', formula_candidate) or re.search(r'\blevel\b|your level', formula_candidate, re.IGNORECASE):
            formula = re.sub(r'\*\*([^*]+)\*\*', r'\1', formula_candidate)
            formula = formula.replace('\u2013', '-').replace('\u2014', '-')
            formula = re.sub(r'\s*([+\-])\s*', r' \1 ', formula)
            formula = re.sub(r'\s+', ' ', formula).strip()
            parsed = {'formula': formula}
            if damage_type:
                parsed['type'] = damage_type
            if char_list:
                parsed['characteristics'] = char_list
            return parsed

    m2 = re.search(r'([A-Za-z]+)\s+damage\s+equal to\s+([^;]+)', part, re.IGNORECASE)
    if m2:
        parsed = {'formula': re.sub(r'\s+', ' ', m2.group(2).strip()), 'type': m2.group(1).lower()}
        return parsed

    return None


def parse_frontmatter(content: str) -> tuple[Dict[str, Any], str]:
    """Extract YAML frontmatter and remaining content from a markdown file.

    If PyYAML is available it will be used; otherwise a conservative
    fallback parser handles simple key: value and list items.
    """
    if not content.startswith('---'):
        return {}, content

    parts = content.split('---', 2)
    if len(parts) < 3:
        return {}, content
    frontmatter_text = parts[1].strip()
    body = parts[2].strip()
    if yaml:
        try:
            frontmatter = yaml.safe_load(frontmatter_text)
            return frontmatter or {}, body
        except Exception as e:
            print(f"Error parsing YAML frontmatter: {e}")
            return {}, content

    frontmatter = {}
    current_key = None
    for line in frontmatter_text.splitlines():
        line = line.rstrip()
        if not line:
            continue
        if line.strip().startswith('- '):
            if current_key:
                if current_key not in frontmatter or not isinstance(frontmatter[current_key], list):
                    frontmatter[current_key] = []
                frontmatter[current_key].append(line.strip()[2:].strip().strip('"\''))
            continue
        if ':' in line:
            key, val = line.split(':', 1)
            key = key.strip()
            val = val.strip().strip('"\'')
            frontmatter[key] = val
            current_key = key
    return frontmatter, body


def strip_markdown_links(text: str) -> str:
    """Remove markdown links from text, keeping only the link text."""
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    text = re.sub(r'\[([^\]]+)\]\[[^\]]*\]', r'\1', text)
    text = re.sub(r'^\[([^\]]+)\]:\s+.*$', '', text, flags=re.MULTILINE)
    return text


def parse_stat_block(content: str) -> Optional[Dict[str, Any]]:
    """Extract stat block information from content if present.

    Returns a dict with keys: name, full_content, stat_table, stats, traits
    """
    match = re.search(r'>?\s*#{6}\s+(.+?)\s+Statblock\s*\n', content, re.IGNORECASE)
    if not match:
        return None

    stat_block_name = match.group(1).strip()
    start_pos = match.end()
    next_heading = re.search(r'\n(?:>\s*)?#{1,6}\s+', content[start_pos:])
    if next_heading:
        stat_block_content = content[start_pos:start_pos + next_heading.start()]
    else:
        stat_block_content = content[start_pos:]

    creature_match = re.search(r'>?\s*\*\*(.+?)\*\*\s*\n', stat_block_content)
    creature_name = creature_match.group(1).strip() if creature_match else stat_block_name

    table_lines = []
    lines = stat_block_content.split('\n')
    in_table = False
    for line in lines:
        if creature_name in line and '**' in line:
            continue
        if '|' in line and not line.strip().startswith('> >'):
            table_lines.append(line)
            in_table = True
        elif in_table and line.strip() in ['', '>']:
            break

    stat_table = '\n'.join(table_lines).strip() if table_lines else None
    if stat_table:
        stat_table = re.sub(r'^>\s*', '', stat_table, flags=re.MULTILINE)

    traits = []
    if stat_table:
        table_end = stat_block_content.find(stat_table) + len(stat_table)
        traits_section = stat_block_content[table_end:]
    else:
        traits_section = stat_block_content

    trait_splits = re.split(r'\n>\s*>\s*\*\*([^*]+)\*\*\s*\n', traits_section)
    for i in range(1, len(trait_splits), 2):
        if i + 1 <= len(trait_splits):
            trait_name = trait_splits[i].strip()
            trait_content = trait_splits[i + 1] if i + 1 < len(trait_splits) else ''
            trait_content = re.sub(r'^>\s*>?\s*', '', trait_content, flags=re.MULTILINE).strip()
            if '|' in trait_content:
                traits.append({'name': trait_name, 'type': 'ability', 'content': trait_content})
            else:
                traits.append({'name': trait_name, 'type': 'trait', 'description': trait_content})

    def parse_stat_table_fields(table: str) -> Dict[str, Any]:
        if not table:
            return {}
        lines = table.strip().split('\n')
        if len(lines) < 3:
            return {}

        def extract_value(cell: str) -> Optional[str]:
            cell = cell.strip()
            bold_match = re.search(r'\*\*([^*]+)\*\*', cell)
            if bold_match:
                value = bold_match.group(1).strip()
            else:
                value = re.sub(r'<br/>.*', '', cell).strip()
            return value if value and value != '-' else None

        def split_row(line: str) -> list:
            cells = [c.strip() for c in line.strip('|').split('|')]
            return cells

        row1 = split_row(lines[0]) if len(lines) > 0 else []
        row2 = split_row(lines[2]) if len(lines) > 2 else []
        row3 = split_row(lines[3]) if len(lines) > 3 else []
        row4 = split_row(lines[4]) if len(lines) > 4 else []

        stats: Dict[str, Any] = {}
        if len(row1) >= 5:
            ancestry = extract_value(row1[0])
            if ancestry:
                stats['ancestry'] = ancestry
            level_val = extract_value(row1[2])
            if level_val:
                level_match = re.search(r'Level\s+(\d+)', level_val)
                if level_match:
                    stats['level'] = int(level_match.group(1))
                else:
                    stats['level'] = level_val
            role = extract_value(row1[3])
            if role:
                stats['role'] = role
            ev = extract_value(row1[4])
            if ev and ev.startswith('EV'):
                ev_match = re.search(r'EV\s+(.+)', ev)
                stats['ev'] = ev_match.group(1).strip() if ev_match else ev

        if len(row2) >= 5:
            size = extract_value(row2[0])
            if size:
                stats['size'] = size
            speed = extract_value(row2[1])
            if speed:
                try:
                    stats['speed'] = int(speed)
                except (ValueError, TypeError):
                    stats['speed'] = speed
            stamina = extract_value(row2[2])
            if stamina:
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

        return stats

    stats = parse_stat_table_fields(stat_table) if stat_table else None

    return {
        'name': creature_name,
        'full_content': stat_block_content.strip(),
        'stat_table': stat_table,
        'stats': stats,
        'traits': traits if traits else None
    }#!/usr/bin/env python3
"""Shared parsing helpers for the Draw Steel markdown parsers.

Currently contains `parse_damage_clause` to extract structured damage
info (formula, type, characteristics) from a textual clause.
"""
from typing import Optional, Dict, Any
import re


def parse_damage_clause(part: str) -> Optional[dict]:
    """Parse a text part that may describe damage and return structured dict.

    Returns None if the part shouldn't be treated as a damage clause.

    Examples handled:
    - "5 + A, R, I, or P fire damage" -> {'formula':'5 + A', 'type':'fire', 'characteristics':['A','R','I','P']}
    - "Lightning damage equal to your level" -> {'formula':'your level','type':'lightning'}
    - "2d6 + A fire damage" -> {'formula':'2d6 + A','type':'fire'}
    - "some text about damage resistance" -> None (preserved as effect)
    """
    if not part or 'damage' not in part.lower():
        return None

    # Try pattern: formula (with optional char list) before 'damage'
    m = re.search(r'([0-9dD\w\s+\-\*\/\(\),]+?)(?:\s+([a-zA-Z]+(?:\s+[a-zA-Z]+)*))?\s+damage', part, re.IGNORECASE)
    if m:
        raw = m.group(1).strip().rstrip(',')
        damage_type_raw = m.group(2) if m.group(2) else None
        damage_type = damage_type_raw.lower() if damage_type_raw else None

        # Split tokens to detect char lists like "A, R, I, or P"
        tokens = re.split(r',|\bor\b', raw, flags=re.IGNORECASE)
        tokens = [t.strip() for t in tokens if t.strip()]
        formula_candidate = tokens[0] if tokens else raw
        char_list = None
        if len(tokens) > 1 and all(len(t) == 1 and t.isalpha() for t in tokens[1:]):
            char_list = [t.upper() for t in tokens[1:]]

        # If damage_type_raw begins with a single-letter characteristic (e.g. "R psychic"),
        # treat that leading letter as a characteristic and move it into the formula/characteristics,
        # leaving the remaining words as the damage type.
        if damage_type_raw:
            parts = [p for p in damage_type_raw.split() if p]
            if len(parts) >= 2 and len(parts[0]) == 1 and parts[0].isalpha():
                lead = parts[0].upper()
                # add to characteristics list
                if not char_list:
                    char_list = [lead]
                else:
                    char_list = [lead] + char_list
                # ensure formula includes the characteristic token
                if not re.search(r'\b' + re.escape(lead) + r'\b', formula_candidate):
                    formula_candidate = (formula_candidate + ' ' + lead).strip()
                # remaining parts become the real damage type
                remaining = ' '.join(parts[1:]).strip()
                damage_type = remaining.lower() if remaining else None

        # Validate candidate looks like damage formula: contains digits/dice, characteristic letters, or 'level'
        if re.search(r'\d|\d+d\d+|\b[AaMmRrPpIi]\b', formula_candidate) or re.search(r'\blevel\b|your level', formula_candidate, re.IGNORECASE):
            formula = re.sub(r'\*\*([^*]+)\*\*', r'\1', formula_candidate)
            formula = formula.replace('\u2013', '-').replace('\u2014', '-')
            formula = re.sub(r'\s*([+\-])\s*', r' \1 ', formula)
            formula = re.sub(r'\s+', ' ', formula).strip()
            parsed = {'formula': formula}
            if damage_type:
                parsed['type'] = damage_type
            if char_list:
                parsed['characteristics'] = char_list
            return parsed

    # Pattern: 'Type damage equal to X'
    m2 = re.search(r'([A-Za-z]+)\s+damage\s+equal to\s+([^;]+)', part, re.IGNORECASE)
    if m2:
        parsed = {'formula': re.sub(r'\s+', ' ', m2.group(2).strip()), 'type': m2.group(1).lower()}
        return parsed

    # Nothing matched confidently — return None to preserve as effect
    return None

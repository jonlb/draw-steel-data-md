#!/usr/bin/env python3
"""
Parse class markdown files from Rules/Classes directory into structured JSON.
Extracts class information including subclasses, heroic resources, advancement tables,
features by level, and ability selection pools without including ability content.
"""

import os
import re
import json
import yaml
from pathlib import Path

def strip_markdown_links(text):
    """Remove markdown links but keep the link text."""
    if not text:
        return text
    # Remove reference-style links [text](#link)
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    return text.strip()

def parse_stat_block(content):
    """Extract stat block information from content if present."""
    # Look for "X Statblock" heading
    match = re.search(r'#{6}\s+(.+?)\s+Statblock\s*\n', content, re.IGNORECASE)
    if not match:
        return None
    
    stat_block_name = match.group(1).strip()
    start_pos = match.end()
    
    # Find the end of the stat block section (next heading or end of content)
    next_heading = re.search(r'\n#{1,6}\s+', content[start_pos:])
    if next_heading:
        stat_block_content = content[start_pos:start_pos + next_heading.start()]
    else:
        stat_block_content = content[start_pos:]
    
    # Extract the creature name (bold text after the heading)
    creature_match = re.search(r'\*\*(.+?)\*\*', stat_block_content)
    creature_name = creature_match.group(1).strip() if creature_match else stat_block_name
    
    # Extract the main stat table (the table with Size, Speed, Stamina, etc.)
    table_match = re.search(r'\|[^\n]+\|[^\n]+\n\|[:\-\s|]+\n(\|[^\n]+\n)+', stat_block_content)
    stat_table = table_match.group(0) if table_match else None
    
    # Extract traits/abilities (blockquoted sections after the table)
    traits = []
    trait_pattern = r'>\s+\*\*([^*]+)\*\*\s*\n((?:>\s+[^\n]*\n)*)'
    for trait_match in re.finditer(trait_pattern, stat_block_content):
        trait_name = trait_match.group(1).strip()
        trait_desc = trait_match.group(2)
        # Clean up the trait description
        trait_desc = re.sub(r'>\s+', '', trait_desc).strip()
        traits.append({
            'name': trait_name,
            'description': trait_desc
        })
    
    return {
        'name': creature_name,
        'full_content': stat_block_content.strip(),
        'stat_table': stat_table,
        'traits': traits if traits else None
    }

def parse_frontmatter(content):
    """Extract YAML frontmatter from markdown content."""
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
    if match:
        try:
            return yaml.safe_load(match.group(1))
        except yaml.YAMLError:
            return {}
    return {}

def parse_quote(content):
    """Extract the class quote (blockquote after description)."""
    # Look for blockquote pattern after class description
    match = re.search(r'<!-- -->\s*>\s*"([^"]+)"\s*>\s*>\s*\*\*([^*]+)\*\*', content, re.DOTALL)
    if match:
        return {
            'text': match.group(1).strip(),
            'author': match.group(2).strip()
        }
    return None

def parse_starting_characteristics(content):
    """Parse starting characteristics arrays."""
    match = re.search(r'\*\*Starting Characteristics:\*\*\s+(.+?)(?=\*\*Weak Potency:)', content, re.DOTALL)
    if not match:
        return None
    
    char_text = match.group(1)
    
    # Extract required characteristics
    required = []
    required_match = re.search(r'You start with (?:a|an) (\w+) of 2(?: and (?:a|an) (\w+) of 2)?', char_text)
    if required_match:
        required.append(required_match.group(1))
        if required_match.group(2):
            required.append(required_match.group(2))
    
    # Extract arrays - each bullet point is a separate array
    arrays = []
    # Match bullet points with comma-separated numbers (e.g., "- 2, −1, −1")
    array_lines = re.findall(r'^[-−•]\s*((?:[-−]?\d+,?\s*)+)$', char_text, re.MULTILINE)
    for array_line in array_lines:
        # Split by comma and extract numbers
        numbers = [x.strip() for x in array_line.replace('−', '-').replace(',', ' ').split()]
        if numbers:
            try:
                array = [int(x) for x in numbers if x]
                if array:  # Only add non-empty arrays
                    arrays.append(array)
            except ValueError:
                continue
    
    return {
        'required': required,
        'arrays': arrays
    }

def parse_skill_sources(from_text):
    """Parse skill sources from a 'from' clause."""
    sources = []
    
    # Handle complex cases like:
    # 1. "Alertness, Architecture, ..., or the skills of the exploration skill group"
    # 2. "Criminal Underworld or the skills of the exploration, interpersonal, or intrigue skill groups"
    # 3. "the interpersonal or lore skill groups"
    # 4. "the intrigue or lore skill groups"
    
    # Check if we have both specific skills AND groups
    if ' or the skills of the ' in from_text or ' or the ' in from_text:
        # Split by "or the skills of" or "or the"
        before_or = from_text.split(' or the ')[0]
        after_or = ' or the '.join(from_text.split(' or the ')[1:])
        
        # Parse skills before "or"
        if before_or and not any(g in before_or.lower() for g in ['interpersonal', 'exploration', 'intrigue', 'lore', 'crafting']):
            # It's a list of specific skills
            specific_skills = [s.strip() for s in before_or.split(',')]
            for skill in specific_skills:
                if skill:
                    sources.append({'type': 'skill', 'value': skill})
        
        # Parse groups after "or the"
        # Could be "skills of the X, Y, or Z skill groups" or just "X skill group"
        for group_name in ['interpersonal', 'exploration', 'intrigue', 'lore', 'crafting']:
            if group_name in after_or.lower():
                sources.append({'type': 'group', 'value': group_name})
    else:
        # Simple pattern: just groups like "the interpersonal or lore skill groups"
        # or could be a single specific skill
        potential_groups = []
        for group_name in ['interpersonal', 'exploration', 'intrigue', 'lore', 'crafting']:
            if group_name in from_text.lower():
                potential_groups.append(group_name)
        
        if potential_groups:
            for group in potential_groups:
                sources.append({'type': 'group', 'value': group})
        else:
            # Might be a single specific skill
            clean_text = from_text.replace('the', '').strip()
            if clean_text:
                sources.append({'type': 'skill', 'value': clean_text})
    
    return sources

def parse_basics(content):
    """Parse the Basics section."""
    basics_match = re.search(r'### Basics\s*\n\n(.+?)(?=###|\Z)', content, re.DOTALL)
    if not basics_match:
        return None
    
    basics_text = basics_match.group(1)
    
    # Starting characteristics
    starting_chars = parse_starting_characteristics(content)
    
    # Potency
    potency = {}
    weak_match = re.search(r'\*\*Weak Potency:\*\*\s*(.+)', basics_text)
    avg_match = re.search(r'\*\*Average Potency:\*\*\s*(.+)', basics_text)
    strong_match = re.search(r'\*\*Strong Potency:\*\*\s*(.+)', basics_text)
    if weak_match:
        potency['weak'] = weak_match.group(1).strip()
    if avg_match:
        potency['average'] = avg_match.group(1).strip()
    if strong_match:
        potency['strong'] = strong_match.group(1).strip()
    
    # Stamina
    stamina = {}
    start_stamina = re.search(r'\*\*Starting Stamina at 1st Level:\*\*\s*(\d+)', basics_text)
    level_stamina = re.search(r'\*\*Stamina Gained at 2nd and Higher Levels:\*\*\s*(\d+)', basics_text)
    if start_stamina:
        stamina['starting'] = int(start_stamina.group(1))
    if level_stamina:
        stamina['per_level'] = int(level_stamina.group(1))
    
    # Recoveries
    recoveries = None
    rec_match = re.search(r'\*\*Recoveries:\*\*\s*(\d+)', basics_text)
    if rec_match:
        recoveries = int(rec_match.group(1))
    
    # Skills - parse with full choice mechanics and quick build
    skills = {}
    skills_match = re.search(r'\*\*Skills:\*\*\s*(.+?)(?=\n\n|\*\*|###|\Z)', basics_text, re.DOTALL)
    if skills_match:
        skills_text = skills_match.group(1)
        
        # Extract quick build
        quick_build = []
        quick_match = re.search(r'\(\*Quick Build:\*\*?\s*(.+?)\)', skills_text)
        if quick_match:
            quick_text = quick_match.group(1).rstrip('.')
            quick_build = [s.strip() for s in quick_text.split(',')]
        
        # Parse given skills (skills you automatically gain)
        given = []
        # Pattern: "You gain the X skill" or "You gain the X and Y skills"
        gain_matches = re.findall(r'You gain the ([A-Z][^(]+?)\s+skill(?:s)?\s*\(', skills_text)
        for gain_text in gain_matches:
            # Handle "X and Y" or just "X"
            if ' and ' in gain_text:
                given.extend([s.strip() for s in gain_text.split(' and ')])
            else:
                given.append(gain_text.strip())
        
        # Parse choice rules
        choices = []
        
        # Find all "Choose X from Y" patterns - need to handle multiple separate choices
        # Pattern 1: "Then choose X skills from Y"
        # Pattern 2: "choose X from Y and Z from W" (Troubadour case)
        
        # First try compound pattern: "choose X from Y and Z from W"
        compound_pattern = r'(?:Then )?[Cc]hoose (\w+) skills? from ([^)]+?) and (\w+) skills? from ([^)]+?)(?:\s*\(|\.)'
        compound_match = re.search(compound_pattern, skills_text)
        
        if compound_match:
            # Handle Troubadour-style: two separate choice rules
            # First choice
            count1_word = compound_match.group(1).lower()
            count_map = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5}
            count1 = count_map.get(count1_word, 0)
            from1_text = compound_match.group(2).strip()
            
            sources1 = parse_skill_sources(from1_text)
            if sources1 and count1 > 0:
                choices.append({
                    'count': count1,
                    'from': sources1,
                    'operator': 'OR'
                })
            
            # Second choice
            count2_word = compound_match.group(3).lower()
            count2 = count_map.get(count2_word, 0)
            from2_text = compound_match.group(4).strip()
            
            sources2 = parse_skill_sources(from2_text)
            if sources2 and count2 > 0:
                choices.append({
                    'count': count2,
                    'from': sources2,
                    'operator': 'OR'
                })
        else:
            # Simple pattern: single choice rule
            simple_pattern = r'(?:Then )?[Cc]hoose (?:any )?(\w+) skills? from (.+?)(?:\s*\(|\.)'
            
            for match in re.finditer(simple_pattern, skills_text):
                count_word = match.group(1).lower()
                count_map = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5}
                count = count_map.get(count_word, 0)
                
                from_text = match.group(2).strip()
                sources = parse_skill_sources(from_text)
                
                if sources and count > 0:
                    choices.append({
                        'count': count,
                        'from': sources,
                        'operator': 'OR'
                    })
        
        skills = {
            'given': given,
            'choices': choices,
            'quick_build': quick_build
        }
    
    return {
        'starting_characteristics': starting_chars,
        'potency': potency,
        'stamina': stamina,
        'recoveries': recoveries,
        'skills': skills
    }

def parse_subclass_info(content, class_name):
    """Parse subclass information."""
    subclass_patterns = {
        'Censor': ('Censor Order', 'order'),
        'Conduit': ('Deity and Domains', 'domain'),
        'Elementalist': ('Elemental Specialization', 'specialization'),
        'Fury': ('Primordial Aspect', 'aspect'),
        'Null': ('Null Tradition', 'tradition'),
        'Shadow': ('Shadow College', 'college'),
        'Tactician': ('Tactical Doctrine', 'doctrine'),
        'Talent': ('Talent Tradition', 'tradition'),
        'Troubadour': ('Troubadour Class Act', 'class_act')
    }
    
    subclass_name, subclass_type = subclass_patterns.get(class_name, ('Subclass', 'subclass'))
    
    # Find the subclass section
    pattern = rf'#### {re.escape(subclass_name)}\s*\n\n(.+?)(?=####|\Z)'
    match = re.search(pattern, content, re.DOTALL)
    if not match:
        return None
    
    subclass_text = match.group(1)
    
    # Extract options (bulleted list)
    # Handle both bold format: - **Option:** description
    # And plain format: - Option: description (Shadow class)
    options = []
    
    # Try bold format first
    option_pattern = r'[-−]\s+\*\*([^:*]+):\*\*\s+(.+?)(?=\n\s*[-−]|\n\n|\Z)'
    matches = list(re.finditer(option_pattern, subclass_text, re.DOTALL))
    
    # If no bold matches, try plain format
    if not matches:
        option_pattern = r'[-−]\s+([^:*\n]+):\s+(.+?)(?=\n\s*[-−]|\n\n|\Z)'
        matches = list(re.finditer(option_pattern, subclass_text, re.DOTALL))
    
    # Special handling for Talent and Elementalist - options are in a sentence, but descriptions are in bold bullets
    if class_name in ['Talent', 'Elementalist'] and not matches:
        # First, extract all bold bullet descriptions
        all_traditions = {}
        # Pattern handles both "abilities allow" (Talent) and "is the element of" (Elementalist)
        bold_bullet_pattern = r'[-−]\s+\*\*([^*]+)\*\*\s+(?:abilities?\s+|is the element of\s+)(.+?)(?=\n\s*[-−]|\n\n|\Z)'
        for bullet_match in re.finditer(bold_bullet_pattern, subclass_text, re.DOTALL):
            tradition_name = bullet_match.group(1).strip()
            tradition_desc = bullet_match.group(2).strip()
            # Clean up description
            tradition_desc = re.sub(r'\s+', ' ', tradition_desc)
            all_traditions[tradition_name.lower()] = {
                'name': tradition_name,
                'description': tradition_desc
            }
        
        # Then find which ones are actually selectable
        # Pattern handles both "talent tradition" and "elemental specialization"
        sentence_pattern = r'You choose (?:a|an) (?:talent tradition|elemental specialization) from the following options:\s*([^.]+)\.'
        sentence_match = re.search(sentence_pattern, subclass_text)
        if sentence_match:
            options_text = sentence_match.group(1)
            # Parse out the tradition names (e.g., "chronopathy, telekinesis, or telepathy")
            # Split by comma and 'or', clean up
            tradition_names = re.split(r',\s*(?:or\s*)?', options_text)
            for tradition_name in tradition_names:
                tradition_name = tradition_name.strip()
                if tradition_name:
                    tradition_key = tradition_name.lower()
                    # Get description from the bold bullets, or use default
                    if tradition_key in all_traditions:
                        tradition_info = all_traditions[tradition_key]
                        options.append({
                            'id': tradition_key.replace(' ', '-'),
                            'name': tradition_info['name'],
                            'description': tradition_info['description'],
                            'skill_granted': None
                        })
                    else:
                        # Fallback if not found
                        options.append({
                            'id': tradition_key.replace(' ', '-'),
                            'name': tradition_name.title(),
                            'description': f'{tradition_name.title()} tradition abilities and features.',
                            'skill_granted': None
                        })
    
    for opt_match in matches:
        option_name = opt_match.group(1).strip()
        option_desc_raw = opt_match.group(2).strip()
        
        # Only take the first paragraph - descriptions are always one paragraph
        option_desc = option_desc_raw.split('\n\n')[0].strip()
        
        # Check for specific skill grant pattern
        specific_skill_match = re.search(r'You (?:have|gain)(?: the)? ([A-Z][a-z]+(?: [A-Z][a-z]+)*) skill', option_desc)
        
        # Check for skill group choice pattern - handle both "from the X skill group" and "from the X group"
        skill_choice_match = re.search(r'You gain (?:one|a) skill from the (\w+)(?: skill)? group', option_desc)
        
        skill_granted = None
        if specific_skill_match:
            # Specific skill granted
            skill_granted = specific_skill_match.group(1)
        elif skill_choice_match:
            # Skill choice from a group
            skill_granted = {
                "type": "choice",
                "count": 1,
                "from": {
                    "type": "group",
                    "value": skill_choice_match.group(1)
                }
            }
        
        # Clean up description - keep skill information intact
        option_desc = strip_markdown_links(option_desc)
        
        options.append({
            'id': option_name.lower().replace(' ', '-').replace("'", ''),
            'name': option_name,
            'description': option_desc.strip(),
            'skill_granted': skill_granted
        })
    
    # Special handling for Conduit (2 domains)
    selection_count = 2 if class_name == 'Conduit' else 1
    
    return {
        'type': subclass_type,
        'name': subclass_name,
        'description': strip_markdown_links(subclass_text.split('\n')[0]),
        'options': options,
        'selection_count': selection_count
    }

def parse_domain_features(content, class_name):
    """Parse domain features tables for Censor and Conduit classes."""
    if class_name not in ['Censor', 'Conduit']:
        return None
    
    domain_features = {}
    
    # Parse 1st-level domain features table
    level1_pattern = r'###### 1st-Level .+ Domain Features Table\s*\n\s*\|[^\n]+\|[^\n]+\|[^\n]+\|\s*\n\s*\|[:\-\s|]+\|\s*\n((?:\s*\|[^\n]+\|[^\n]+\|[^\n]+\|\s*\n)+)'
    level1_match = re.search(level1_pattern, content, re.MULTILINE)
    
    if level1_match:
        table_content = level1_match.group(1)
        features_1st = []
        
        # Parse each row
        for line in table_content.strip().split('\n'):
            if '|' in line:
                cells = [cell.strip() for cell in line.split('|')[1:-1]]
                if len(cells) >= 3:
                    domain = cells[0]
                    feature = cells[1]
                    skill_group = cells[2] if len(cells) > 2 else None
                    
                    feature_data = {
                        'domain': domain,
                        'feature': feature
                    }
                    if skill_group:
                        feature_data['skill_group'] = skill_group
                    
                    features_1st.append(feature_data)
        
        if features_1st:
            domain_features['1st_level'] = features_1st
    
    # Parse 4th-level domain features table
    level4_pattern = r'###### 4th-Level .+ Domain Features Table\s*\n\s*\|[^\n]+\|[^\n]+\|\s*\n\s*\|[:\-\s|]+\|\s*\n((?:\s*\|[^\n]+\|[^\n]+\|\s*\n)+)'
    level4_match = re.search(level4_pattern, content, re.MULTILINE)
    
    if level4_match:
        table_content = level4_match.group(1)
        features_4th = []
        
        # Parse each row
        for line in table_content.strip().split('\n'):
            if '|' in line:
                cells = [cell.strip() for cell in line.split('|')[1:-1]]
                if len(cells) >= 2:
                    domain = cells[0]
                    feature = cells[1]
                    
                    features_4th.append({
                        'domain': domain,
                        'feature': feature
                    })
        
        if features_4th:
            domain_features['4th_level'] = features_4th
    
    # Parse 7th-level domain features table
    level7_pattern = r'###### 7th-Level .+ Domain Features Table\s*\n\s*\|[^\n]+\|[^\n]+\|\s*\n\s*\|[:\-\s|]+\|\s*\n((?:\s*\|[^\n]+\|[^\n]+\|\s*\n)+)'
    level7_match = re.search(level7_pattern, content, re.MULTILINE)
    
    if level7_match:
        table_content = level7_match.group(1)
        features_7th = []
        
        # Parse each row
        for line in table_content.strip().split('\n'):
            if '|' in line:
                cells = [cell.strip() for cell in line.split('|')[1:-1]]
                if len(cells) >= 2:
                    domain = cells[0]
                    feature = cells[1]
                    
                    features_7th.append({
                        'domain': domain,
                        'feature': feature
                    })
        
        if features_7th:
            domain_features['7th_level'] = features_7th
    
    return domain_features if domain_features else None

def parse_elemental_specialization_features_table(content, class_name):
    """Parse the 1st-Level Elemental Specialization Features Table for Elementalist class."""
    if class_name != 'Elementalist':
        return None
    
    # Find the 1st-Level Elemental Specialization Features Table
    table_pattern = r'###### 1st-Level Elemental Specialization Features Table\s*\n\s*\|[^\n]+\|[^\n]+\|\s*\n\s*\|[:\-\s|]+\|\s*\n((?:\s*\|[^\n]+\|[^\n]+\|\s*\n)+)'
    table_match = re.search(table_pattern, content, re.MULTILINE)
    
    if not table_match:
        return None
    
    table_content = table_match.group(1)
    specialization_features = {}
    
    # Parse each row
    for line in table_content.strip().split('\n'):
        if '|' in line:
            cells = [cell.strip() for cell in line.split('|')[1:-1]]
            if len(cells) >= 2:
                specialization = cells[0].lower()
                feature = cells[1]
                
                # Convert feature name to id
                feature_id = ability_name_to_id(feature)
                
                specialization_features[specialization] = [feature_id]
    
    return specialization_features if specialization_features else None

def parse_aspect_features_table(content, class_name):
    """Parse the 1st-Level Aspect Features Table for Fury class."""
    if class_name != 'Fury':
        return None
    
    # Find the 1st-Level Aspect Features Table
    table_pattern = r'###### 1st-Level Aspect Features Table\s*\n\s*\|[^\n]+\|[^\n]+\|\s*\n\s*\|[:\-\s|]+\|\s*\n((?:\s*\|[^\n]+\|[^\n]+\|\s*\n)+)'
    table_match = re.search(table_pattern, content, re.MULTILINE)
    
    if not table_match:
        return None
    
    table_content = table_match.group(1)
    aspect_features = {}
    
    # Parse each row
    for line in table_content.strip().split('\n'):
        if '|' in line:
            cells = [cell.strip() for cell in line.split('|')[1:-1]]
            if len(cells) >= 2:
                aspect = cells[0].lower()
                features_str = cells[1]
                
                # Split features by comma and clean up
                features = [f.strip() for f in features_str.split(',')]
                
                # Convert feature names to ids
                feature_ids = [ability_name_to_id(feature) for feature in features]
                
                aspect_features[aspect] = feature_ids
    
    return aspect_features if aspect_features else None

def parse_domain_piety_effects(content, class_name):
    """Parse domain piety and effects for Conduit class."""
    if class_name != 'Conduit':
        return None
    
    domain_piety_effects = {}
    
    # Find the Domain Piety and Effects section
    section_pattern = r'##### Domain Piety and Effects\s*\n(.*?)(?=\n\s*#### [123456789]|\n\s*#### 1[0-9]|\Z)'
    section_match = re.search(section_pattern, content, re.DOTALL)
    
    if not section_match:
        return None
    
    section_content = section_match.group(1)
    
    # Parse each domain's piety and effect
    domain_pattern = r'###### (\w+) Domain Piety and Effect\s*\n\s*- \*\*Piety:\*\*\s*(.+?)\s*\n\s*- \*\*Prayer Effect:\*\*\s*(.+?)(?=\n\s*######|\n\s*####|\Z)'
    
    for match in re.finditer(domain_pattern, section_content, re.DOTALL):
        domain_name = match.group(1)
        piety_trigger = match.group(2).strip()
        prayer_effect = match.group(3).strip()
        
        domain_piety_effects[domain_name] = {
            'piety_trigger': piety_trigger,
            'prayer_effect': prayer_effect
        }
    
    return domain_piety_effects if domain_piety_effects else None

def parse_heroic_resource(content, class_name):
    """Parse heroic resource information."""
    # Resource names by class
    resource_names = {
        'Censor': 'wrath',
        'Conduit': 'piety',
        'Elementalist': 'essence',
        'Fury': 'ferocity',
        'Null': 'discipline',
        'Shadow': 'insight',
        'Tactician': 'focus',
        'Talent': 'clarity',
        'Troubadour': 'drama'
    }
    
    resource_name = resource_names.get(class_name, 'resource')
    
    # Find the resource section - look for the heading (some classes have "X and Y" headings)
    pattern = rf'#### {resource_name.title()}[^#\n]*\n(.+?)(?=^###|\Z)'
    match = re.search(pattern, content, re.DOTALL | re.MULTILINE)
    if not match:
        return None
    
    resource_text = match.group(1)
    
    # Extract the introductory description (text before the first ##### heading)
    description = None
    description_match = re.search(r'^(.+?)(?=^#####|\Z)', resource_text, re.DOTALL | re.MULTILINE)
    if description_match:
        desc_text = description_match.group(1).strip()
        # Clean up: remove blockquotes, extra whitespace, and markdown formatting
        desc_text = re.sub(r'^>\s*', '', desc_text, flags=re.MULTILINE)
        desc_text = re.sub(r'\n\s*\n', ' ', desc_text)
        desc_text = strip_markdown_links(desc_text)
        # Only keep the first paragraph if there are multiple
        first_para = desc_text.split('\n\n')[0] if '\n\n' in desc_text else desc_text
        if first_para and len(first_para) > 10:  # Make sure it's substantive
            description = first_para.strip()
    
    # Parse combat section - look directly for it in full content
    combat_pattern = rf'##### {resource_name.title()} in Combat\s*\n(.+?)(?=^#####|\Z)'
    combat_match = re.search(combat_pattern, content, re.DOTALL | re.MULTILINE | re.IGNORECASE)
    combat = {}
    if combat_match:
        combat_text = combat_match.group(1)
        
        # Starting amount
        if 'Victories' in combat_text or 'victories' in combat_text:
            combat['starting'] = 'Victories'
        
        # Per turn - look for "at the start of each of your turns"
        per_turn_match = re.search(r'start of each of your turns[^.]+?you gain (\d+d\d+|\d+) ' + resource_name, combat_text, re.IGNORECASE)
        if per_turn_match:
            combat['per_turn'] = per_turn_match.group(1)
        
        # Triggers - look for "Additionally" or "first time" patterns
        triggers = []
        # Split by sentences to avoid duplicate matches
        sentences = re.split(r'(?<=[.!?])\s+', combat_text)
        for sentence in sentences:
            if 'you gain' in sentence.lower() and resource_name in sentence.lower():
                # Extract the amount
                amount_match = re.search(r'you gain (\d+d?\d*|\d+) ' + resource_name, sentence, re.IGNORECASE)
                if amount_match:
                    amount = amount_match.group(1)
                    # Clean up the condition
                    condition = re.sub(r',?\s*you gain.*', '', sentence, flags=re.IGNORECASE).strip()
                    if condition and 'start of' not in condition.lower():  # Skip per-turn entries
                        triggers.append({
                            'condition': strip_markdown_links(condition.strip()),
                            'amount': amount
                        })
        
        if triggers:
            combat['triggers'] = triggers
        
        # Special mechanics (like Talent's strain)
        special = []
        if 'strain' in combat_text.lower() or 'negative' in combat_text.lower():
            special.append('Can spend into negative (strain mechanics)')
        if 'pray' in combat_text.lower() and class_name == 'Conduit':
            special.append('Prayer mechanics for additional piety')
        if special:
            combat['special_mechanics'] = special
    
    # Parse outside combat section - look directly for it in full content
    outside_pattern = rf'##### {resource_name.title()} Outside of Combat\s*\n(.+?)(?=^####|\Z)'
    outside_combat_match = re.search(outside_pattern, content, re.DOTALL | re.MULTILINE | re.IGNORECASE)
    outside_combat = {}
    if outside_combat_match:
        outside_text = outside_combat_match.group(1)
        outside_combat['usage_rule'] = 'Can use abilities without spending resource, but can\'t use same ability again until earning Victories or finishing respite'
        outside_combat['respite_reset'] = True
    
    # Return None if we couldn't find any resource information
    if not combat and not outside_combat:
        return {
            'name': resource_name,
            'description': description,
            'combat': {},
            'outside_combat': {},
            'related_features': {
                'in_combat': f'{resource_name.title()} in Combat',
                'outside_combat': f'{resource_name.title()} Outside of Combat'
            }
        }
    
    return {
        'name': resource_name,
        'description': description,
        'combat': combat if combat else {},
        'outside_combat': outside_combat if outside_combat else {},
        'related_features': {
            'in_combat': f'{resource_name.title()} in Combat',
            'outside_combat': f'{resource_name.title()} Outside of Combat'
        }
    }

def parse_advancement_table(content):
    """Parse the advancement table."""
    # Find table in markdown
    table_match = re.search(r'\| Level \|(.+?)\n\n', content, re.DOTALL)
    if not table_match:
        return []
    
    table_text = table_match.group(0)
    lines = table_text.strip().split('\n')
    
    # Parse header to get column names
    header = lines[0]
    columns = [col.strip() for col in header.split('|')[1:-1]]
    
    # Parse data rows (skip separator line)
    advancement = []
    for line in lines[2:]:
        if not line.strip():
            continue
        cells = [cell.strip() for cell in line.split('|')[1:-1]]
        if len(cells) < 2:
            continue
        
        try:
            level = int(cells[0].replace('st', '').replace('nd', '').replace('rd', '').replace('th', ''))
        except ValueError:
            continue
        
        # Parse features column
        features = []
        if len(cells) > 1:
            features_text = cells[1]
            features = [f.strip() for f in features_text.split(',') if f.strip()]
        
        # Parse abilities column
        abilities = {}
        if len(cells) > 2:
            abilities_text = cells[2]
            # Count "signature" occurrences
            sig_count = abilities_text.lower().count('signature')
            if sig_count > 0:
                abilities['signature'] = sig_count
            
            # Extract costs
            costs = []
            for cost in re.findall(r'\b(\d+)\b', abilities_text):
                costs.append(int(cost))
            if costs:
                abilities['costs'] = sorted(list(set(costs)))
        
        # Parse subclass abilities column (if exists)
        subclass_abilities = {}
        if len(cells) > 3:
            subclass_text = cells[3]
            costs = []
            for cost in re.findall(r'\b(\d+)\b', subclass_text):
                costs.append(int(cost))
            if costs:
                subclass_abilities['costs'] = sorted(list(set(costs)))
        
        advancement.append({
            'level': level,
            'features': features,
            'abilities': abilities,
            'subclass_abilities': subclass_abilities if subclass_abilities else None
        })
    
    return advancement

def ability_name_to_id(name):
    """Convert an ability name to an ID (kebab-case)."""
    # Remove cost indicators like "(3 Wrath)"
    name = re.sub(r'\s*\(\d+\s+\w+\)', '', name)
    # Remove special characters and convert to lowercase
    name = name.strip()
    # Replace spaces and special chars with hyphens
    name = re.sub(r'[^\w\s-]', '', name)
    name = re.sub(r'[-\s]+', '-', name)
    return name.lower()

def parse_ability_pools_from_content(content, class_name):
    """Parse ability listings to build ability pools organized by level, then by cost/subclass."""
    pools_by_level = {}
    
    resource_names = {
        'Censor': 'Wrath',
        'Conduit': 'Piety',
        'Elementalist': 'Essence',
        'Fury': 'Ferocity',
        'Null': 'Discipline',
        'Shadow': 'Insight',
        'Tactician': 'Focus',
        'Talent': 'Clarity',
        'Troubadour': 'Drama'
    }
    resource_name = resource_names.get(class_name, 'Resource')
    
    # Find all level sections
    level_sections = list(re.finditer(r'###\s+(\d+)(?:st|nd|rd|th)-Level Features', content))
    
    for i, level_match in enumerate(level_sections):
        level = int(level_match.group(1))
        section_start = level_match.end()
        
        # Find next level section or end of content
        if i + 1 < len(level_sections):
            section_end = level_sections[i + 1].start()
        else:
            section_end = len(content)
        
        section_content = content[section_start:section_end]
        
        if level not in pools_by_level:
            pools_by_level[level] = {}
        
        # Parse signature abilities (only at level 1)
        if level == 1:
            sig_patterns = [
                r'#{4,5}\s+Signature Abilit(?:y|ies)\s*\n\n(.+?)(?=\n#{2,5} |\Z)',
                r'#{4,5}\s+Kit Signature Abilit(?:y|ies)\s*\n\n(.+?)(?=\n#{2,5} |\Z)'
            ]
            
            for pattern in sig_patterns:
                sig_match = re.search(pattern, section_content, re.DOTALL)
                if sig_match:
                    sig_text = sig_match.group(1)
                    sig_abilities = re.findall(r'######\s+([^\n]+)', sig_text)
                    if sig_abilities:
                        count_available = 1
                        choose_match = re.search(r'Choose (\w+) signature', sig_text, re.IGNORECASE)
                        if choose_match:
                            count_word = choose_match.group(1).lower()
                            count_map = {'one': 1, 'two': 2, 'three': 3}
                            count_available = count_map.get(count_word, 1)
                        
                        ability_ids = [ability_name_to_id(name) for name in sig_abilities]
                        pools_by_level[level]['signature_abilities'] = {
                            'cost': 0,
                            'count_available': count_available,
                            'ability_count': len(sig_abilities),
                            'ability_ids': ability_ids
                        }
                    break
        
        # Parse general heroic abilities by cost
        for cost in [3, 5, 7, 9, 11]:
            patterns = [
                rf'#{{4,6}}\s+{cost}-{resource_name} Abilit(?:y|ies)\s*\n',
                rf'#{{4,6}}\s+{cost}-{resource_name.lower()} Abilit(?:y|ies)\s*\n'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, section_content, re.IGNORECASE)
                if match:
                    start_pos = match.end()
                    # Look for next major heading (##-#####) OR another ability cost heading (######)
                    # Match ###### only if it's followed by a cost indicator like "5-Essence Ability"
                    next_heading = re.search(r'\n(?:#{2,5}\s+|#{6}\s+\d+-\w+\s+Abilit)', section_content[start_pos:])
                    if next_heading:
                        ability_text = section_content[start_pos:start_pos + next_heading.start()]
                    else:
                        ability_text = section_content[start_pos:]
                    
                    abilities = re.findall(r'(?:^|\n)>\s*#{6}\s+([^\n]+)', ability_text, re.MULTILINE)
                    if not abilities:
                        abilities = re.findall(r'^\s*#{6}\s+([^\n]+)', ability_text, re.MULTILINE)
                    
                    if abilities:
                        count_available = 1
                        choose_match = re.search(r'Choose (\w+) heroic ability', ability_text, re.IGNORECASE)
                        if choose_match:
                            count_word = choose_match.group(1).lower()
                            count_map = {'one': 1, 'two': 2, 'three': 3}
                            count_available = count_map.get(count_word, 1)
                        
                        ability_ids = [ability_name_to_id(name) for name in abilities]
                        pool_key = f'{cost}_resource_abilities'
                        pools_by_level[level][pool_key] = {
                            'cost': cost,
                            'cost_resource': resource_name.lower(),
                            'count_available': count_available,
                            'ability_count': len(abilities),
                            'ability_ids': ability_ids
                        }
                    break
            
            # Also check for "New X-Essence Ability" sections that introduce additional abilities
            new_patterns = [
                rf'#{{4,6}}\s+New {cost}-{resource_name} Abilit(?:y|ies)\s*\n',
                rf'#{{4,6}}\s+New {cost}-{resource_name.lower()} Abilit(?:y|ies)\s*\n'
            ]
            
            for pattern in new_patterns:
                match = re.search(pattern, section_content, re.IGNORECASE)
                if match:
                    start_pos = match.end()
                    next_heading = re.search(r'\n(?:#{2,5}\s+|#{6}\s+\d+-\w+\s+Abilit)', section_content[start_pos:])
                    if next_heading:
                        ability_text = section_content[start_pos:start_pos + next_heading.start()]
                    else:
                        ability_text = section_content[start_pos:]
                    
                    new_abilities = re.findall(r'(?:^|\n)>\s*#{6}\s+([^\n]+)', ability_text, re.MULTILINE)
                    if not new_abilities:
                        new_abilities = re.findall(r'^\s*#{6}\s+([^\n]+)', ability_text, re.MULTILINE)
                    
                    if new_abilities:
                        new_ability_ids = [ability_name_to_id(name) for name in new_abilities]
                        pool_key = f'{cost}_resource_abilities_new'
                        pools_by_level[level][pool_key] = {
                            'cost': cost,
                            'cost_resource': resource_name.lower(),
                            'count_available': 1,
                            'ability_count': len(new_abilities),
                            'ability_ids': new_ability_ids
                        }
                    break
        
        # Parse subclass-specific abilities (e.g., "2nd-Level Doctrine Ability" or "2nd-Level College Ability")
        subclass_ability_pattern = rf'####\s+{level}(?:st|nd|rd|th)-Level \w+ Abilit(?:y|ies)'
        if re.search(subclass_ability_pattern, section_content, re.IGNORECASE):
            # Find individual subclass sections (e.g., "##### 2nd-Level Insurgent Ability" or "##### 2nd-Level Black Ash Abilities")
            subclass_patterns = list(re.finditer(
                rf'#####\s+{level}(?:st|nd|rd|th)-Level ([^\n]+?) Abilit(?:y|ies)\s*\n',
                section_content,
                re.IGNORECASE
            ))
            
            for j, subclass_match in enumerate(subclass_patterns):
                subclass_name_full = subclass_match.group(1).strip()
                # Convert to ID format (e.g., "Black Ash" -> "black-ash")
                subclass_name = ability_name_to_id(subclass_name_full)
                start_pos = subclass_match.end()
                
                # Find next subclass section or next major heading
                if j + 1 < len(subclass_patterns):
                    subclass_text = section_content[start_pos:subclass_patterns[j + 1].start()]
                else:
                    next_section = re.search(r'\n#{2,4}\s+', section_content[start_pos:])
                    if next_section:
                        subclass_text = section_content[start_pos:start_pos + next_section.start()]
                    else:
                        subclass_text = section_content[start_pos:]
                
                # Extract abilities from this subclass section
                abilities = re.findall(r'(?:^|\n)>\s*#{6}\s+([^\n]+)', subclass_text, re.MULTILINE)
                if not abilities:
                    abilities = re.findall(r'^\s*#{6}\s+([^\n]+)', subclass_text, re.MULTILINE)
                
                if abilities:
                    # Determine cost from ability names (e.g., "Fog of War (5 Focus)")
                    cost = None
                    for ability in abilities:
                        cost_match = re.search(r'\((\d+)\s+' + resource_name, ability, re.IGNORECASE)
                        if cost_match:
                            cost = int(cost_match.group(1))
                            break
                    
                    if cost:
                        count_available = 1
                        choose_match = re.search(r'Choose one', subclass_text, re.IGNORECASE)
                        if choose_match:
                            count_available = 1
                        
                        ability_ids = [ability_name_to_id(name) for name in abilities]
                        pool_key = f'{cost}_resource_abilities_{subclass_name}'
                        pools_by_level[level][pool_key] = {
                            'cost': cost,
                            'cost_resource': resource_name.lower(),
                            'subclass': subclass_name,
                            'count_available': count_available,
                            'ability_count': len(abilities),
                            'ability_ids': ability_ids
                        }
    
    return pools_by_level

def parse_characteristic_increase(content, level):
    """Parse the details of a characteristic increase at a given level."""
    # Find the characteristic increase section for this level
    level_patterns = [
        rf'###\s+{level}(?:st|nd|rd|th)-Level Features.*?####\s+Characteristic Increase\s*\n\n(.+?)(?=\n####|\Z)',
        rf'####\s+Characteristic Increase\s*\n\n(.+?)(?=\n####|\Z)'
    ]
    
    for pattern in level_patterns:
        match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
        if match:
            desc_text = match.group(1).strip()
            # Take only the first paragraph
            first_para = desc_text.split('\n\n')[0].strip()
            
            # Parse into structured format
            details = []
            
            # Pattern 1: "Your X and Y scores each increase to N"
            pattern1 = r'Your (\w+) and (\w+) scores each increase to (\d+)'
            match1 = re.search(pattern1, first_para, re.IGNORECASE)
            if match1:
                char1, char2, score = match1.groups()
                details.append({
                    'characteristic': char1,
                    'score': int(score)
                })
                details.append({
                    'characteristic': char2,
                    'score': int(score)
                })
                return details
            
            # Pattern 2: "Your X score increases to N. Additionally, you can increase one of your characteristic scores by 1, to a maximum of M"
            pattern2 = r'Your (\w+) score increases to (\d+)\. Additionally, you can increase one of your characteristic scores by (\d+), to a maximum of (\d+)'
            match2 = re.search(pattern2, first_para, re.IGNORECASE)
            if match2:
                char, score, increase_by, max_score = match2.groups()
                details.append({
                    'characteristic': char,
                    'score': int(score)
                })
                details.append({
                    'characteristic': 'any',
                    'increase': int(increase_by),
                    'maximum': int(max_score)
                })
                return details
            
            # Pattern 3: "Each of your characteristic scores increases by N, to a maximum of M"
            pattern3 = r'Each of your characteristic scores increases by (\d+), to a maximum of (\d+)'
            match3 = re.search(pattern3, first_para, re.IGNORECASE)
            if match3:
                increase_by, max_score = match3.groups()
                details.append({
                    'characteristic': 'all',
                    'increase': int(increase_by),
                    'maximum': int(max_score)
                })
                return details
            
            # If no pattern matches, return the raw text as fallback
            return first_para
    
    return None

def parse_quick_build_option(content, section_name):
    """Parse Quick Build option from a section of content."""
    # Look for Quick Build pattern in the section
    quick_build_pattern = r'\(\*Quick Build:\s*([^)]+)\)'
    match = re.search(quick_build_pattern, content, re.IGNORECASE)
    if match:
        quick_build_text = match.group(1).strip()
        # Remove leading "* " if present
        if quick_build_text.startswith('* '):
            quick_build_text = quick_build_text[2:]
        
        # Special parsing for Deity and Domains
        if section_name == 'Deity and Domains':
            return parse_deity_domains_quick_build(quick_build_text)
        
        return quick_build_text
    return None


def parse_deity_domains_quick_build(text):
    """Parse deity and domains from quick build text."""
    result = {
        'description': text
    }
    
    # Parse deity
    # Patterns: "Cavall as deity" or "Adûn for deity"
    deity_match = re.search(r'([A-Za-zûû]+)\s+(?:as|for)\s+deity', text, re.IGNORECASE)
    if deity_match:
        result['deity'] = deity_match.group(1).strip()
    
    # Parse domains
    domains = []
    # Pattern: "and War as domain" or "and Life and Protection as domains"
    domain_match = re.search(r'and\s+(.+?)(?:\s+as\s+(?:domain|domains))\.?$', text, re.IGNORECASE)
    if domain_match:
        domain_text = domain_match.group(1).strip()
        # Split by "and" for multiple domains
        if ' and ' in domain_text:
            domains = [d.strip() for d in domain_text.split(' and ')]
        else:
            domains = [domain_text]
    
    if domains:
        result['domains'] = domains
    
    return result

def parse_features_by_level(advancement_table, subclass, ability_pools, class_name, content, aspect_features_table=None, elemental_specialization_features_table=None):
    """Build features_by_level structure from advancement table and other data."""
    features_by_level = {}
    
    for level_data in advancement_table:
        level = level_data['level']
        features_list = []
        
        for feature_name in level_data['features']:
            feature_id = ability_name_to_id(feature_name)
            
            # Determine feature type and build structure
            feature = {
                'feature_id': feature_id,
                'feature_name': feature_name,
                'feature_type': classify_feature_type(feature_name, level, subclass, class_name),
                'description': None  # Would need to parse from content
            }
            
            # Add choice information for features that involve choices
            if 'Perk' in feature_name:
                feature['choice'] = {
                    'required': True,
                    'count': 1,
                    'from': 'all_perks'
                }
            elif 'Skill' in feature_name and 'Increase' not in feature_name:
                feature['choice'] = {
                    'required': True,
                    'count': 1,
                    'from': 'all_skills'
                }
                # Add quick build option from Skills section
                skills_section_pattern = r'\*\*Skills:\*\*(.*?)(?=\n\*\*|\n###|\Z)'
                skills_match = re.search(skills_section_pattern, content, re.DOTALL)
                if skills_match:
                    quick_build = parse_quick_build_option(skills_match.group(1), 'Skills')
                    if quick_build:
                        feature['choice']['quick_build'] = quick_build
            elif 'Characteristic Increase' in feature_name:
                increase_details = parse_characteristic_increase(content, level)
                feature['choice'] = {
                    'required': True,
                    'type': 'characteristic_increase'
                }
                if increase_details:
                    feature['details'] = increase_details
            elif feature_id == 'triggered-action':
                feature['choice'] = {
                    'required': True,
                    'count': 1,
                    'from': 'triggered_actions'
                }
            elif feature['feature_type'] == 'deity_and_domains':
                # Deity and domains feature - reference Gods and Religion chapter
                # Conduit chooses 2 domains, Censor chooses 1 domain
                domain_count = 2 if class_name == 'Conduit' else 1
                domain_desc = 'Choose two domains from your deity\'s portfolio' if domain_count == 2 else 'Choose one domain from your deity\'s portfolio'
                
                feature['choice'] = {
                    'required': True,
                    'deity': {
                        'source': 'gods-and-religion',
                        'description': 'Choose a god or saint, or create your own deity'
                    },
                    'domains': {
                        'count': domain_count,
                        'source': 'deity_portfolio',
                        'description': domain_desc
                    }
                }
                # Add quick build option from Deity and Domains section
                deity_section_pattern = r'#### Deity and Domains\s*\n(.+?)(?=\n####|\Z)'
                deity_match = re.search(deity_section_pattern, content, re.DOTALL)
                if deity_match:
                    quick_build = parse_quick_build_option(deity_match.group(1), 'Deity and Domains')
                    if quick_build:
                        feature['choice']['quick_build'] = quick_build
            elif feature['feature_type'] == 'subclass_choice':
                # Only the initial subclass selection gets the choice options
                feature['choice'] = {
                    'required': True,
                    'count': subclass['selection_count'],
                    'options': subclass['options']
                }
                # Add quick build option from subclass section
                subclass_section_pattern = rf'#### {re.escape(subclass["name"])}\s*\n(.+?)(?=\n####|\n###|\Z)'
                subclass_match = re.search(subclass_section_pattern, content, re.DOTALL)
                if subclass_match:
                    quick_build = parse_quick_build_option(subclass_match.group(1), subclass['name'])
                    if quick_build:
                        feature['choice']['quick_build'] = quick_build
            elif feature['feature_type'] == 'kit_choice':
                # Kit choice feature
                feature['choice'] = {
                    'required': True,
                    'type': 'kit',
                    'description': 'Choose a kit'
                }
                # Add quick build option from Kit section
                kit_section_pattern = r'You can use and gain the benefits of a kit\.(.*?)(?=\n####|\n###|\Z)'
                kit_match = re.search(kit_section_pattern, content, re.DOTALL)
                if kit_match:
                    quick_build = parse_quick_build_option(kit_match.group(1), 'Kit')
                    if quick_build:
                        feature['choice']['quick_build'] = quick_build
            elif feature['feature_type'] == 'prayer_choice':
                # Prayer choice for Conduit - can choose to pray for bonus piety
                feature['choice'] = {
                    'required': False,  # Optional prayer
                    'type': 'prayer',
                    'description': 'Choose to pray at the start of your turn for bonus piety effects'
                }
                # Add quick build option from Prayer section
                prayer_section_pattern = r'#### Prayer\s*\n(.+?)(?=\n####|\Z)'
                prayer_match = re.search(prayer_section_pattern, content, re.DOTALL)
                if prayer_match:
                    quick_build = parse_quick_build_option(prayer_match.group(1), 'Prayer')
                    if quick_build:
                        feature['choice']['quick_build'] = quick_build
            elif feature['feature_type'] == 'ward_choice':
                # Conduit Ward choice - need to determine what the choice is
                # Based on Conduit description, this might be choosing which ward to use
                feature['choice'] = {
                    'required': True,
                    'type': 'ward',
                    'description': 'Choose your conduit ward'
                }
                # Add quick build option from Conduit Ward section
                ward_section_pattern = r'#### Conduit Ward\s*\n(.+?)(?=\n####|\Z)'
                ward_match = re.search(ward_section_pattern, content, re.DOTALL)
                if ward_match:
                    quick_build = parse_quick_build_option(ward_match.group(1), 'Conduit Ward')
                    if quick_build:
                        feature['choice']['quick_build'] = quick_build
            elif 'Abilities' in feature_name or 'Ability' in feature_name:
                # Link to ability pools
                abilities_data = level_data.get('abilities', {})
                subclass_abilities_data = level_data.get('subclass_abilities', {})
                
                feature['choice'] = build_ability_choice(feature_name, abilities_data, subclass_abilities_data, ability_pools, class_name, level)
                
                # Add quick build option for ability choices
                # Try to find the section based on the feature name
                if 'Signature' in feature_name:
                    ability_section_pattern = r'#{4,5}\s+Signature Abilit(?:y|ies)\s*\n(.+?)(?=\n#{2,5} |\Z)'
                else:
                    # For other abilities, look for patterns like "3-Piety Ability"
                    cost_match = re.search(r'(\d+)-', feature_name)
                    if cost_match:
                        cost = cost_match.group(1)
                        resource = feature_name.split('-')[1].split()[0]  # Extract resource name
                        ability_section_pattern = rf'#{4,5}\s+{cost}-{resource} Abilit(?:y|ies)\s*\n(.+?)(?=\n#{2,5} |\Z)'
                    else:
                        ability_section_pattern = None
                
                if ability_section_pattern:
                    ability_match = re.search(ability_section_pattern, content, re.DOTALL)
                    if ability_match:
                        quick_build = parse_quick_build_option(ability_match.group(1), feature_name)
                    if quick_build:
                        feature['choice']['quick_build'] = quick_build
            
            # Add subclass_options for aspect-features in Fury
            if class_name == 'Fury' and feature_name == 'Aspect Features' and aspect_features_table:
                feature['subclass_options'] = aspect_features_table
            
            features_list.append(feature)        # Add Domain Piety and Effects as passive feature at level 1 for Conduit only
        if level == 1 and class_name == 'Conduit':
            domain_piety_feature = {
                'feature_id': 'domain-piety-and-effects',
                'feature_name': 'Domain Piety and Effects',
                'feature_type': 'passive',
                'description': None
            }
            # Insert after the "piety" feature
            piety_index = next((i for i, f in enumerate(features_list) if f['feature_name'] == 'Piety'), len(features_list))
            features_list.insert(piety_index + 1, domain_piety_feature)
        
        # Add Judgment Order Benefit as passive feature at level 1 for Censor only
        if level == 1 and class_name == 'Censor':
            # Parse the Judgment Order Benefit description from the markdown
            judgment_benefit_pattern = r'##### Judgment Order Benefit\s*\n(.+?)(?=\n####|\n###|\Z)'
            judgment_match = re.search(judgment_benefit_pattern, content, re.DOTALL)
            description = None
            if judgment_match:
                description = judgment_match.group(1).strip()
            
            judgment_benefit_feature = {
                'feature_id': 'judgment-order-benefit',
                'feature_name': 'Judgment Order Benefit',
                'feature_type': 'passive',
                'description': description
            }
            # Insert after the "Judgment" feature
            judgment_index = next((i for i, f in enumerate(features_list) if f['feature_name'] == 'Judgment'), len(features_list))
            features_list.insert(judgment_index + 1, judgment_benefit_feature)
        
        features_by_level[str(level)] = features_list
    
    return features_by_level

def classify_feature_type(feature_name, level, subclass, class_name):
    """Classify what type of feature this is."""
    name_lower = feature_name.lower()
    
    if 'perk' in name_lower:
        return 'perk_choice'
    elif 'skill' in name_lower and 'increase' not in name_lower:
        return 'skill_choice'
    elif 'characteristic increase' in name_lower:
        return 'stat_increase'
    elif 'abilities' in name_lower or 'ability' in name_lower:
        return 'ability_choice'
    # Special case: "Deity and Domains" feature for Conduit and Censor
    elif feature_name == 'Deity and Domains':
        return 'deity_and_domains'
    # Only the initial subclass selection is a choice (exact match with subclass name)
    elif level == 1 and feature_name.lower() == subclass['name'].lower():
        return 'subclass_choice'
    elif subclass['type'] in name_lower or 'order' in name_lower or 'domain' in name_lower or 'aspect' in name_lower:
        return 'subclass_feature'
    elif 'kit' in name_lower:
        return 'kit_choice'
    # Special cases for Conduit features
    elif feature_name.lower() == 'prayer':
        return 'prayer_choice'
    elif feature_name.lower() == 'conduit ward':
        return 'ward_choice'
    elif feature_name.lower() == 'triggered action':
        return 'triggered_action'
    else:
        return 'passive'

def build_ability_choice(feature_name, abilities_data, subclass_abilities_data, ability_pools, class_name, level):
    """Build the choice structure for ability selections."""
    choice = {
        'required': True
    }
    
    # Get pools for this level
    level_pools = ability_pools.get(level, {})
    
    # Extract what kind of abilities this is asking for
    if 'Signature' in feature_name:
        pool = level_pools.get('signature_abilities', {})
        choice['count'] = pool.get('count_available', 1)
        choice['from'] = 'signature_abilities'
        choice['options'] = pool.get('ability_ids', [])
    else:
        # Extract cost from feature name (e.g., "7-Wrath Ability" or "New 9-Essence Ability")
        cost_match = re.search(r'(\d+)-', feature_name)
        if cost_match:
            cost = int(cost_match.group(1))
            pool_key = f'{cost}_resource_abilities'
            
            # Check for general pool first at current level
            pool = level_pools.get(pool_key, {})
            
            # If feature name has "New", merge new abilities with earlier level pool
            if 'New' in feature_name:
                # Get new abilities from current level
                new_pool = level_pools.get(f'{cost}_resource_abilities_new', {})
                new_ability_ids = new_pool.get('ability_ids', [])
                
                # Get old abilities from earlier level
                old_ability_ids = []
                if not pool:
                    for search_level in range(level - 1, 0, -1):
                        search_pools = ability_pools.get(search_level, {})
                        if pool_key in search_pools:
                            pool = search_pools[pool_key]
                            old_ability_ids = pool.get('ability_ids', [])
                            break
                else:
                    old_ability_ids = pool.get('ability_ids', [])
                
                # Merge new and old abilities
                if new_ability_ids or old_ability_ids:
                    merged_ids = new_ability_ids + old_ability_ids
                    pool = {
                        'cost': cost,
                        'cost_resource': new_pool.get('cost_resource') or pool.get('cost_resource', ''),
                        'count_available': 1,
                        'ability_count': len(merged_ids),
                        'ability_ids': merged_ids
                    }
            
            # If still not found, might be a subclass-specific ability
            if not pool:
                # Find all pools that match the cost pattern for any subclass
                subclass_pools = {k: v for k, v in level_pools.items() 
                                 if k.startswith(f'{cost}_resource_abilities_')}
                if subclass_pools:
                    # This is a subclass-specific ability choice
                    # Don't set 'from' or 'options' here - it's subclass-dependent
                    choice['count'] = 1
                    choice['cost'] = cost
                    return choice
            
            choice['count'] = pool.get('count_available', 1)
            choice['cost'] = cost
            choice['from'] = pool_key
            choice['options'] = pool.get('ability_ids', [])
    
    return choice

def parse_class(filepath):
    """Parse a single class file."""
    print(f"  Parsing {os.path.basename(filepath)}...")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Parse frontmatter
    frontmatter = parse_frontmatter(content)
    
    # Get class name
    class_name = frontmatter.get('item_name', os.path.basename(filepath).replace('.md', ''))
    
    # Extract description (first paragraph after h2)
    desc_match = re.search(r'## ' + re.escape(class_name) + r'\s*\n\n(.+?)(?=\n\n|\Z)', content, re.DOTALL)
    description = None
    if desc_match:
        description = strip_markdown_links(desc_match.group(1).strip())
    
    # Parse quote
    quote = parse_quote(content)
    
    # Parse basics
    basics = parse_basics(content)
    
    # Parse subclass info
    subclass = parse_subclass_info(content, class_name)
    
    # Parse heroic resource
    heroic_resource = parse_heroic_resource(content, class_name)
    
    # Parse advancement table
    advancement_table = parse_advancement_table(content)
    
    # Parse ability pools
    ability_pools = parse_ability_pools_from_content(content, class_name)
    
    # Parse aspect features table (for Fury)
    aspect_features_table = parse_aspect_features_table(content, class_name)
    
    # Parse elemental specialization features table (for Elementalist)
    elemental_specialization_features_table = parse_elemental_specialization_features_table(content, class_name)
    
    # Parse features by level
    features_by_level = parse_features_by_level(advancement_table, subclass, ability_pools, class_name, content, aspect_features_table, elemental_specialization_features_table)
    
    # Parse domain features (for Censor and Conduit)
    domain_features = parse_domain_features(content, class_name)
    
    # Parse domain piety effects (for Censor and Conduit)
    domain_piety_effects = parse_domain_piety_effects(content, class_name)
    
    # Build the class data
    class_data = {
        'item_id': frontmatter.get('item_id'),
        'item_name': class_name,
        'item_index': frontmatter.get('item_index'),
        'source': frontmatter.get('source'),
        'type': frontmatter.get('type'),
        'description': description,
        'quote': quote,
        'basics': basics,
        'subclass': subclass,
        'domain_features': domain_features,
        'domain_piety_effects': domain_piety_effects,
        'heroic_resource': heroic_resource,
        'advancement_table': advancement_table,
        'ability_pools': ability_pools,
        'features_by_level': features_by_level
    }
    
    return class_data

def main():
    # Paths
    script_dir = Path(__file__).parent.parent
    classes_dir = script_dir / 'Rules' / 'Classes'
    output_dir = script_dir / 'data'
    output_file = output_dir / 'classes.json'
    
    print(f"Parsing classes from {classes_dir}...")
    
    # Get all class files (exclude _Index.md)
    class_files = sorted([
        f for f in classes_dir.glob('*.md')
        if not f.name.startswith('_')
    ])
    
    if not class_files:
        print(f"No class files found in {classes_dir}")
        return
    
    # Parse each class
    classes = []
    for class_file in class_files:
        try:
            class_data = parse_class(class_file)
            classes.append(class_data)
        except Exception as e:
            print(f"Error parsing {class_file.name}: {e}")
            import traceback
            traceback.print_exc()
    
    # Create output directory if needed
    output_dir.mkdir(exist_ok=True)
    
    # Write JSON
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(classes, f, indent=2, ensure_ascii=False)
    
    print(f"\nWriting {len(classes)} classes to {output_file}...")
    print(f"Done! Classes saved to {output_file}")

if __name__ == '__main__':
    main()

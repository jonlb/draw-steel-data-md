#!/usr/bin/env python3
"""
Parse career markdown files from Rules/Careers directory into structured JSON.
"""

import os
import re
import json
import yaml
from pathlib import Path


def parse_frontmatter(content):
    """Extract YAML frontmatter from markdown content."""
    frontmatter_pattern = r'^---\s*\n(.*?)\n---\s*\n'
    match = re.match(frontmatter_pattern, content, re.DOTALL)
    
    if match:
        frontmatter_text = match.group(1)
        try:
            return yaml.safe_load(frontmatter_text), content[match.end():]
        except yaml.YAMLError:
            return {}, content
    return {}, content


def strip_markdown_links(text):
    """Remove markdown link syntax, keeping only the link text."""
    return re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)


def parse_quick_build(text):
    """Extract quick build values from parentheses."""
    match = re.search(r'\(\*Quick Build:\*\s*([^)]+)\)', text)
    if match:
        items = match.group(1).strip()
        # Split by comma and clean up
        return [item.strip().rstrip('.') for item in items.split(',')]
    return None


def parse_skills_section(skills_text):
    """Parse the skills section into given and choice arrays."""
    given = []
    choices = []
    quick_build = parse_quick_build(skills_text)
    
    # Remove quick build from text for parsing
    clean_text = re.sub(r'\s*\(\*Quick Build:\*[^)]+\)', '', skills_text).strip()
    
    # Parse given skills with "or" - e.g., "The Music or Perform skill"
    given_or_pattern = r'[Tt]he\s+([A-Z][A-Za-z\s]+?)\s+or\s+([A-Z][A-Za-z\s]+?)\s+skill'
    or_match = re.search(given_or_pattern, skills_text)
    if or_match:
        skill1 = or_match.group(1).strip()
        skill2 = or_match.group(2).strip()
        given.append({
            "names": [skill1, skill2],
            "type": "or"
        })
        # Remove this from text so we don't parse it again
        clean_text = clean_text[:or_match.start()] + clean_text[or_match.end():]
    
    # Parse regular given skills
    # Look for either "The X skill (from..." or standalone "X (from..."
    
    # First, check if there's "The X skill" pattern - if so, only use that
    the_skill_pattern = r'[Tt]he\s+([A-Z][A-Za-z\s]+?)\s+skill\s+(?:\(|from)'
    the_skill_matches = list(re.finditer(the_skill_pattern, clean_text))
    
    if the_skill_matches:
        # Found "The X skill" pattern, use it
        for match in the_skill_matches:
            skill = match.group(1).strip()
            if not any(skill in g['names'] for g in given):
                given.append({
                    "names": [skill],
                    "type": "standard"
                })
    else:
        # No "The X skill" pattern, look for standalone like "Swim (from..." or "Nature (from..."
        standalone_pattern = r'(?:^|,\s+)([A-Z][A-Za-z\s]+?)\s+\(from\s+the'
        for match in re.finditer(standalone_pattern, clean_text):
            skill = match.group(1).strip()
            if not any(skill in g['names'] for g in given):
                given.append({
                    "names": [skill],
                    "type": "standard"
                })
    
    # Parse choices - look for patterns like "one skill from the X group", "two skills from the Y group", "two more skills from the Y group"
    # Also handle "either X or Y" patterns
    
    # Pattern 1: "either X or Y" - e.g., "two skills from either the crafting group or the exploration group"
    either_pattern = r'(one|two|three|four|\d+)\s+(?:skill|skills)\s+from\s+either\s+the\s+(\w+)\s+group\s+or\s+the\s+(\w+)\s+group'
    
    for match in re.finditer(either_pattern, clean_text, re.IGNORECASE):
        number_str = match.group(1).lower()
        group1 = match.group(2).strip()
        group2 = match.group(3).strip()
        
        # Convert number word to integer
        number_map = {"one": 1, "two": 2, "three": 3, "four": 4}
        number = number_map.get(number_str, int(number_str) if number_str.isdigit() else 1)
        
        choices.append({
            "number": number,
            "group": {
                "names": [group1, group2],
                "type": "or"
            }
        })
    
    # Pattern 2: Standard "X skills from the Y group"
    choice_pattern = r'(one|two|three|four|\d+)\s+(?:more\s+)?(?:skill|skills|other\s+skills?)\s+from\s+the\s+(\w+(?:\s+skill)?)\s+(?:skill\s+)?group'
    
    for match in re.finditer(choice_pattern, clean_text, re.IGNORECASE):
        number_str = match.group(1).lower()
        group = match.group(2).strip()
        
        # Convert number word to integer
        number_map = {"one": 1, "two": 2, "three": 3, "four": 4}
        number = number_map.get(number_str, int(number_str) if number_str.isdigit() else 1)
        
        # Normalize group name (remove " skill" suffix if present)
        group = re.sub(r'\s+skill$', '', group)
        
        choices.append({
            "number": number,
            "group": {
                "names": [group],
                "type": "from"
            }
        })
    
    return given, choices, quick_build


def parse_benefits_section(content):
    """Parse the career benefits section."""
    benefits = {
        "skills": None,
        "languages": None,
        "project_points": None,
        "renown": None,
        "wealth": None,
        "perk": None
    }
    
    # Extract Skills
    skills_match = re.search(r'\*\*Skills:\*\*\s*([^\n]+)', content)
    if skills_match:
        skills_text = skills_match.group(1)
        given, choices, quick_build = parse_skills_section(skills_text)
        
        # Get description without quick build
        description = re.sub(r'\s*\(\*Quick Build:\*[^)]+\)', '', skills_text).strip()
        
        benefits["skills"] = {
            "description": description,
            "given": given if given else None,
            "choice": choices if choices else None,
            "quick_build": quick_build
        }
    
    # Extract Languages
    languages_match = re.search(r'\*\*Languages:\*\*\s*([^\n]+)', content)
    if languages_match:
        lang_text = languages_match.group(1).strip()
        # Extract number from text like "Two languages" or "One language"
        number_map = {"one": 1, "two": 2, "three": 3, "four": 4}
        for word, num in number_map.items():
            if word in lang_text.lower():
                benefits["languages"] = {"count": num}
                break
    
    # Extract Project Points
    project_match = re.search(r'\*\*Project Points:\*\*\s*(\d+)', content)
    if project_match:
        benefits["project_points"] = int(project_match.group(1))
    
    # Extract Renown
    renown_match = re.search(r'\*\*Renown:\*\*\s*([+\-]?\d+)', content)
    if renown_match:
        benefits["renown"] = int(renown_match.group(1))
    
    # Extract Wealth
    wealth_match = re.search(r'\*\*Wealth:\*\*\s*([+\-]?\d+)', content)
    if wealth_match:
        benefits["wealth"] = int(wealth_match.group(1))
    
    # Extract Perk
    perk_match = re.search(r'\*\*Perk:\*\*\s*([^\n]+)', content)
    if perk_match:
        perk_text = perk_match.group(1)
        quick_build = parse_quick_build(perk_text)
        # Remove the quick build part from description
        description = re.sub(r'\s*\(\*Quick Build:\*[^)]+\)', '', perk_text).strip()
        
        # Parse number and type from description like "One intrigue perk" or "Two lore perks"
        number = None
        perk_type = None
        
        # Extract number
        number_match = re.search(r'\b(one|two|three|four|1|2|3|4)\b', description.lower())
        if number_match:
            number_map = {"one": 1, "two": 2, "three": 3, "four": 4}
            num_str = number_match.group(1).lower()
            number = number_map.get(num_str, int(num_str) if num_str.isdigit() else None)
        
        # Extract type (word before "perk" or "perks")
        type_match = re.search(r'\b(\w+)\s+perks?', description.lower())
        if type_match:
            perk_type = type_match.group(1)
        
        benefits["perk"] = {
            "number": number,
            "type": perk_type,
            "description": description,
            "quick_build": quick_build[0] if quick_build else None
        }
    
    return benefits


def parse_inciting_incidents(content):
    """Parse the inciting incidents table."""
    incidents = []
    
    # Find the table section
    table_pattern = r'\| d6\s+\| Inciting Incident.*?\n\| ---.*?\n((?:\| \d+\s+\|.*?\n)+)'
    table_match = re.search(table_pattern, content, re.DOTALL)
    
    if not table_match:
        return incidents
    
    table_content = table_match.group(1)
    
    # Parse each row
    row_pattern = r'\|\s*(\d+)\s+\|\s*\*\*([^:*]+):\*\*\s*(.*?)\s*\|'
    
    for match in re.finditer(row_pattern, table_content, re.DOTALL):
        roll = match.group(1).strip()
        title = match.group(2).strip()
        description = match.group(3).strip()
        description = strip_markdown_links(description)
        
        incidents.append({
            "roll": roll,
            "title": title,
            "description": description
        })
    
    return incidents


def parse_career_content(content):
    """Parse the main content section of a career."""
    # Split at "You gain the following career benefits:"
    parts = re.split(r'You gain the following career benefits:', content, maxsplit=1)
    
    if len(parts) != 2:
        return "", {}, []
    
    description = parts[0].strip()
    description = strip_markdown_links(description)
    
    benefits_and_incidents = parts[1]
    
    # Parse benefits
    benefits = parse_benefits_section(benefits_and_incidents)
    
    # Parse inciting incidents
    incidents = parse_inciting_incidents(benefits_and_incidents)
    
    return description, benefits, incidents


def parse_career_file(file_path):
    """Parse a single career markdown file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Parse frontmatter
    frontmatter, remaining_content = parse_frontmatter(content)
    
    # Remove the heading (#### Career Name)
    remaining_content = re.sub(r'^#{1,4}\s+[^\n]+\n+', '', remaining_content, count=1)
    
    # Parse content
    description, benefits, incidents = parse_career_content(remaining_content)
    
    # Build career object
    career = {
        "item_id": frontmatter.get("item_id", ""),
        "item_name": frontmatter.get("item_name", ""),
        "item_index": frontmatter.get("item_index", ""),
        "source": frontmatter.get("source", ""),
        "description": description,
        "benefits": benefits,
        "inciting_incidents": incidents
    }
    
    return career


def main():
    # Get the project root directory
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    careers_dir = project_root / "Rules" / "Careers"
    output_file = project_root / "data" / "careers.json"
    
    print(f"Parsing careers from {careers_dir}...")
    
    careers = []
    
    # Process each markdown file in the directory
    for file_path in sorted(careers_dir.glob("*.md")):
        # Skip _Index.md files
        if file_path.name.startswith("_"):
            continue
        
        print(f"Parsing {file_path.name}...")
        career = parse_career_file(file_path)
        careers.append(career)
    
    # Write to JSON file
    print(f"Writing {len(careers)} careers to {output_file}...")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(careers, f, indent=2, ensure_ascii=False)
    
    print(f"Done! Careers saved to {output_file}")


if __name__ == "__main__":
    main()

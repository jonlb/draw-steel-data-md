#!/usr/bin/env python3
"""
Parse language-related tables from Background.md chapter.
Extracts: Typical Ancestry Cultures, Archetypical Cultures, 
Languages by Ancestry, and Dead Languages tables.
"""

import json
import os
import re
from pathlib import Path


def slugify(text):
    """Convert text to a slug format."""
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text.strip('-')


def parse_markdown_table(table_text):
    """Parse a markdown table into a list of dictionaries."""
    lines = [line.strip() for line in table_text.strip().split('\n') if line.strip()]
    
    if len(lines) < 3:  # Need at least header, separator, and one data row
        return []
    
    # Parse header - split on | and keep all cells including empty ones
    header_line = lines[0]
    header_cells = header_line.split('|')
    # Remove leading/trailing empty cells
    if header_cells[0].strip() == '':
        header_cells = header_cells[1:]
    if header_cells and header_cells[-1].strip() == '':
        header_cells = header_cells[:-1]
    headers = [h.strip() for h in header_cells]
    
    # Skip separator line (lines[1])
    
    # Parse data rows
    rows = []
    for line in lines[2:]:
        if not line.strip() or '---' in line:
            continue
        
        # Split cells, handling leading/trailing pipes
        cells = line.split('|')
        if cells[0].strip() == '':
            cells = cells[1:]
        if cells and cells[-1].strip() == '':
            cells = cells[:-1]
        cells = [c.strip() for c in cells]
        
        # Match cells to headers
        row_dict = {}
        for i, header in enumerate(headers):
            if i < len(cells):
                # Convert header to snake_case
                key = slugify(header).replace('-', '_')
                row_dict[key] = cells[i]
            else:
                # Missing cell
                key = slugify(header).replace('-', '_')
                row_dict[key] = ''
        
        rows.append(row_dict)
    
    return rows


def extract_table_by_name(content, table_name):
    """Extract a specific table from markdown content by its heading."""
    # Pattern to match the table heading and capture the table
    # Use a simple approach: find the heading, then capture the table that follows
    pattern = r'#{1,6}\s+' + re.escape(table_name) + r'.*?\n\n((?:\|[^\n]+\n)+)'
    
    match = re.search(pattern, content, re.DOTALL)
    if match:
        return match.group(1)
    return None


def parse_typical_ancestry_cultures(content):
    """Parse the Typical Ancestry Cultures Table."""
    table_text = extract_table_by_name(content, "Typical Ancestry Cultures Table")
    if not table_text:
        return None
    
    rows = parse_markdown_table(table_text)
    
    return {
        "table_id": "typical-ancestry-cultures",
        "table_name": "Typical Ancestry Cultures Table",
        "description": "Archetypical culture aspects for heroes who grew up surrounded mostly by other members of their ancestry.",
        "type": "culture_reference",
        "entries": rows
    }


def parse_archetypical_cultures(content):
    """Parse the Archetypical Cultures Table."""
    table_text = extract_table_by_name(content, "Archetypical Cultures Table")
    if not table_text:
        return None
    
    rows = parse_markdown_table(table_text)
    
    return {
        "table_id": "archetypical-cultures",
        "table_name": "Archetypical Cultures Table",
        "description": "Culture aspects based on cultural archetypes such as noble houses or pirate crews.",
        "type": "culture_reference",
        "entries": rows
    }


def parse_vaslorian_languages(content):
    """Parse the Vaslorian Human Languages Table."""
    table_text = extract_table_by_name(content, "Vaslorian Human Languages Table")
    if not table_text:
        return None
    
    rows = parse_markdown_table(table_text)
    
    return {
        "table_id": "vaslorian-human-languages",
        "table_name": "Vaslorian Human Languages Table",
        "description": "Dominant languages in Vaslorian human-centric territories by region.",
        "type": "language_reference",
        "entries": rows
    }


def parse_languages_by_ancestry(content):
    """Parse the Languages by Ancestry Table."""
    table_text = extract_table_by_name(content, "Languages by Ancestry Table")
    if not table_text:
        return None
    
    rows = parse_markdown_table(table_text)
    
    # Process each row to handle the notes field properly
    for row in rows:
        # Clean up any line breaks in notes
        if 'notes' in row:
            row['notes'] = row['notes'].replace('<br/>', ' ').replace('  ', ' ').strip()
    
    return {
        "table_id": "languages-by-ancestry",
        "table_name": "Languages by Ancestry Table",
        "description": "The most common languages actively spoken and signed by significant populations of people in Orden.",
        "type": "language_reference",
        "entries": rows
    }


def parse_dead_languages(content):
    """Parse the Dead Languages Table."""
    table_text = extract_table_by_name(content, "Dead Languages Table")
    if not table_text:
        return None
    
    rows = parse_markdown_table(table_text)
    
    # Process each row to handle the notes field properly
    for row in rows:
        # Clean up any line breaks in common topics
        if 'common_topics' in row:
            row['common_topics'] = row['common_topics'].replace('<br/>', ' ').replace('  ', ' ').strip()
    
    return {
        "table_id": "dead-languages",
        "table_name": "Dead Languages Table",
        "description": "Ancient languages of Orden that are no longer actively spoken, and the modern languages related to them.",
        "type": "language_reference",
        "entries": rows
    }


def main():
    # Paths
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    background_file = project_root / 'Rules' / 'Chapters' / 'Background.md'
    output_file = project_root / 'data' / 'languages.json'
    
    print(f"Parsing language tables from {background_file}...")
    
    # Read the Background.md file
    with open(background_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Parse all tables
    tables = []
    
    print("  Parsing Typical Ancestry Cultures Table...")
    typical_ancestry = parse_typical_ancestry_cultures(content)
    if typical_ancestry:
        tables.append(typical_ancestry)
    
    print("  Parsing Archetypical Cultures Table...")
    archetypical = parse_archetypical_cultures(content)
    if archetypical:
        tables.append(archetypical)
    
    print("  Parsing Vaslorian Human Languages Table...")
    vaslorian = parse_vaslorian_languages(content)
    if vaslorian:
        tables.append(vaslorian)
    
    print("  Parsing Languages by Ancestry Table...")
    languages_by_ancestry = parse_languages_by_ancestry(content)
    if languages_by_ancestry:
        tables.append(languages_by_ancestry)
    
    print("  Parsing Dead Languages Table...")
    dead_languages = parse_dead_languages(content)
    if dead_languages:
        tables.append(dead_languages)
    
    # Create output directory if it doesn't exist
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Write to JSON file
    print(f"\nWriting {len(tables)} tables to {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(tables, f, indent=2, ensure_ascii=False)
    
    print(f"Done! Language tables saved to {output_file}")
    
    # Print summary
    print(f"\nTables parsed:")
    for table in tables:
        print(f"  {table['table_name']}: {len(table['entries'])} entries")


if __name__ == "__main__":
    main()

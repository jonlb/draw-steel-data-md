#!/usr/bin/env python3
"""
Parse Draw Steel deities and saints from Gods and Religion chapter.

Extracts deities and saints with their domains from the markdown file
and generates a structured JSON file.
"""

import json
import os
import re
from pathlib import Path
from typing import Dict, List, Any


def slugify(text: str) -> str:
    """Convert text to a slug format."""
    slug = text.lower()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[-\s]+', '-', slug)
    return slug.strip('-')


def parse_markdown_table(table_text: str) -> List[Dict[str, str]]:
    """Parse a markdown table into a list of dictionaries."""
    lines = [line.strip() for line in table_text.strip().split('\n') if line.strip()]
    
    if len(lines) < 2:
        return []
    
    # Parse header
    header_line = lines[0]
    headers = [cell.strip() for cell in header_line.split('|')]
    headers = [h for h in headers if h]  # Remove empty
    
    # Skip separator line (lines[1])
    
    # Parse data rows
    entries = []
    for line in lines[2:]:  # Skip header and separator
        cells = [cell.strip() for cell in line.split('|')]
        cells = [c for c in cells if c]  # Remove empty
        
        if len(cells) >= len(headers):
            entry = {}
            for i, header in enumerate(headers):
                entry[header.lower()] = cells[i]
            entries.append(entry)
    
    return entries


def extract_table_by_name(content: str, table_name: str) -> str:
    """Extract a specific table from the content by its heading name."""
    # Match the heading followed by table content
    pattern = r'#{1,6}\s+' + re.escape(table_name) + r'.*?\n\n((?:\|[^\n]+\n)+)'
    match = re.search(pattern, content, re.DOTALL)
    
    if match:
        return match.group(1)
    return ""


def parse_deities_table(content: str) -> List[Dict[str, Any]]:
    """Parse the Deities and Domains table."""
    table_text = extract_table_by_name(content, "Deities and Domains Table")
    
    if not table_text:
        print("Warning: Deities and Domains Table not found")
        return []
    
    entries = parse_markdown_table(table_text)
    
    deities = []
    for entry in entries:
        deity_name = entry.get('deity', '').strip()
        domains_text = entry.get('domains', '').strip()
        
        if deity_name and domains_text:
            domains = [d.strip() for d in domains_text.split(',')]
            
            deity = {
                "id": slugify(deity_name),
                "name": deity_name,
                "type": "deity",
                "domains": domains
            }
            deities.append(deity)
    
    return deities


def parse_saints_table(content: str) -> List[Dict[str, Any]]:
    """Parse the Saints and Domains table."""
    table_text = extract_table_by_name(content, "Saints and Domains Table")
    
    if not table_text:
        print("Warning: Saints and Domains Table not found")
        return []
    
    entries = parse_markdown_table(table_text)
    
    saints = []
    for entry in entries:
        saint_name = entry.get('saint', '').strip()
        domains_text = entry.get('domains', '').strip()
        
        if saint_name and domains_text:
            domains = [d.strip() for d in domains_text.split(',')]
            
            saint = {
                "id": slugify(saint_name),
                "name": saint_name,
                "type": "saint",
                "domains": domains
            }
            saints.append(saint)
    
    return saints


def extract_deity_details(content: str) -> Dict[str, Any]:
    """Extract additional details about deities from their section headings."""
    deity_details = {}
    
    # Match deity sections: ### DeityName followed by **Domains:**
    deity_pattern = r'### ([^\n]+)\n\n\*\*Domains:\*\*\s+([^\n]+)'
    
    for match in re.finditer(deity_pattern, content):
        deity_name = match.group(1).strip()
        domains_text = match.group(2).strip()
        
        deity_id = slugify(deity_name)
        domains = [d.strip() for d in domains_text.split(',')]
        
        # Find the description (text between domains line and next heading or hero section)
        start_pos = match.end()
        # Look for next ### or #### heading
        next_section = re.search(r'\n#{3,4}\s+', content[start_pos:])
        if next_section:
            end_pos = start_pos + next_section.start()
        else:
            end_pos = len(content)
        
        description = content[start_pos:end_pos].strip()
        # Clean up the description
        description = re.sub(r'\n{3,}', '\n\n', description)
        
        deity_details[deity_id] = {
            "description": description,
            "domains": domains
        }
    
    return deity_details


def extract_saint_details(content: str) -> Dict[str, Any]:
    """Extract additional details about saints from their section headings."""
    saint_details = {}
    
    # Match saint sections: ##### SaintName followed by **Domains:**
    saint_pattern = r'##### ([^\n]+)\n\n\*\*Domains:\*\*\s+([^\n]+)'
    
    for match in re.finditer(saint_pattern, content):
        saint_name = match.group(1).strip()
        domains_text = match.group(2).strip()
        
        saint_id = slugify(saint_name)
        domains = [d.strip() for d in domains_text.split(',')]
        
        # Find the description (text between domains line and next heading)
        start_pos = match.end()
        # Look for next ##### heading or #### heading
        next_section = re.search(r'\n#{4,5}\s+', content[start_pos:])
        if next_section:
            end_pos = start_pos + next_section.start()
        else:
            # Look for ### heading (next deity)
            next_deity = re.search(r'\n###\s+', content[start_pos:])
            if next_deity:
                end_pos = start_pos + next_deity.start()
            else:
                end_pos = len(content)
        
        description = content[start_pos:end_pos].strip()
        # Clean up the description
        description = re.sub(r'\n{3,}', '\n\n', description)
        
        saint_details[saint_id] = {
            "description": description,
            "domains": domains
        }
    
    return saint_details


def determine_patron_ancestry(content: str, deity_id: str) -> str:
    """Determine which ancestry a deity is patron of."""
    ancestry_map = {
        'val': 'elf',
        'ord': 'dwarf',
        'kul': 'orc',
        'aan': 'human'
    }
    
    if deity_id in ancestry_map:
        return ancestry_map[deity_id]
    
    # Check in the content
    deity_sections = {
        'val': 'patron of the elves',
        'ord': 'patron of the dwarves',
        'kul': 'Father of Flames',  # Creates orcs
        'aan': 'patron of the humans'
    }
    
    for deity, pattern in deity_sections.items():
        if deity == deity_id and pattern in content.lower():
            return ancestry_map.get(deity, '')
    
    return ''


def main():
    """Main function to parse deities and generate JSON."""
    # Get the repository root
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    gods_file = repo_root / 'Rules' / 'Chapters' / 'Gods and Religion.md'
    output_dir = repo_root / 'data'
    
    # Ensure output directory exists
    output_dir.mkdir(exist_ok=True)
    
    print(f"Parsing deities and saints from {gods_file}...")
    
    # Read the file
    try:
        with open(gods_file, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading file: {e}")
        return
    
    # Parse tables
    deities = parse_deities_table(content)
    saints = parse_saints_table(content)
    
    # Extract additional details
    deity_details = extract_deity_details(content)
    saint_details = extract_saint_details(content)
    
    # Merge details with table data
    for deity in deities:
        if deity['id'] in deity_details:
            deity['description'] = deity_details[deity['id']]['description']
        
        # Determine patron ancestry
        patron = determine_patron_ancestry(content, deity['id'])
        if patron:
            deity['patron_of'] = patron
    
    for saint in saints:
        if saint['id'] in saint_details:
            saint['description'] = saint_details[saint['id']]['description']
    
    # Combine all entities
    all_entities = deities + saints
    
    print(f"\n✓ Parsed {len(deities)} deities")
    print(f"✓ Parsed {len(saints)} saints")
    
    # Count by domain
    domain_counts = {}
    for entity in all_entities:
        for domain in entity['domains']:
            domain_counts[domain] = domain_counts.get(domain, 0) + 1
    
    print("\nEntities by domain:")
    for domain, count in sorted(domain_counts.items()):
        print(f"  {domain}: {count}")
    
    # Write JSON output
    output_file = output_dir / 'deities.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_entities, f, indent=2, ensure_ascii=False)
    
    print(f"\n✓ Generated {output_file}")
    print(f"\nTotal entities: {len(all_entities)}")


if __name__ == '__main__':
    main()

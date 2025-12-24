#!/usr/bin/env python3
"""
Script to parse "Piety in Combat" section from Conduit.md and create the corresponding feature file.
"""

import re
from pathlib import Path

def parse_piety_in_combat():
    # Path to the Conduit.md file
    conduit_file = Path("Rules/Classes/Conduit.md")
    
    # Read the content
    with open(conduit_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Pattern to find the "Piety in Combat" section
    # Start after ##### Piety in Combat
    # End before ###### Conduit Advancement Table
    start_pattern = r'^##### Piety in Combat$'
    end_pattern = r'^###### Conduit Advancement Table$'
    
    # Find the section
    match = re.search(start_pattern + r'\s*(.*?)\s*(?=' + end_pattern + r')', content, re.MULTILINE | re.DOTALL)
    
    if match:
        piety_content = match.group(1).strip()
        
        # Create the output directory if it doesn't exist
        output_dir = Path("Rules/Features/Conduit/1st-Level Features")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Output file
        output_file = output_dir / "Piety in Combat.md"
        
        # Write the content with the header
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("##### Piety in Combat\n\n")
            f.write(piety_content)
        
        print(f"Created feature file: {output_file}")
    else:
        print("Could not find 'Piety in Combat' section in Conduit.md")

if __name__ == "__main__":
    parse_piety_in_combat()
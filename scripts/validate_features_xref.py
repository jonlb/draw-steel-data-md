#!/usr/bin/env python3
"""
Validate cross-references between classes.json and features.json.
"""

import json
from pathlib import Path
from collections import defaultdict

def load_json(file_path):
    """Load JSON file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def main():
    """Validate feature cross-references."""
    repo_root = Path(__file__).parent.parent
    classes_json = load_json(repo_root / 'data' / 'classes.json')
    features_data = load_json(repo_root / 'data' / 'features.json')
    
    # Extract classes array
    classes_data = classes_json.get('classes', classes_json)
    if isinstance(classes_data, dict):
        classes_data = [classes_data]
    
    # Build feature ID index
    feature_index = {}
    for feature in features_data:
        key = (feature['class'], feature['level'], feature['item_id'])
        feature_index[key] = feature
    
    print("Validating feature cross-references between classes.json and features.json...\n")
    
    total_refs = 0
    matched = 0
    missing = []
    
    for class_data in classes_data:
        class_name = class_data.get('item_name', class_data.get('class_name', 'Unknown'))
        features_by_level = class_data.get('features_by_level', {})
        
        for level, feature_list in features_by_level.items():
            for feature_obj in feature_list:
                # Handle both dict and string formats
                if isinstance(feature_obj, dict):
                    feature_id = feature_obj.get('feature_id')
                else:
                    feature_id = feature_obj
                
                if not feature_id:
                    continue
                    
                total_refs += 1
                key = (class_name.lower(), int(level), feature_id)
                
                if key in feature_index:
                    matched += 1
                else:
                    missing.append({
                        'class': class_name,
                        'level': level,
                        'feature_id': feature_id
                    })
    
    print(f"Total feature references in classes.json: {total_refs}")
    print(f"Matched in features.json: {matched}")
    print(f"Match rate: {matched / total_refs * 100:.1f}%")
    
    if missing:
        print(f"\nMissing features ({len(missing)}):")
        for item in missing[:10]:  # Show first 10
            print(f"  {item['class']} level {item['level']}: {item['feature_id']}")
        if len(missing) > 10:
            print(f"  ... and {len(missing) - 10} more")
    else:
        print("\n✓ All feature references validated!")
    
    # Check for features not referenced in classes
    print("\nChecking for unreferenced features...")
    
    referenced_features = set()
    for class_data in classes_data:
        class_name = class_data.get('item_name', class_data.get('class_name', 'Unknown'))
        features_by_level = class_data.get('features_by_level', {})
        for level, feature_list in features_by_level.items():
            for feature_obj in feature_list:
                # Handle both dict and string formats
                if isinstance(feature_obj, dict):
                    feature_id = feature_obj.get('feature_id')
                else:
                    feature_id = feature_obj
                
                if not feature_id:
                    continue
                    
                referenced_features.add((class_name.lower(), int(level), feature_id))
    
    unreferenced = []
    for feature in features_data:
        key = (feature['class'], feature['level'], feature['item_id'])
        if key not in referenced_features:
            unreferenced.append(feature)
    
    if unreferenced:
        print(f"Found {len(unreferenced)} unreferenced features:")
        for feature in unreferenced[:10]:
            print(f"  {feature['class']} level {feature['level']}: {feature['item_id']} ({feature['name']})")
        if len(unreferenced) > 10:
            print(f"  ... and {len(unreferenced) - 10} more")
    else:
        print("✓ All features are referenced in classes.json")

if __name__ == '__main__':
    main()

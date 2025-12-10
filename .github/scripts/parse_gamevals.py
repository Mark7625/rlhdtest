#!/usr/bin/env python3
"""
Parse Java gameval files from RuneLite GitHub repository and generate gamevals.json
"""
import json
import re
from pathlib import Path
from typing import Dict, List

import requests

# Base URL for RuneLite raw files
BASE_URL = (
    "https://raw.githubusercontent.com/runelite/runelite/refs/heads/master"
    "/runelite-api/src/main/java/net/runelite/api/gameval"
)

# Mapping of categories to their Java class files
EXPORT_MAP: Dict[str, List[str]] = {
    'npcs': ['NpcID.java'],
    'objects': ['ObjectID.java', 'ObjectID1.java'],
    'anims': ['AnimationID.java'],
    'spotanims': ['SpotanimID.java']
}

OUTPUT_PATH = Path('src/main/resources/rs117/hd/scene/gamevals.json')
CONSTANT_PATTERN = re.compile(
    r'(?:/\*\*.*?\*/\s*)?public\s+static\s+final\s+int\s+(\w+)\s*=\s*(-?\d+)\s*;',
    re.DOTALL | re.MULTILINE
)


def fetch_java_file(class_name: str) -> str:
    """Fetch a Java file from RuneLite GitHub repository."""
    url = f"{BASE_URL}/{class_name}"
    print(f"Fetching {url}...")
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.text


def parse_java_constants(java_content: str) -> Dict[str, int]:
    """
    Parse Java file to extract public static final int constants.
    
    Returns:
        Dictionary mapping constant names to their integer values.
    """
    constants = {}
    for match in CONSTANT_PATTERN.finditer(java_content):
        name = match.group(1)
        value = int(match.group(2))
        constants[name] = value
    return constants


def main() -> None:
    """Main function to fetch, parse, and generate gamevals.json."""
    full_export: Dict[str, Dict[str, int]] = {}
    
    for category, file_list in EXPORT_MAP.items():
        print(f"\nProcessing {category}...")
        constants: Dict[str, int] = {}
        
        for java_file in file_list:
            try:
                java_content = fetch_java_file(java_file)
                file_constants = parse_java_constants(java_content)
                constants.update(file_constants)
                print(f"  Found {len(file_constants)} constants in {java_file}")
            except requests.RequestException as e:
                print(f"  Error fetching {java_file}: {e}")
                raise
            except Exception as e:
                print(f"  Error processing {java_file}: {e}")
                raise
        
        full_export[category] = constants
        print(f"  Total {category}: {len(constants)} constants")
    
    # Write output file
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    json_content = "// AUTO-GENERATED FILE. DO NOT MODIFY.\n" + json.dumps(
        full_export, indent=4, sort_keys=True
    )
    OUTPUT_PATH.write_text(json_content, encoding='utf-8')
    
    total_constants = sum(len(v) for v in full_export.values())
    print(f"\nGenerated {OUTPUT_PATH}")
    print(f"Total constants: {total_constants}")


if __name__ == '__main__':
    main()


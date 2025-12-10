#!/usr/bin/env python3
"""
Compare old and new gamevals.json files and generate a change report.
Detects renamed (same ID, different name), added, and removed gamevals.
"""
import json
import sys
from pathlib import Path
import subprocess

def load_gamevals(file_path):
    """Load gamevals.json file"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        # Remove the comment line if present
        if content.startswith('//'):
            content = '\n'.join(content.split('\n')[1:])
        return json.loads(content)

def reverse_map(gamevals):
    """Create reverse mapping: ID -> name for each category"""
    reverse = {}
    for category, constants in gamevals.items():
        reverse[category] = {}
        for name, id_value in constants.items():
            if id_value not in reverse[category]:
                reverse[category][id_value] = []
            reverse[category][id_value].append(name)
    return reverse

def find_gameval_in_json(json_data, gameval_name, path=""):
    """Recursively search JSON for exact string matches of gameval name"""
    matches = []
    
    if isinstance(json_data, dict):
        for key, value in json_data.items():
            new_path = f"{path}.{key}" if path else key
            matches.extend(find_gameval_in_json(value, gameval_name, new_path))
    elif isinstance(json_data, list):
        for i, item in enumerate(json_data):
            new_path = f"{path}[{i}]" if path else f"[{i}]"
            matches.extend(find_gameval_in_json(item, gameval_name, new_path))
    elif isinstance(json_data, str) and json_data == gameval_name:
        matches.append(path if path else "root")
    
    return matches

def check_json_files_for_gamevals(removed_names, renamed_old_names):
    """Check lights.json and model_overrides.json for removed/renamed gameval names"""
    affected_files = {}
    files_to_check = [
        ('src/main/resources/rs117/hd/scene/lights.json', 'lights.json'),
        ('src/main/resources/rs117/hd/scene/model_overrides.json', 'model_overrides.json')
    ]
    
    # Collect all names to check with their change type (removed or renamed)
    names_to_check = {}  # name -> 'removed' or 'renamed'
    for category, removed_list in removed_names.items():
        for name, _ in removed_list:
            names_to_check[name] = 'removed'
    for category, renamed_list in renamed_old_names.items():
        for old_name, _, _ in renamed_list:
            names_to_check[old_name] = 'renamed'
    
    if not names_to_check:
        return affected_files
    
    for file_path, file_display_name in files_to_check:
        json_path = Path(file_path)
        if not json_path.exists():
            continue
        
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            
            file_matches = {}
            for gameval_name, change_type in names_to_check.items():
                matches = find_gameval_in_json(json_data, gameval_name)
                if matches:
                    file_matches[gameval_name] = {
                        'matches': matches,
                        'change_type': change_type
                    }
            
            if file_matches:
                affected_files[file_display_name] = file_matches
        except Exception as e:
            print(f"Warning: Could not check {file_display_name}: {e}", file=sys.stderr)
    
    return affected_files

def compare_gamevals(old_gamevals, new_gamevals):
    """Compare old and new gamevals and detect changes"""
    changes = {
        'renamed': {},  # category -> [(old_name, new_name, id)]
        'added': {},    # category -> [(name, id)]
        'removed': {}   # category -> [(name, id)]
    }
    
    # Check all categories
    all_categories = set(old_gamevals.keys()) | set(new_gamevals.keys())
    
    for category in all_categories:
        old_constants = old_gamevals.get(category, {})
        new_constants = new_gamevals.get(category, {})
        
        # Build ID -> name mappings
        old_id_to_names = {}
        for name, id_val in old_constants.items():
            if id_val not in old_id_to_names:
                old_id_to_names[id_val] = []
            old_id_to_names[id_val].append(name)
        
        new_id_to_names = {}
        for name, id_val in new_constants.items():
            if id_val not in new_id_to_names:
                new_id_to_names[id_val] = []
            new_id_to_names[id_val].append(name)
        
        # Track which IDs we've already processed
        processed_ids = set()
        
        # Find renames: IDs that exist in both but with different names
        for id_val in set(old_id_to_names.keys()) & set(new_id_to_names.keys()):
            old_names = set(old_id_to_names[id_val])
            new_names = set(new_id_to_names[id_val])
            
            if old_names != new_names:
                # Some names changed - this is a rename
                processed_ids.add(id_val)
                if category not in changes['renamed']:
                    changes['renamed'][category] = []
                # Report each old name that doesn't exist in new
                for old_name in old_names - new_names:
                    for new_name in new_names - old_names:
                        changes['renamed'][category].append((old_name, new_name, id_val))
        
        # Find removed: IDs that exist in old but not in new (and weren't renamed)
        for id_val in set(old_id_to_names.keys()) - set(new_id_to_names.keys()):
            if id_val not in processed_ids:
                if category not in changes['removed']:
                    changes['removed'][category] = []
                for old_name in old_id_to_names[id_val]:
                    changes['removed'][category].append((old_name, id_val))
        
        # Find added: IDs that exist in new but not in old
        for id_val in set(new_id_to_names.keys()) - set(old_id_to_names.keys()):
            if category not in changes['added']:
                changes['added'][category] = []
            for new_name in new_id_to_names[id_val]:
                changes['added'][category].append((new_name, id_val))
        
        # Also check for names that changed ID (should be rare but handle it)
        for old_name, old_id in old_constants.items():
            if old_name in new_constants:
                new_id = new_constants[old_name]
                if old_id != new_id:
                    # Name exists but ID changed - treat as removal + addition
                    if category not in changes['removed']:
                        changes['removed'][category] = []
                    changes['removed'][category].append((old_name, old_id))
                    if category not in changes['added']:
                        changes['added'][category] = []
                    changes['added'][category].append((old_name, new_id))
    
    return changes

def generate_report(changes):
    """Generate a markdown report of changes"""
    report_lines = []
    
    # Check JSON files for affected gamevals
    affected_files = check_json_files_for_gamevals(changes['removed'], changes['renamed'])
    
    has_warnings = False
    if any(changes['renamed'].values()) or any(changes['removed'].values()):
        has_warnings = True
    
    # Add warning about JSON files if any matches found
    if affected_files:
        report_lines.append("## ⚠️ WARNING: FOLLOWING CHANGES HAVE BEEN MADE THAT MAY AFFECT THE JSONS")
        report_lines.append("")
        report_lines.append("The following files contain references to removed or renamed gamevals and should be checked:")
        report_lines.append("")
        for file_name, file_matches in affected_files.items():
            report_lines.append(f"### {file_name}")
            report_lines.append("")
            for gameval_name, match_data in sorted(file_matches.items()):
                change_type = match_data['change_type']
                matches = match_data['matches']
                change_label = "🔄 Renamed" if change_type == 'renamed' else "❌ Removed"
                report_lines.append(f"- `{gameval_name}` - {change_label} (found in {len(matches)} location(s))")
            report_lines.append("")
        report_lines.append("")
    
    # Generate unified diff-style view for all changes
    has_any_changes = any(changes['renamed'].values()) or any(changes['removed'].values()) or any(changes['added'].values())
    
    if has_any_changes:
        report_lines.append("## Gamevals Changes")
        report_lines.append("")
        
        # Process all categories
        all_categories = set()
        all_categories.update(changes['renamed'].keys())
        all_categories.update(changes['removed'].keys())
        all_categories.update(changes['added'].keys())
        
        for category in sorted(all_categories):
            renamed_list = changes['renamed'].get(category, [])
            removed_list = changes['removed'].get(category, [])
            added_list = changes['added'].get(category, [])
            
            if renamed_list or removed_list or added_list:
                total_count = len(renamed_list) + len(removed_list) + len(added_list)
                report_lines.append(f"<details>")
                report_lines.append(f"<summary><b>{category.upper()}</b> ({total_count} changes)</summary>")
                report_lines.append("")
                report_lines.append("```diff")
                
                # Show renamed items (old name removed, new name added)
                for old_name, new_name, id_val in renamed_list:
                    report_lines.append(f"-{old_name} (ID: {id_val})")
                    report_lines.append(f"+{new_name} (ID: {id_val})")
                
                # Show removed items
                for name, id_val in removed_list:
                    report_lines.append(f"-{name} (ID: {id_val})")
                
                # Show added items
                for name, id_val in added_list:
                    report_lines.append(f"+{name} (ID: {id_val})")
                
                report_lines.append("```")
                report_lines.append("")
                report_lines.append("</details>")
                report_lines.append("")
    
    if not has_warnings and not any(changes['added'].values()):
        report_lines.append("No changes detected.")
    
    return '\n'.join(report_lines)

def main():
    """Main function"""
    # Get the old version from git
    try:
        result = subprocess.run(
            ['git', 'show', 'HEAD:src/main/resources/rs117/hd/scene/gamevals.json'],
            capture_output=True,
            text=True,
            check=True
        )
        old_content = result.stdout
        if old_content.startswith('//'):
            old_content = '\n'.join(old_content.split('\n')[1:])
        old_gamevals = json.loads(old_content)
    except subprocess.CalledProcessError:
        print("Warning: Could not fetch old gamevals.json from git", file=sys.stderr)
        old_gamevals = {}
    
    # Load new version
    new_path = Path('src/main/resources/rs117/hd/scene/gamevals.json')
    if not new_path.exists():
        print("Error: New gamevals.json not found", file=sys.stderr)
        sys.exit(1)
    
    new_gamevals = load_gamevals(new_path)
    
    # Compare
    changes = compare_gamevals(old_gamevals, new_gamevals)
    
    # Generate report
    report = generate_report(changes)
    print(report)

if __name__ == '__main__':
    main()


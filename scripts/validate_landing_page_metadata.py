#!/usr/bin/env python3
"""
Validate landing page metadata in plugin YAML files.

This script validates that all plugin YAML files (collectors, policies, catalogers)
have complete and valid landing page metadata for the website guardrails pages.

Usage:
    python scripts/validate_landing_page_metadata.py [--verbose] [--type TYPE]

Options:
    --verbose   Show detailed information about each plugin
    --type      Validate only specific type: collector, policy, cataloger (default: all)
"""

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


# =============================================================================
# Plugin Type Configurations
# =============================================================================

PLUGIN_CONFIGS = {
    "collector": {
        "directory": "collectors",
        "yaml_file": "lunar-collector.yml",
        "item_key": "collectors",
    },
    "policy": {
        "directory": "policies",
        "yaml_file": "lunar-policy.yml",
        "item_key": "policies",
    },
    "cataloger": {
        "directory": "catalogers",
        "yaml_file": "lunar-cataloger.yml",
        "item_key": "catalogers",
    },
}

# Valid categories from the plan
VALID_CATEGORIES = {
    "repository-and-ownership",
    "deployment-and-infrastructure",
    "testing-and-quality",
    "devex-build-and-ci",
    "security-and-compliance",
    "operational-readiness",
}

# Valid status values
VALID_STATUSES = {"stable", "beta", "experimental", "deprecated"}

# Valid related types
VALID_RELATED_TYPES = {"collector", "policy", "cataloger"}

# Character limits
DISPLAY_NAME_MAX_LENGTH = 50
TAGLINE_MAX_LENGTH = 100
SEO_TITLE_MAX_LENGTH = 50
SEO_DESCRIPTION_MAX_LENGTH = 160
SUB_SEO_TITLE_MAX_LENGTH = 60
SUB_SEO_DESCRIPTION_MAX_LENGTH = 200
RELATED_REASON_MAX_LENGTH = 80


@dataclass
class ValidationResult:
    """Result of validating a collector YAML."""
    collector_path: Path
    collector_name: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0


def parse_yaml_simple(content: str) -> dict[str, Any]:
    """
    Simple YAML parser for our specific use case.
    Handles the structure we need without external dependencies.
    """
    result: dict[str, Any] = {}
    lines = content.split("\n")
    
    current_path: list[str] = []
    current_indent = 0
    in_multiline = False
    multiline_key = ""
    multiline_value = ""
    multiline_indent = 0
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Handle multiline strings (| or >)
        if in_multiline:
            stripped = line.lstrip()
            line_indent = len(line) - len(stripped)
            
            if stripped and line_indent <= multiline_indent and not line.startswith(" " * (multiline_indent + 1)):
                # End of multiline
                set_nested_value(result, current_path + [multiline_key], multiline_value.strip())
                in_multiline = False
                # Don't increment i, reprocess this line
                continue
            else:
                multiline_value += line + "\n"
                i += 1
                continue
        
        # Skip empty lines and comments
        if not line.strip() or line.strip().startswith("#"):
            i += 1
            continue
        
        # Calculate indent
        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        
        # Adjust current path based on indent
        while current_path and indent <= current_indent - 2:
            current_path.pop()
            current_indent -= 2
        
        # Parse key-value or list item
        if stripped.startswith("- "):
            # List item
            item_content = stripped[2:].strip()
            
            # Get or create the list at current path
            parent = get_nested_value(result, current_path)
            if not isinstance(parent, list):
                set_nested_value(result, current_path, [])
                parent = get_nested_value(result, current_path)
            
            if ": " in item_content or item_content.endswith(":"):
                # Item with nested content: - name: value
                if ": " in item_content:
                    key, value = item_content.split(": ", 1)
                    parent.append({key.strip(): parse_value(value.strip())})
                else:
                    key = item_content[:-1]
                    parent.append({key.strip(): {}})
            else:
                # Simple list item
                parent.append(parse_value(item_content))
        
        elif ": " in stripped or stripped.endswith(":"):
            # Key-value pair
            if ": " in stripped:
                key, value = stripped.split(": ", 1)
                key = key.strip()
                value = value.strip()
                
                if value == "|" or value == ">":
                    # Multiline string
                    in_multiline = True
                    multiline_key = key
                    multiline_value = ""
                    multiline_indent = indent
                else:
                    set_nested_value(result, current_path + [key], parse_value(value))
            else:
                # New section
                key = stripped[:-1].strip()
                set_nested_value(result, current_path + [key], {})
                current_path.append(key)
                current_indent = indent + 2
        
        i += 1
    
    # Handle any remaining multiline content
    if in_multiline:
        set_nested_value(result, current_path + [multiline_key], multiline_value.strip())
    
    return result


def parse_value(value: str) -> Any:
    """Parse a YAML value into the appropriate Python type."""
    if not value:
        return ""
    
    # Remove quotes
    if (value.startswith('"') and value.endswith('"')) or \
       (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    
    # Boolean
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    
    # Number
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        pass
    
    # Array (simple inline format)
    if value.startswith("[") and value.endswith("]"):
        items = value[1:-1].split(",")
        return [parse_value(item.strip()) for item in items if item.strip()]
    
    return value


def get_nested_value(obj: dict, path: list[str]) -> Any:
    """Get a value from a nested dict using a path."""
    current = obj
    for key in path:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return None
    return current


def set_nested_value(obj: dict, path: list[str], value: Any) -> None:
    """Set a value in a nested dict using a path."""
    current = obj
    for key in path[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]
    if path:
        current[path[-1]] = value


def parse_yaml_file(yaml_path: Path) -> Optional[dict[str, Any]]:
    """Parse a YAML file and return its contents as a dict."""
    try:
        content = yaml_path.read_text()
        return parse_yaml_simple(content)
    except Exception as e:
        return None


def parse_yaml_with_regex(content: str) -> dict[str, Any]:
    """
    Parse YAML using regex for more reliable extraction of specific fields.
    This is a fallback/supplement to the simple parser.
    """
    result: dict[str, Any] = {}
    
    # Extract landing_page section
    landing_page_match = re.search(
        r"^landing_page:\s*$\n((?:[ ]+.*\n)*)",
        content,
        re.MULTILINE
    )
    
    if landing_page_match:
        landing_section = landing_page_match.group(1)
        result["landing_page"] = {}
        
        # Extract simple fields
        for field_name in ["display_name", "tagline", "seo_title", "category", "icon", "status"]:
            match = re.search(
                rf'^  {field_name}:\s*["\']?([^"\'\n]+)["\']?\s*$',
                landing_section,
                re.MULTILINE
            )
            if match:
                result["landing_page"][field_name] = match.group(1).strip()
        
        # Extract seo_description (multiline)
        seo_desc_match = re.search(
            r'^  seo_description:\s*\|?\s*$\n((?:[ ]{4,}.*\n)*)',
            landing_section,
            re.MULTILINE
        )
        if seo_desc_match:
            desc_lines = seo_desc_match.group(1).strip()
            result["landing_page"]["seo_description"] = " ".join(
                line.strip() for line in desc_lines.split("\n")
            )
        
        # Extract categories (array)
        categories_match = re.search(
            r'^  categories:\s*$\n((?:[ ]+- .*\n)*)',
            landing_section,
            re.MULTILINE
        )
        if categories_match:
            cats = re.findall(r'^\s+- ["\']?([^"\'\n]+)["\']?', categories_match.group(1), re.MULTILINE)
            result["landing_page"]["categories"] = cats
        
        # Extract related array
        related_match = re.search(
            r'^  related:\s*$\n((?:[ ]+.*\n)*)',
            landing_section,
            re.MULTILINE
        )
        if related_match:
            related_section = related_match.group(1)
            related_items = []
            
            # Find each related item (starts with - slug:)
            item_matches = re.finditer(
                r'^\s+- slug:\s*["\']?([^"\'\n]+)["\']?\s*$\n'
                r'(?:\s+type:\s*["\']?([^"\'\n]+)["\']?\s*$\n)?'
                r'(?:\s+reason:\s*["\']?([^"\'\n]+)["\']?\s*$)?',
                related_section,
                re.MULTILINE
            )
            for match in item_matches:
                item = {"slug": match.group(1).strip()}
                if match.group(2):
                    item["type"] = match.group(2).strip()
                if match.group(3):
                    item["reason"] = match.group(3).strip()
                related_items.append(item)
            
            result["landing_page"]["related"] = related_items
    
    # Extract collectors array with SEO fields
    collectors_match = re.search(
        r"^collectors:\s*$\n((?:[ ]+.*\n)*)",
        content,
        re.MULTILINE
    )
    
    if collectors_match:
        collectors_section = collectors_match.group(1)
        collectors = []
        
        # Split by "- name:" to get individual collectors
        collector_blocks = re.split(r'^  - name:', collectors_section, flags=re.MULTILINE)
        
        for block in collector_blocks[1:]:  # Skip first empty split
            collector: dict[str, Any] = {}
            
            # Get name (first line)
            name_match = re.match(r'\s*([^\n]+)', block)
            if name_match:
                collector["name"] = name_match.group(1).strip()
            
            # Get seo_title
            seo_title_match = re.search(
                r'^\s+seo_title:\s*["\']?([^"\'\n]+)["\']?\s*$',
                block,
                re.MULTILINE
            )
            if seo_title_match:
                collector["seo_title"] = seo_title_match.group(1).strip()
            
            # Get seo_description (multiline)
            seo_desc_match = re.search(
                r'^\s+seo_description:\s*\|?\s*$\n((?:[ ]{6,}.*\n)*)',
                block,
                re.MULTILINE
            )
            if seo_desc_match:
                desc_lines = seo_desc_match.group(1).strip()
                collector["seo_description"] = " ".join(
                    line.strip() for line in desc_lines.split("\n")
                )
            
            # Get seo_keywords (array)
            keywords_match = re.search(
                r'^\s+seo_keywords:\s*\[([^\]]+)\]',
                block,
                re.MULTILINE
            )
            if keywords_match:
                keywords = [
                    k.strip().strip('"\'') 
                    for k in keywords_match.group(1).split(",")
                ]
                collector["seo_keywords"] = [k for k in keywords if k]
            
            if collector.get("name"):
                collectors.append(collector)
        
        result["collectors"] = collectors
    
    # Extract top-level name
    name_match = re.search(r"^name:\s*(.+)$", content, re.MULTILINE)
    if name_match:
        result["name"] = name_match.group(1).strip()
    
    return result


def get_readme_title(readme_path: Path) -> Optional[str]:
    """Extract the title from a README file."""
    if not readme_path.exists():
        return None
    
    try:
        content = readme_path.read_text()
        lines = content.split("\n")
        
        for line in lines:
            if line.startswith("# "):
                return line[2:].strip()
        return None
    except Exception:
        return None


def validate_plugin(
    plugin_dir: Path,
    plugin_type: str,
    config: dict[str, Any],
    base_dir: Path,
) -> ValidationResult:
    """Validate a plugin's landing page metadata."""
    plugin_name = plugin_dir.name
    yaml_path = plugin_dir / config["yaml_file"]
    readme_path = plugin_dir / "README.md"
    
    result = ValidationResult(
        collector_path=yaml_path,
        collector_name=plugin_name,
    )
    
    # Get related directories
    policies_dir = base_dir / "policies"
    collectors_dir = base_dir / "collectors"
    catalogers_dir = base_dir / "catalogers"
    
    # Check YAML exists
    if not yaml_path.exists():
        result.errors.append(f"Missing {config['yaml_file']}")
        return result
    
    # Parse YAML
    try:
        content = yaml_path.read_text()
        data = parse_yaml_with_regex(content)
    except Exception as e:
        result.errors.append(f"Failed to parse YAML: {e}")
        return result
    
    # Get landing_page section
    landing_page = data.get("landing_page", {})
    if not landing_page:
        result.errors.append("Missing 'landing_page:' section")
        return result
    
    # Validate display_name
    display_name = landing_page.get("display_name")
    if not display_name:
        result.errors.append("Missing landing_page.display_name")
    elif len(display_name) > DISPLAY_NAME_MAX_LENGTH:
        result.errors.append(
            f"landing_page.display_name too long ({len(display_name)} chars, "
            f"max {DISPLAY_NAME_MAX_LENGTH})"
        )
    
    # Validate tagline
    tagline = landing_page.get("tagline")
    if not tagline:
        result.errors.append("Missing landing_page.tagline")
    elif len(tagline) > TAGLINE_MAX_LENGTH:
        result.errors.append(
            f"landing_page.tagline too long ({len(tagline)} chars, "
            f"max {TAGLINE_MAX_LENGTH})"
        )
    
    # Validate seo_title
    seo_title = landing_page.get("seo_title")
    if not seo_title:
        result.errors.append("Missing landing_page.seo_title")
    elif len(seo_title) > SEO_TITLE_MAX_LENGTH:
        result.errors.append(
            f"landing_page.seo_title too long ({len(seo_title)} chars, "
            f"max {SEO_TITLE_MAX_LENGTH})"
        )
    
    # Validate seo_description
    seo_description = landing_page.get("seo_description")
    if not seo_description:
        result.errors.append("Missing landing_page.seo_description")
    elif len(seo_description) > SEO_DESCRIPTION_MAX_LENGTH:
        result.errors.append(
            f"landing_page.seo_description too long ({len(seo_description)} chars, "
            f"max {SEO_DESCRIPTION_MAX_LENGTH})"
        )
    
    # Validate category/categories
    category = landing_page.get("category")
    categories = landing_page.get("categories", [])
    
    if not category and not categories:
        result.errors.append(
            "Missing landing_page.category or landing_page.categories"
        )
    else:
        all_categories = categories if categories else [category]
        for cat in all_categories:
            if cat not in VALID_CATEGORIES:
                result.errors.append(
                    f"Invalid category '{cat}'. Must be one of: {sorted(VALID_CATEGORIES)}"
                )
    
    # Validate icon (required)
    icon = landing_page.get("icon")
    if not icon:
        result.errors.append("Missing landing_page.icon")
    else:
        icon_path = plugin_dir / icon
        if not icon_path.exists():
            result.errors.append(
                f"Icon file not found: {icon} (expected at {icon_path})"
            )
    
    # Validate status (optional, but must be valid if present)
    status = landing_page.get("status")
    if status and status not in VALID_STATUSES:
        result.errors.append(
            f"Invalid status '{status}'. Must be one of: {sorted(VALID_STATUSES)}"
        )
    
    # Validate related (optional, but structure must be valid if present)
    related = landing_page.get("related", [])
    if related:
        for i, rel in enumerate(related):
            if not isinstance(rel, dict):
                result.errors.append(f"landing_page.related[{i}] must be an object")
                continue
            
            # slug is required
            if not rel.get("slug"):
                result.errors.append(f"landing_page.related[{i}].slug is required")
            
            # type is required
            rel_type = rel.get("type")
            if not rel_type:
                result.errors.append(f"landing_page.related[{i}].type is required")
            elif rel_type not in VALID_RELATED_TYPES:
                result.errors.append(
                    f"landing_page.related[{i}].type '{rel_type}' invalid. "
                    f"Must be one of: {sorted(VALID_RELATED_TYPES)}"
                )
            
            # reason is optional but has max length
            reason = rel.get("reason", "")
            if reason and len(reason) > RELATED_REASON_MAX_LENGTH:
                result.errors.append(
                    f"landing_page.related[{i}].reason too long ({len(reason)} chars, "
                    f"max {RELATED_REASON_MAX_LENGTH})"
                )
            
            # Cross-validate: check if related plugin exists
            slug = rel.get("slug")
            if slug and rel_type:
                if rel_type == "policy":
                    target_dir = policies_dir / slug
                elif rel_type == "collector":
                    target_dir = collectors_dir / slug
                elif rel_type == "cataloger":
                    target_dir = catalogers_dir / slug
                else:
                    target_dir = None
                
                if target_dir and not target_dir.exists():
                    result.warnings.append(
                        f"landing_page.related[{i}] references non-existent "
                        f"{rel_type} '{slug}'"
                    )
    
    # Validate sub-items SEO fields
    item_key = config["item_key"]
    items = data.get(item_key, [])
    if not items:
        result.errors.append(f"No {item_key} found in YAML")
    else:
        for i, item in enumerate(items):
            name = item.get("name", f"[{i}]")
            
            # seo_title required
            sub_seo_title = item.get("seo_title")
            if not sub_seo_title:
                result.errors.append(f"{item_key}.{name}: missing seo_title")
            elif len(sub_seo_title) > SUB_SEO_TITLE_MAX_LENGTH:
                result.errors.append(
                    f"{item_key}.{name}: seo_title too long ({len(sub_seo_title)} chars, "
                    f"max {SUB_SEO_TITLE_MAX_LENGTH})"
                )
            
            # seo_description required
            sub_seo_desc = item.get("seo_description")
            if not sub_seo_desc:
                result.errors.append(f"{item_key}.{name}: missing seo_description")
            elif len(sub_seo_desc) > SUB_SEO_DESCRIPTION_MAX_LENGTH:
                result.errors.append(
                    f"{item_key}.{name}: seo_description too long ({len(sub_seo_desc)} chars, "
                    f"max {SUB_SEO_DESCRIPTION_MAX_LENGTH})"
                )
            
            # seo_keywords required (at least 1)
            sub_keywords = item.get("seo_keywords", [])
            if not sub_keywords:
                result.errors.append(f"{item_key}.{name}: missing seo_keywords")
            elif not isinstance(sub_keywords, list) or len(sub_keywords) < 1:
                result.errors.append(
                    f"{item_key}.{name}: seo_keywords must be an array with at least 1 keyword"
                )
    
    # Validate README title matches display_name
    if display_name and readme_path.exists():
        readme_title = get_readme_title(readme_path)
        # README title should be "{display_name} Collector" or similar based on type
        suffix = {"collector": "Collector", "policy": "Policies", "cataloger": "Cataloger"}.get(plugin_type, "")
        expected_title = f"{display_name} {suffix}".strip()
        
        # Also accept the backtick format from existing READMEs
        alt_expected = f"`{plugin_name}` {suffix}".strip()
        
        if readme_title and readme_title != expected_title and readme_title != alt_expected:
            result.warnings.append(
                f"README title '{readme_title}' doesn't match expected "
                f"'{expected_title}' (from display_name)"
            )
    
    return result


def validate_plugin_type(
    plugin_type: str,
    base_dir: Path,
    verbose: bool,
) -> tuple[int, int, int]:
    """Validate all plugins of a specific type."""
    config = PLUGIN_CONFIGS[plugin_type]
    plugins_dir = base_dir / config["directory"]
    
    if not plugins_dir.exists():
        print(f"  Directory not found: {plugins_dir}")
        return 0, 0, 0
    
    # Find all plugin directories (those with the YAML file)
    plugin_dirs = sorted([
        d for d in plugins_dir.iterdir()
        if d.is_dir() and (d / config["yaml_file"]).exists()
    ])
    
    if not plugin_dirs:
        print(f"  No {plugin_type}s found in {plugins_dir}")
        return 0, 0, 0
    
    valid_count = 0
    error_count = 0
    warning_count = 0
    
    for plugin_dir in plugin_dirs:
        result = validate_plugin(plugin_dir, plugin_type, config, base_dir)
        
        status_symbol = "✓" if result.is_valid else "✗"
        print(f"  {status_symbol} {result.collector_name}")
        
        if verbose and result.is_valid:
            yaml_path = plugin_dir / config["yaml_file"]
            content = yaml_path.read_text()
            data = parse_yaml_with_regex(content)
            lp = data.get("landing_page", {})
            print(f"    display_name: {lp.get('display_name', '(missing)')}")
            print(f"    category: {lp.get('category') or lp.get('categories', '(missing)')}")
        
        if result.errors:
            error_count += len(result.errors)
            for error in result.errors:
                print(f"    ERROR: {error}")
        else:
            valid_count += 1
        
        if result.warnings:
            warning_count += len(result.warnings)
            for warning in result.warnings:
                print(f"    WARNING: {warning}")
    
    return valid_count, error_count, warning_count


def main():
    parser = argparse.ArgumentParser(
        description="Validate landing page metadata in plugin YAML files"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed information about each plugin",
    )
    parser.add_argument(
        "--type", "-t",
        choices=["collector", "policy", "cataloger", "all"],
        default="all",
        help="Plugin type to validate (default: all)",
    )
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=Path(__file__).parent.parent,
        help="Base directory containing collectors/policies/catalogers",
    )
    args = parser.parse_args()
    
    base_dir = args.base_dir.resolve()
    
    types_to_validate = (
        ["collector", "policy", "cataloger"]
        if args.type == "all"
        else [args.type]
    )
    
    print("Validating landing page metadata...\n")
    
    total_valid = 0
    total_errors = 0
    total_warnings = 0
    
    for plugin_type in types_to_validate:
        config = PLUGIN_CONFIGS[plugin_type]
        plugins_dir = base_dir / config["directory"]
        plugin_count = len([
            d for d in plugins_dir.iterdir()
            if d.is_dir() and (d / config["yaml_file"]).exists()
        ]) if plugins_dir.exists() else 0
        
        print(f"{plugin_type.upper()}S ({plugin_count}):")
        valid, errors, warnings = validate_plugin_type(plugin_type, base_dir, args.verbose)
        total_valid += valid
        total_errors += errors
        total_warnings += warnings
        print()
    
    # Summary
    print("-" * 60)
    if total_errors == 0:
        if total_warnings > 0:
            print(f"All plugins have valid landing page metadata ({total_warnings} warning(s)).")
        else:
            print("All plugins have valid landing page metadata.")
        sys.exit(0)
    else:
        print(f"Validation failed: {total_errors} error(s), {total_warnings} warning(s)")
        print("\nRequired landing_page fields:")
        print(f"  display_name: max {DISPLAY_NAME_MAX_LENGTH} chars")
        print(f"  tagline: max {TAGLINE_MAX_LENGTH} chars")
        print(f"  seo_title: max {SEO_TITLE_MAX_LENGTH} chars")
        print(f"  seo_description: max {SEO_DESCRIPTION_MAX_LENGTH} chars")
        print(f"  category: one of {sorted(VALID_CATEGORIES)}")
        print(f"  icon: path to SVG file (must exist)")
        print(f"\nOptional landing_page fields:")
        print(f"  status: one of {sorted(VALID_STATUSES)} (defaults to stable)")
        print(f"  related: array of {{slug, type, reason}}")
        print(f"\nRequired per-item fields:")
        print(f"  seo_title: max {SUB_SEO_TITLE_MAX_LENGTH} chars")
        print(f"  seo_description: max {SUB_SEO_DESCRIPTION_MAX_LENGTH} chars")
        print(f"  seo_keywords: array with at least 1 keyword")
        sys.exit(1)


if __name__ == "__main__":
    main()

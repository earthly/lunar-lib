#!/usr/bin/env python3
"""
Unified README structure validator for all plugin types.

This script validates that all plugin README.md files follow the structure
defined in their respective templates.

Usage:
    python scripts/validate_readme_structure.py [--verbose] [--type TYPE]

Options:
    --verbose   Show detailed information about each README
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
        "title_suffix": "Collector",
        "uses_path": "github://earthly/lunar-lib/collectors",
        "item_list_name": "collectors",  # Key in YAML
        "item_section_name": "Collectors",  # Section name in README
        "data_section_name": "Collected Data",
        "related_section_name": None,  # Moved to YAML
        "related_directory": None,
        # Sections: Inputs, Secrets, Related Policies moved to YAML
        "sections": [
            {"name": "Overview", "required": True},
            {"name": "Collected Data", "required": True},
            {"name": "Collectors", "required": False},
            {"name": "Installation", "required": True},
        ],
        # Sections that have been moved to YAML and should not be in README
        "disallowed_sections": [
            "Inputs",
            "Secrets",
            "Related Policies",
            "Related Collectors",
            "Example Component JSON",
        ],
    },
    "policy": {
        "directory": "policies",
        "yaml_file": "lunar-policy.yml",
        "title_suffix": "Guardrails",
        "uses_path": "github://earthly/lunar-lib/policies",
        "item_list_name": "policies",
        "item_section_name": "Policies",
        "data_section_name": "Required Data",
        "related_section_name": None,  # Moved to YAML
        "related_directory": None,
        # Sections: Inputs, Related Collectors moved to YAML
        "sections": [
            {"name": "Overview", "required": True},
            {"name": "Policies", "required": True},
            {"name": "Required Data", "required": True},
            {"name": "Installation", "required": True},
            {"name": "Examples", "required": True},
            {"name": "Remediation", "required": True},
        ],
        # Sections that have been moved to YAML and should not be in README
        "disallowed_sections": [
            "Inputs",
            "Related Collectors",
            "Related Policies",
        ],
    },
    "cataloger": {
        "directory": "catalogers",
        "yaml_file": "lunar-cataloger.yml",
        "title_suffix": "Cataloger",
        "uses_path": "github.com/earthly/lunar-lib/catalogers",
        "item_list_name": "catalogers",
        "item_section_name": "Catalogers",
        "data_section_name": "Synced Data",
        "related_section_name": None,
        "related_directory": None,
        # Sections: Inputs, Secrets moved to YAML
        "sections": [
            {"name": "Overview", "required": True},
            {"name": "Synced Data", "required": True},
            {"name": "Catalogers", "required": False},
            {"name": "Hook Type", "required": True},
            {"name": "Installation", "required": True},
            {"name": "Source System", "required": True},
        ],
        # Sections that have been moved to YAML and should not be in README
        "disallowed_sections": [
            "Inputs",
            "Secrets",
            "Related Policies",
            "Related Collectors",
            "Example Catalog JSON",
        ],
    },
}

# Validation constraints
ONE_LINER_MIN_LENGTH = 20
ONE_LINER_MAX_LENGTH = 200
OVERVIEW_MIN_SENTENCES = 2
OVERVIEW_MAX_SENTENCES = 5
OVERVIEW_MIN_LENGTH = 100
OVERVIEW_MAX_LENGTH = 800


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class Section:
    """Represents a markdown section."""
    name: str
    level: int
    start_line: int
    end_line: int
    content: str


@dataclass
class ValidationResult:
    """Result of validating a README."""
    readme_path: Path
    plugin_type: str
    plugin_name: str
    title: Optional[str] = None
    one_liner: Optional[str] = None
    sections: list[Section] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0


# =============================================================================
# Parsing Functions
# =============================================================================

def count_sentences(text: str) -> int:
    """Count approximate number of sentences in text."""
    sentences = re.split(r'[.!?]+(?:\s|$)', text.strip())
    return len([s for s in sentences if s.strip()])


def parse_readme(content: str) -> tuple[Optional[str], Optional[str], list[Section]]:
    """Parse a README into its title, one-liner description, and sections."""
    lines = content.split("\n")
    title = None
    one_liner = None
    sections: list[Section] = []
    
    i = 0
    
    # Find title
    while i < len(lines) and lines[i].strip() == "":
        i += 1
    
    if i < len(lines) and lines[i].startswith("# "):
        title = lines[i][2:].strip()
        i += 1
        
        while i < len(lines) and lines[i].strip() == "":
            i += 1
        
        if i < len(lines) and lines[i].strip() and not lines[i].startswith("#"):
            one_liner = lines[i].strip()
    
    # Parse sections
    section_pattern = re.compile(r"^(#{2,6})\s+(.+)$")
    current_section_start = None
    current_section_name = None
    current_section_level = None
    in_code_block = False
    
    for line_num, line in enumerate(lines):
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue
        
        if in_code_block:
            continue
        
        match = section_pattern.match(line)
        if match:
            level = len(match.group(1))
            name = match.group(2).strip()
            
            if level == 2:
                if current_section_name is not None:
                    section_content = "\n".join(lines[current_section_start:line_num])
                    sections.append(Section(
                        name=current_section_name,
                        level=current_section_level,
                        start_line=current_section_start,
                        end_line=line_num - 1,
                        content=section_content,
                    ))
                
                current_section_start = line_num
                current_section_name = name
                current_section_level = level
    
    if current_section_name is not None:
        section_content = "\n".join(lines[current_section_start:])
        sections.append(Section(
            name=current_section_name,
            level=current_section_level,
            start_line=current_section_start,
            end_line=len(lines) - 1,
            content=section_content,
        ))
    
    return title, one_liner, sections


def get_section_body(section: Section) -> str:
    """Extract the body content of a section (excluding the heading)."""
    lines = section.content.split("\n")
    return "\n".join(lines[1:]).strip()


def get_plugin_name_from_yaml(yaml_file: Path) -> Optional[str]:
    """Get the top-level 'name' field from a YAML file."""
    if not yaml_file.exists():
        return None
    
    content = yaml_file.read_text()
    match = re.search(r"^name:\s*(.+)$", content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return None


def get_item_names_from_yaml(yaml_file: Path, item_key: str) -> set[str]:
    """Get item names from a YAML file (collectors, policies, or catalogers)."""
    if not yaml_file.exists():
        return set()
    
    item_names = set()
    content = yaml_file.read_text()
    
    in_items_section = False
    lines = content.split("\n")
    
    for line in lines:
        if re.match(rf"^{item_key}:\s*$", line):
            in_items_section = True
            continue
        
        if in_items_section and re.match(r"^[a-zA-Z]", line) and not line.startswith(" "):
            in_items_section = False
            continue
        
        if in_items_section:
            match = re.match(r"^\s+-\s*name:\s*(.+)$", line)
            if match:
                item_names.add(match.group(1).strip())
    
    return item_names


def get_inputs_from_yaml(yaml_file: Path) -> set[str]:
    """Get input names from a YAML file."""
    if not yaml_file.exists():
        return set()
    
    input_names = set()
    content = yaml_file.read_text()
    
    in_inputs_section = False
    lines = content.split("\n")
    
    for line in lines:
        if re.match(r"^inputs:\s*$", line):
            in_inputs_section = True
            continue
        
        if in_inputs_section and re.match(r"^[a-zA-Z]", line) and not line.startswith(" "):
            in_inputs_section = False
            continue
        
        if in_inputs_section:
            match = re.match(r"^  ([a-zA-Z_][a-zA-Z0-9_]*):\s*$", line)
            if match:
                input_names.add(match.group(1))
    
    return input_names


def extract_table_names(content: str) -> list[str]:
    """Extract names from a table with backtick-formatted first column."""
    pattern = re.compile(r"^\|\s*`([^`]+)`\s*\|", re.MULTILINE)
    return pattern.findall(content)


def extract_path_table_paths(content: str) -> list[str]:
    """Extract paths from a table with Path column."""
    lines = content.split("\n")
    in_path_table = False
    paths = []
    
    for line in lines:
        if "| Path |" in line and "| Type |" in line:
            in_path_table = True
            continue
        
        if in_path_table and (line.strip().startswith("|--") or line.strip().startswith("| --")):
            continue
        
        if in_path_table and (not line.strip() or line.startswith("#")):
            in_path_table = False
            continue
        
        if in_path_table and line.strip().startswith("|"):
            path_match = re.match(r"^\|\s*`([^`]+)`\s*\|", line)
            if path_match:
                paths.append(path_match.group(1))
    
    return paths


# =============================================================================
# Validation Logic
# =============================================================================

def validate_readme(
    readme_path: Path,
    plugin_name: str,
    plugin_type: str,
    config: dict[str, Any],
    base_dir: Path,
) -> ValidationResult:
    """Validate a README against the template structure."""
    result = ValidationResult(
        readme_path=readme_path,
        plugin_type=plugin_type,
        plugin_name=plugin_name,
    )
    
    try:
        content = readme_path.read_text()
    except Exception as e:
        result.errors.append(f"Failed to read file: {e}")
        return result
    
    title, one_liner, sections = parse_readme(content)
    result.title = title
    result.one_liner = one_liner
    result.sections = sections
    
    plugin_dir = readme_path.parent
    yaml_file = plugin_dir / config["yaml_file"]
    
    # Validate YAML name matches directory name
    yaml_name = get_plugin_name_from_yaml(yaml_file)
    if yaml_name is None:
        result.errors.append(f"Missing {config['yaml_file']} or 'name' field in YAML")
    elif yaml_name != plugin_name:
        result.errors.append(
            f"YAML 'name: {yaml_name}' does not match directory name '{plugin_name}'"
        )
    
    # Validate title
    if not title:
        result.errors.append("Missing title (# heading)")
    else:
        # Accept both formats:
        # 1. `{name}` {Suffix} (old format with backticks)
        # 2. {Name} {Suffix} (new clean format, e.g., "Dockerfile Collector")
        backtick_format = f"`{plugin_name}` {config['title_suffix']}"
        # Check if title ends with the suffix (flexible on the prefix)
        if not title.endswith(config['title_suffix']):
            result.errors.append(
                f"Title must end with '{config['title_suffix']}', got '{title}'"
            )
    
    # Validate one-liner description
    if not one_liner:
        result.errors.append("Missing one-line description after title")
    else:
        if len(one_liner) < ONE_LINER_MIN_LENGTH:
            result.errors.append(
                f"One-liner too short ({len(one_liner)} chars). "
                f"Minimum: {ONE_LINER_MIN_LENGTH} chars"
            )
        if len(one_liner) > ONE_LINER_MAX_LENGTH:
            result.errors.append(
                f"One-liner too long ({len(one_liner)} chars). "
                f"Maximum: {ONE_LINER_MAX_LENGTH} chars"
            )
    
    # Check sections
    section_order = [s["name"] for s in config["sections"]]
    required_sections = {s["name"] for s in config["sections"] if s["required"]}
    section_names = [s.name for s in sections]
    
    for required in required_sections:
        if required not in section_names:
            result.errors.append(f"Missing required section: ## {required}")
    
    template_sections_present = [s for s in section_order if s in section_names]
    readme_sections_in_template = [s for s in section_names if s in section_order]
    
    if template_sections_present != readme_sections_in_template:
        result.errors.append(
            f"Sections out of order. Expected: {template_sections_present}, "
            f"Found: {readme_sections_in_template}"
        )
    
    # Check for disallowed sections (moved to YAML)
    disallowed_sections = config.get("disallowed_sections", [])
    found_disallowed = [s for s in section_names if s in disallowed_sections]
    if found_disallowed:
        for section in found_disallowed:
            result.errors.append(
                f"Section '## {section}' is not allowed - this content has been moved to the YAML file"
            )
    
    unknown_sections = [
        s for s in section_names 
        if s not in section_order and s not in disallowed_sections
    ]
    if unknown_sections:
        result.errors.append(f"Unknown sections (not in template): {unknown_sections}")
    
    # Validate Overview section
    overview = next((s for s in sections if s.name == "Overview"), None)
    if overview:
        body = get_section_body(overview)
        sentence_count = count_sentences(body)
        
        if len(body) < OVERVIEW_MIN_LENGTH:
            result.errors.append(
                f"Overview too short ({len(body)} chars). Minimum: {OVERVIEW_MIN_LENGTH} chars"
            )
        if len(body) > OVERVIEW_MAX_LENGTH:
            result.errors.append(
                f"Overview too long ({len(body)} chars). Maximum: {OVERVIEW_MAX_LENGTH} chars"
            )
        if sentence_count < OVERVIEW_MIN_SENTENCES:
            result.errors.append(
                f"Overview has too few sentences ({sentence_count}). "
                f"Minimum: {OVERVIEW_MIN_SENTENCES} sentences"
            )
        if sentence_count > OVERVIEW_MAX_SENTENCES:
            result.errors.append(
                f"Overview has too many sentences ({sentence_count}). "
                f"Maximum: {OVERVIEW_MAX_SENTENCES} sentences"
            )
    
    # Validate item list section (Collectors/Policies/Catalogers)
    item_section_name = config["item_section_name"]
    item_list_name = config["item_list_name"]
    yaml_items = get_item_names_from_yaml(yaml_file, item_list_name)
    item_section = next((s for s in sections if s.name == item_section_name), None)
    
    if len(yaml_items) > 1 and not item_section:
        result.errors.append(
            f"## {item_section_name} section is required since YAML has "
            f"{len(yaml_items)} items: {sorted(yaml_items)}"
        )
    
    if item_section:
        body = item_section.content
        # Map plural section names to singular column headers
        singular_map = {"Collectors": "Collector", "Policies": "Policy", "Catalogers": "Cataloger"}
        singular_name = singular_map.get(item_section_name, item_section_name)
        
        has_table = re.search(rf"\|\s*{singular_name}\s*\|.*Description\s*\|", body, re.IGNORECASE)
        if not has_table:
            # Also try the plural form
            has_table = re.search(rf"\|\s*{item_section_name}\s*\|.*Description\s*\|", body, re.IGNORECASE)
        
        if not has_table:
            result.errors.append(
                f"## {item_section_name} must have a table with {singular_name}, Description columns"
            )
        else:
            names_in_readme = set(extract_table_names(body))
            if yaml_items:
                missing = yaml_items - names_in_readme
                extra = names_in_readme - yaml_items
                
                if missing:
                    result.errors.append(
                        f"## {item_section_name} table is missing items from YAML: {sorted(missing)}"
                    )
                if extra:
                    result.errors.append(
                        f"## {item_section_name} table lists items not in YAML: {sorted(extra)}"
                    )
    
    # Validate Installation section
    installation = next((s for s in sections if s.name == "Installation"), None)
    if installation:
        body = installation.content
        if "```yaml" not in body:
            result.errors.append(
                "## Installation must have a ```yaml code block with example config"
            )
        else:
            uses_pattern = re.compile(
                rf"uses:\s*{re.escape(config['uses_path'])}/([^@\s]+)"
            )
            uses_match = uses_pattern.search(body)
            if not uses_match:
                result.errors.append(
                    f"## Installation must have 'uses: {config['uses_path']}/{{name}}@...'"
                )
            else:
                uses_path = uses_match.group(1)
                if uses_path != plugin_name:
                    result.errors.append(
                        f"## Installation 'uses:' path '{uses_path}' does not match "
                        f"directory '{plugin_name}'"
                    )
    
    # Type-specific validations
    if plugin_type == "policy":
        _validate_policy_specific(result, sections, plugin_dir, base_dir)
    elif plugin_type == "cataloger":
        _validate_cataloger_specific(result, sections, plugin_dir)
    
    return result


def _validate_policy_specific(
    result: ValidationResult,
    sections: list[Section],
    plugin_dir: Path,
    base_dir: Path,
) -> None:
    """Policy-specific validations."""
    # Validate Required Data section
    required_data = next((s for s in sections if s.name == "Required Data"), None)
    if required_data:
        body = required_data.content
        if "| Path |" not in body:
            result.errors.append(
                "## Required Data must have a table with Path, Type columns"
            )
        else:
            paths = extract_path_table_paths(body)
            invalid_paths = [p for p in paths if not p.startswith(".")]
            if invalid_paths:
                result.errors.append(
                    f"## Required Data paths must start with '.': {invalid_paths}"
                )
    
    # Validate Examples section
    examples = next((s for s in sections if s.name == "Examples"), None)
    if examples:
        body = examples.content
        if "passing" not in body.lower():
            result.errors.append("## Examples must have a 'Passing Example' subsection")
        if "failing" not in body.lower():
            result.errors.append("## Examples must have a 'Failing Example' subsection")
        if "```json" not in body:
            result.errors.append("## Examples must have ```json code blocks")
    
    # Validate Remediation section
    remediation = next((s for s in sections if s.name == "Remediation"), None)
    if remediation:
        body = get_section_body(remediation)
        if len(body) < 50:
            result.errors.append(
                "## Remediation section is too short. Provide actionable steps."
            )
    
    # Validate Related Collectors section
    related = next((s for s in sections if s.name == "Related Collectors"), None)
    if related:
        body = get_section_body(related)
        link_pattern = re.compile(r"^-\s+\[.*?\]\(.*?\)", re.MULTILINE)
        links = link_pattern.findall(body)
        if not links:
            result.errors.append(
                "## Related Collectors must have a bulleted list with markdown links"
            )


def _validate_cataloger_specific(
    result: ValidationResult,
    sections: list[Section],
    plugin_dir: Path,
) -> None:
    """Cataloger-specific validations."""
    # Validate Synced Data section
    synced_data = next((s for s in sections if s.name == "Synced Data"), None)
    if synced_data:
        body = synced_data.content
        if "| Path |" not in body:
            result.errors.append(
                "## Synced Data must have a table with Path, Type, Description columns"
            )
    
    # Validate Hook Type section
    hook_type = next((s for s in sections if s.name == "Hook Type"), None)
    if hook_type:
        body = hook_type.content
        if "| Hook |" not in body:
            result.errors.append(
                "## Hook Type must have a table with Hook, Schedule/Trigger columns"
            )
    
    # Validate Source System section
    source_system = next((s for s in sections if s.name == "Source System"), None)
    if source_system:
        body = get_section_body(source_system)
        if len(body) < 50:
            result.errors.append(
                "## Source System section is too short. Describe the external system."
            )


# =============================================================================
# Main Entry Point
# =============================================================================

def validate_plugin_type(
    plugin_type: str,
    base_dir: Path,
    verbose: bool,
) -> tuple[int, int, int]:
    """Validate all READMEs of a specific plugin type."""
    config = PLUGIN_CONFIGS[plugin_type]
    plugins_dir = base_dir / config["directory"]
    
    if not plugins_dir.exists():
        print(f"Directory not found: {plugins_dir}")
        return 0, 0, 0
    
    readme_files = sorted(plugins_dir.glob("*/README.md"))
    
    if not readme_files:
        print(f"No README.md files found in {plugins_dir}")
        return 0, 0, 0
    
    print(f"\nValidating {len(readme_files)} {plugin_type} README(s)...")
    
    valid_count = 0
    error_count = 0
    warning_count = 0
    
    for readme_path in readme_files:
        plugin_name = readme_path.parent.name
        result = validate_readme(readme_path, plugin_name, plugin_type, config, base_dir)
        
        status = "✓" if result.is_valid else "✗"
        print(f"  {status} {plugin_name}/README.md")
        
        if verbose:
            print(f"    Title: {result.title or '(missing)'}")
            print(f"    Sections: {[s.name for s in result.sections]}")
        
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
        description="Validate plugin README structure against templates"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed information about each README",
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
    
    total_valid = 0
    total_errors = 0
    total_warnings = 0
    
    for plugin_type in types_to_validate:
        valid, errors, warnings = validate_plugin_type(plugin_type, base_dir, args.verbose)
        total_valid += valid
        total_errors += errors
        total_warnings += warnings
    
    print("\n" + "-" * 60)
    if total_errors == 0:
        if total_warnings > 0:
            print(f"All READMEs valid ({total_warnings} warning(s)).")
        else:
            print("All READMEs follow the template structure.")
        sys.exit(0)
    else:
        print(f"Validation failed: {total_errors} error(s), {total_warnings} warning(s)")
        sys.exit(1)


if __name__ == "__main__":
    main()

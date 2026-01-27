#!/usr/bin/env python3
"""
Enforce cataloger README structure based on the template.

This script validates that all cataloger README.md files follow the structure
defined in ai-context/cataloger-README-template.md.

Usage:
    python scripts/enforce_cataloger_readme_structure.py [--verbose]

Options:
    --verbose   Show detailed information about each README
"""

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# Define the expected section order from the template
# Sections marked as optional can be missing without error
TEMPLATE_SECTIONS = [
    {"name": "Overview", "required": True},
    {"name": "Synced Data", "required": True},
    {"name": "Catalogers", "required": False},  # Optional: only if multiple catalogers
    {"name": "Hook Type", "required": True},
    {"name": "Inputs", "required": True},
    {"name": "Secrets", "required": False},  # Optional: only if secrets are needed
    {"name": "Installation", "required": True},
    {"name": "Source System", "required": True},
]

# Section names in order for validation
SECTION_ORDER = [s["name"] for s in TEMPLATE_SECTIONS]
REQUIRED_SECTIONS = {s["name"] for s in TEMPLATE_SECTIONS if s["required"]}

# Validation constraints
ONE_LINER_MIN_LENGTH = 20
ONE_LINER_MAX_LENGTH = 200
OVERVIEW_MIN_SENTENCES = 2
OVERVIEW_MAX_SENTENCES = 5
OVERVIEW_MIN_LENGTH = 100
OVERVIEW_MAX_LENGTH = 800


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
    title: Optional[str] = None
    one_liner: Optional[str] = None
    sections: list[Section] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0


def count_sentences(text: str) -> int:
    """Count approximate number of sentences in text."""
    # Simple sentence counting: split on . ! ? followed by space or end
    sentences = re.split(r'[.!?]+(?:\s|$)', text.strip())
    # Filter out empty strings
    return len([s for s in sentences if s.strip()])


def parse_readme(content: str) -> tuple[Optional[str], Optional[str], list[Section]]:
    """
    Parse a README into its title, one-liner description, and sections.
    
    Returns:
        tuple of (title, one_liner, sections)
    """
    lines = content.split("\n")
    title = None
    one_liner = None
    sections: list[Section] = []
    
    i = 0
    
    # Find title (# heading at start)
    while i < len(lines) and lines[i].strip() == "":
        i += 1
    
    if i < len(lines) and lines[i].startswith("# "):
        title = lines[i][2:].strip()
        i += 1
        
        # Skip empty lines after title
        while i < len(lines) and lines[i].strip() == "":
            i += 1
        
        # Capture one-liner description (non-empty, non-heading line)
        if i < len(lines) and lines[i].strip() and not lines[i].startswith("#"):
            one_liner = lines[i].strip()
    
    # Parse sections
    section_pattern = re.compile(r"^(#{2,6})\s+(.+)$")
    
    current_section_start = None
    current_section_name = None
    current_section_level = None
    in_code_block = False
    
    for line_num, line in enumerate(lines):
        # Track code blocks to ignore headings inside them
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue
        
        if in_code_block:
            continue
        
        match = section_pattern.match(line)
        if match:
            level = len(match.group(1))
            name = match.group(2).strip()
            
            # Only track level-2 sections (## headings)
            if level == 2:
                # Close previous section
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
    
    # Close last section
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
    # Skip the heading line and any empty lines after it
    body_lines = lines[1:]  # Skip ## heading
    return "\n".join(body_lines).strip()


def validate_title(title: str, directory_name: str) -> tuple[bool, str]:
    """
    Validate that title follows the exact format: `directory-name` Cataloger
    
    Returns:
        tuple of (is_valid, error_message)
    """
    expected = f"`{directory_name}` Cataloger"
    if title == expected:
        return True, ""
    return False, f"Title must be exactly '{expected}', got '{title}'"


def extract_path_table_paths(content: str) -> list[str]:
    """Extract paths from the '| Path |' table only, ignoring other tables."""
    lines = content.split("\n")
    in_path_table = False
    paths = []
    
    for line in lines:
        # Check if this is the header of the Path table
        if "| Path |" in line and "| Type |" in line:
            in_path_table = True
            continue
        
        # Skip separator line
        if in_path_table and line.strip().startswith("|--") or line.strip().startswith("| --"):
            continue
        
        # Check if we've left the table (empty line or new heading)
        if in_path_table and (not line.strip() or line.startswith("#")):
            in_path_table = False
            continue
        
        # Extract path from table row
        if in_path_table and line.strip().startswith("|"):
            path_match = re.match(r"^\|\s*`([^`]+)`\s*\|", line)
            if path_match:
                paths.append(path_match.group(1))
    
    return paths


def extract_cataloger_names(content: str) -> list[str]:
    """Extract cataloger names from the Catalogers section table."""
    # Match: | `cataloger-name` | description |
    pattern = re.compile(r"^\|\s*`([^`]+)`\s*\|", re.MULTILINE)
    return pattern.findall(content)


def get_plugin_name_from_yaml(yaml_file: Path) -> Optional[str]:
    """Get the top-level 'name' field from a YAML file."""
    if not yaml_file.exists():
        return None
    
    content = yaml_file.read_text()
    # Match top-level name: field (not indented)
    match = re.search(r"^name:\s*(.+)$", content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return None


def get_cataloger_names_from_yaml(cataloger_dir: Path) -> set[str]:
    """Get cataloger names from lunar-cataloger.yml file."""
    yaml_file = cataloger_dir / "lunar-cataloger.yml"
    if not yaml_file.exists():
        return set()
    
    cataloger_names = set()
    content = yaml_file.read_text()
    
    # Simple YAML parsing - look for "- name: cataloger-name" patterns under catalogers:
    in_catalogers_section = False
    lines = content.split("\n")
    
    for line in lines:
        # Check if we're entering the catalogers section
        if re.match(r"^catalogers:\s*$", line):
            in_catalogers_section = True
            continue
        
        # Check if we're leaving the catalogers section (new top-level key)
        if in_catalogers_section and re.match(r"^[a-zA-Z]", line) and not line.startswith(" "):
            in_catalogers_section = False
            continue
        
        # Extract cataloger names
        if in_catalogers_section:
            match = re.match(r"^\s+-\s*name:\s*(.+)$", line)
            if match:
                cataloger_names.add(match.group(1).strip())
    
    return cataloger_names


def get_inputs_from_yaml(yaml_file: Path) -> tuple[set[str], set[str]]:
    """
    Get input names from a lunar-cataloger.yml file.
    
    Returns:
        tuple of (required_inputs, optional_inputs)
    """
    if not yaml_file.exists():
        return set(), set()
    
    required_inputs = set()
    optional_inputs = set()
    content = yaml_file.read_text()
    
    # Find the inputs: section and extract input names
    # Inputs are defined as top-level keys under "inputs:"
    in_inputs_section = False
    current_input = None
    has_default = False
    lines = content.split("\n")
    
    for line in lines:
        # Check if we're entering the inputs section
        if re.match(r"^inputs:\s*$", line):
            in_inputs_section = True
            continue
        
        # Check if we're leaving the inputs section (new top-level key)
        if in_inputs_section and re.match(r"^[a-zA-Z]", line) and not line.startswith(" "):
            # Save the last input
            if current_input:
                if has_default:
                    optional_inputs.add(current_input)
                else:
                    required_inputs.add(current_input)
            in_inputs_section = False
            continue
        
        # Extract input names (2-space indented keys under inputs:)
        if in_inputs_section:
            match = re.match(r"^  ([a-zA-Z_][a-zA-Z0-9_]*):\s*$", line)
            if match:
                # Save the previous input
                if current_input:
                    if has_default:
                        optional_inputs.add(current_input)
                    else:
                        required_inputs.add(current_input)
                current_input = match.group(1)
                has_default = False
            elif current_input and re.match(r"^\s+default:", line):
                has_default = True
    
    # Save the last input
    if current_input:
        if has_default:
            optional_inputs.add(current_input)
        else:
            required_inputs.add(current_input)
    
    return required_inputs, optional_inputs


@dataclass
class InputInfo:
    """Information about an input parameter."""
    name: str
    required: bool


def extract_inputs(content: str) -> list[InputInfo]:
    """Extract input names and required status from the Inputs section table."""
    inputs = []
    lines = content.split("\n")
    in_table = False
    
    for line in lines:
        # Check if this is the header of the Input table
        if "| Input |" in line and "| Required |" in line:
            in_table = True
            continue
        
        # Skip separator line
        if in_table and (line.strip().startswith("|--") or line.strip().startswith("| --")):
            continue
        
        # Check if we've left the table
        if in_table and (not line.strip() or line.startswith("#")):
            in_table = False
            continue
        
        # Extract input info from table row
        # Format: | `input_name` | Yes/No | default | description |
        if in_table and line.strip().startswith("|"):
            # Split by | and extract columns
            cols = [c.strip() for c in line.split("|")]
            if len(cols) >= 4:  # Empty, Input, Required, Default, Description, Empty
                name_match = re.match(r"`([^`]+)`", cols[1])
                if name_match:
                    name = name_match.group(1)
                    # Handle both "Yes" and "**Yes**" formats
                    required = "yes" in cols[2].lower()
                    inputs.append(InputInfo(name=name, required=required))
    
    return inputs


def validate_readme(
    readme_path: Path,
    cataloger_name: str,
) -> ValidationResult:
    """Validate a README against the template structure."""
    result = ValidationResult(readme_path=readme_path)
    
    try:
        content = readme_path.read_text()
    except Exception as e:
        result.errors.append(f"Failed to read file: {e}")
        return result
    
    title, one_liner, sections = parse_readme(content)
    result.title = title
    result.one_liner = one_liner
    result.sections = sections
    
    # Validate YAML name matches directory name
    cataloger_dir = readme_path.parent
    yaml_file = cataloger_dir / "lunar-cataloger.yml"
    yaml_name = get_plugin_name_from_yaml(yaml_file)
    if yaml_name is None:
        result.errors.append("Missing lunar-cataloger.yml or 'name' field in YAML")
    elif yaml_name != cataloger_name:
        result.errors.append(
            f"YAML 'name: {yaml_name}' does not match directory name '{cataloger_name}'"
        )
    
    # Validate title
    if not title:
        result.errors.append("Missing title (# heading)")
    else:
        # Title must be exactly: `directory-name` Cataloger
        is_valid, error_msg = validate_title(title, cataloger_name)
        if not is_valid:
            result.errors.append(error_msg)
    
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
    
    # Get section names present in the README
    section_names = [s.name for s in sections]
    
    # Check for required sections
    for required in REQUIRED_SECTIONS:
        if required not in section_names:
            result.errors.append(f"Missing required section: ## {required}")
    
    # Check section order
    template_sections_present = [s for s in SECTION_ORDER if s in section_names]
    readme_sections_in_template = [s for s in section_names if s in SECTION_ORDER]
    
    if template_sections_present != readme_sections_in_template:
        result.errors.append(
            f"Sections out of order. Expected: {template_sections_present}, "
            f"Found: {readme_sections_in_template}"
        )
    
    # Check for unknown sections
    unknown_sections = [s for s in section_names if s not in SECTION_ORDER]
    if unknown_sections:
        result.warnings.append(f"Unknown sections (not in template): {unknown_sections}")
    
    # Validate Overview section
    overview = next((s for s in sections if s.name == "Overview"), None)
    if overview:
        body = get_section_body(overview)
        sentence_count = count_sentences(body)
        
        if len(body) < OVERVIEW_MIN_LENGTH:
            result.errors.append(
                f"Overview too short ({len(body)} chars). "
                f"Minimum: {OVERVIEW_MIN_LENGTH} chars"
            )
        if len(body) > OVERVIEW_MAX_LENGTH:
            result.errors.append(
                f"Overview too long ({len(body)} chars). "
                f"Maximum: {OVERVIEW_MAX_LENGTH} chars"
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
    
    # Validate Synced Data section
    synced_data = next((s for s in sections if s.name == "Synced Data"), None)
    if synced_data:
        body = synced_data.content
        
        # Must have a <details> block with example JSON
        if "<details>" not in body:
            result.errors.append(
                "## Synced Data must have a <details> block with example JSON"
            )
        else:
            # Check for proper structure: <details> with <summary> and json code block
            if "<summary>" not in body:
                result.errors.append(
                    "## Synced Data <details> must have a <summary> element"
                )
            if "```json" not in body:
                result.errors.append(
                    "## Synced Data <details> must contain a ```json code block"
                )
        
        # Must have a path table
        if "| Path |" not in body:
            result.errors.append(
                "## Synced Data must have a table with Path, Type, Description columns"
            )
        else:
            # Validate that paths in the Path table start with `.`
            paths = extract_path_table_paths(body)
            invalid_paths = [p for p in paths if not p.startswith(".")]
            if invalid_paths:
                result.errors.append(
                    f"## Synced Data paths must start with '.': {invalid_paths}"
                )
    
    # Get cataloger names from lunar-cataloger.yml for validation
    cataloger_dir = readme_path.parent
    yaml_catalogers = get_cataloger_names_from_yaml(cataloger_dir)
    
    # Validate Catalogers section (when present) has proper table format
    catalogers_section = next((s for s in sections if s.name == "Catalogers"), None)
    
    # If there are multiple catalogers in YAML, Catalogers section is required
    if len(yaml_catalogers) > 1 and not catalogers_section:
        result.errors.append(
            f"## Catalogers section is required since lunar-cataloger.yml has "
            f"{len(yaml_catalogers)} catalogers: {sorted(yaml_catalogers)}"
        )
    
    if catalogers_section:
        body = catalogers_section.content
        # Check for table header with Cataloger and Description columns (flexible spacing)
        has_cataloger_table = re.search(r"\|\s*Cataloger\s*\|.*Description\s*\|", body)
        if not has_cataloger_table:
            result.errors.append(
                "## Catalogers must have a table with Cataloger, Description columns"
            )
        else:
            # Check table has at least one data row (not just header)
            cataloger_names_in_readme = set(extract_cataloger_names(body))
            if not cataloger_names_in_readme:
                result.errors.append(
                    "## Catalogers table must have at least one cataloger listed"
                )
            elif yaml_catalogers:
                # Verify completeness against lunar-cataloger.yml
                missing_from_readme = yaml_catalogers - cataloger_names_in_readme
                extra_in_readme = cataloger_names_in_readme - yaml_catalogers
                
                if missing_from_readme:
                    result.errors.append(
                        f"## Catalogers table is missing catalogers from lunar-cataloger.yml: "
                        f"{sorted(missing_from_readme)}"
                    )
                if extra_in_readme:
                    result.errors.append(
                        f"## Catalogers table lists catalogers not in lunar-cataloger.yml: "
                        f"{sorted(extra_in_readme)}"
                    )
    
    # Validate Hook Type section
    hook_type_section = next((s for s in sections if s.name == "Hook Type"), None)
    if hook_type_section:
        body = hook_type_section.content
        # Must have a table with Hook column
        if "| Hook |" not in body:
            result.errors.append(
                "## Hook Type must have a table with Hook, Schedule/Trigger, Description columns"
            )
    
    # Get inputs from lunar-cataloger.yml for validation
    yaml_file = cataloger_dir / "lunar-cataloger.yml"
    required_yaml_inputs, optional_yaml_inputs = get_inputs_from_yaml(yaml_file)
    all_yaml_inputs = required_yaml_inputs | optional_yaml_inputs
    
    # Validate Inputs section has a table or "no configurable inputs" note
    inputs_section = next((s for s in sections if s.name == "Inputs"), None)
    if inputs_section:
        body = inputs_section.content
        has_table = "| Input |" in body
        # Only consider "no configurable inputs" if there's NO table
        has_no_inputs = not has_table and "no configurable inputs" in body.lower()
        
        if all_yaml_inputs and has_no_inputs:
            result.errors.append(
                f"## Inputs says 'no configurable inputs' but lunar-cataloger.yml has inputs: "
                f"{sorted(all_yaml_inputs)}"
            )
        elif not all_yaml_inputs and has_table:
            result.warnings.append(
                "## Inputs has a table but lunar-cataloger.yml has no inputs defined"
            )
        elif not has_table and not has_no_inputs:
            result.errors.append(
                "## Inputs must have a table or state 'no configurable inputs'"
            )
        elif has_table and all_yaml_inputs:
            # Verify all inputs from YAML are documented
            inputs_in_readme = set(i.name for i in extract_inputs(body))
            
            missing_from_readme = all_yaml_inputs - inputs_in_readme
            extra_in_readme = inputs_in_readme - all_yaml_inputs
            
            if missing_from_readme:
                result.errors.append(
                    f"## Inputs table is missing inputs from lunar-cataloger.yml: "
                    f"{sorted(missing_from_readme)}"
                )
            if extra_in_readme:
                result.errors.append(
                    f"## Inputs table lists inputs not in lunar-cataloger.yml: "
                    f"{sorted(extra_in_readme)}"
                )
            
            # Verify required status matches
            readme_inputs = extract_inputs(body)
            for inp in readme_inputs:
                if inp.name in required_yaml_inputs and not inp.required:
                    result.errors.append(
                        f"## Inputs: '{inp.name}' is required in YAML (no default) "
                        f"but marked as optional in README"
                    )
                elif inp.name in optional_yaml_inputs and inp.required:
                    result.errors.append(
                        f"## Inputs: '{inp.name}' has a default in YAML "
                        f"but marked as required in README"
                    )
    
    # Validate Secrets section - only present if there are actual secrets
    secrets_section = next((s for s in sections if s.name == "Secrets"), None)
    if secrets_section:
        body = get_section_body(secrets_section)
        # Must have at least one bullet point with actual content
        bullet_pattern = re.compile(r"^-\s+`[^`]+`", re.MULTILINE)
        bullets = bullet_pattern.findall(body)
        if not bullets:
            result.errors.append(
                "## Secrets section exists but has no secrets listed. "
                "Remove this section if there are no secrets, or add bullet points: "
                "- `SECRET_NAME` - description"
            )
    
    # Validate Installation section has YAML code block
    installation = next((s for s in sections if s.name == "Installation"), None)
    if installation:
        body = installation.content
        if "```yaml" not in body:
            result.errors.append(
                "## Installation must have a ```yaml code block with example config"
            )
        else:
            # Validate the uses: path matches the cataloger directory
            # Match: uses: github.com/earthly/lunar-lib/catalogers/{name}@...
            uses_pattern = re.compile(
                r"uses:\s*github\.com/earthly/lunar-lib/catalogers/([^@\s]+)"
            )
            uses_match = uses_pattern.search(body)
            if not uses_match:
                result.errors.append(
                    "## Installation must have 'uses: github.com/earthly/lunar-lib/catalogers/{name}@...'"
                )
            else:
                uses_path = uses_match.group(1)
                if uses_path != cataloger_name:
                    result.errors.append(
                        f"## Installation 'uses:' path '{uses_path}' does not match "
                        f"cataloger directory '{cataloger_name}'"
                    )
            
            # Check for include suggestion if multiple catalogers exist
            if catalogers_section:
                cataloger_names = extract_cataloger_names(catalogers_section.content)
                if len(cataloger_names) > 1:
                    # Should have a commented include line with a valid cataloger name
                    include_pattern = re.compile(r"#\s*include:\s*\[([^\]]+)\]")
                    include_match = include_pattern.search(body)
                    if not include_match:
                        result.errors.append(
                            f"## Installation should have '# include: [{cataloger_names[0]}]' "
                            f"comment since there are {len(cataloger_names)} sub-catalogers"
                        )
                    else:
                        # Validate the example cataloger name exists
                        include_example = include_match.group(1).strip()
                        if include_example not in cataloger_names:
                            result.errors.append(
                                f"## Installation include example '{include_example}' is not a valid "
                                f"cataloger. Available: {cataloger_names}"
                            )
            
            # Check for with: section if there are required inputs
            if inputs_section and required_yaml_inputs:
                inputs = extract_inputs(inputs_section.content)
                required_inputs = [i for i in inputs if i.required]
                
                # Required inputs must be uncommented in with: block
                for inp in required_inputs:
                    # Check for uncommented input (not starting with #)
                    req_pattern = re.compile(rf"^\s+{inp.name}:", re.MULTILINE)
                    if not req_pattern.search(body):
                        result.errors.append(
                            f"## Installation must have required input '{inp.name}:' "
                            f"uncommented in with: block"
                        )
    
    # Validate Source System section has content
    source_system = next((s for s in sections if s.name == "Source System"), None)
    if source_system:
        body = get_section_body(source_system)
        if len(body) < 50:
            result.errors.append(
                f"## Source System section is too short ({len(body)} chars). "
                f"Should describe the external system and setup requirements."
            )
    
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Validate cataloger README structure against template"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed information about each README",
    )
    parser.add_argument(
        "--catalogers-dir",
        type=Path,
        default=Path(__file__).parent.parent / "catalogers",
        help="Path to catalogers directory",
    )
    args = parser.parse_args()
    
    catalogers_dir = args.catalogers_dir.resolve()
    if not catalogers_dir.exists():
        print(f"Error: Catalogers directory not found: {catalogers_dir}")
        sys.exit(1)
    
    # Find all README.md files in cataloger directories
    readme_files = sorted(catalogers_dir.glob("*/README.md"))
    
    if not readme_files:
        print(f"No README.md files found in {catalogers_dir}")
        sys.exit(0)
    
    print(f"Validating {len(readme_files)} cataloger README(s)...\n")
    
    all_valid = True
    
    for readme_path in readme_files:
        cataloger_name = readme_path.parent.name
        result = validate_readme(readme_path, cataloger_name)
        
        # Print status
        status = "✓" if result.is_valid else "✗"
        print(f"{status} {cataloger_name}/README.md")
        
        if args.verbose:
            print(f"  Title: {result.title or '(missing)'}")
            one_liner_preview = (
                result.one_liner[:50] + "..." 
                if result.one_liner and len(result.one_liner) > 50 
                else result.one_liner or "(missing)"
            )
            print(f"  One-liner: {one_liner_preview}")
            print(f"  Sections: {[s.name for s in result.sections]}")
        
        if result.errors:
            all_valid = False
            for error in result.errors:
                print(f"  ERROR: {error}")
        
        if result.warnings:
            for warning in result.warnings:
                print(f"  WARNING: {warning}")
        
        print()
    
    # Summary
    print("-" * 60)
    if all_valid:
        print("All cataloger READMEs follow the template structure.")
        sys.exit(0)
    else:
        print("Some cataloger READMEs have structural issues.")
        print("\nExpected section order (from template):")
        for section in TEMPLATE_SECTIONS:
            req = "required" if section["required"] else "optional"
            print(f"  ## {section['name']} ({req})")
        print(f"\nConstraints:")
        print(f"  Title: must match cataloger directory name")
        print(f"  One-liner: {ONE_LINER_MIN_LENGTH}-{ONE_LINER_MAX_LENGTH} chars")
        print(f"  Overview: {OVERVIEW_MIN_SENTENCES}-{OVERVIEW_MAX_SENTENCES} sentences, "
              f"{OVERVIEW_MIN_LENGTH}-{OVERVIEW_MAX_LENGTH} chars")
        print(f"  Synced Data: table with paths starting with '.' + <details> JSON example")
        print(f"  Catalogers: table with Cataloger/Description columns (when present)")
        print(f"  Hook Type: table with Hook/Schedule/Description columns")
        print(f"  Secrets: only include if secrets exist (bullet list)")
        print(f"  Installation: YAML with correct 'uses:' path matching cataloger directory")
        print(f"  Source System: description of external system (min 50 chars)")
        sys.exit(1)


if __name__ == "__main__":
    main()

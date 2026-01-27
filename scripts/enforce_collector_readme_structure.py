#!/usr/bin/env python3
"""
Enforce collector README structure based on the template.

This script validates that all collector README.md files follow the structure
defined in ai-context/collector-README-template.md.

Usage:
    python scripts/enforce_collector_readme_structure.py [--verbose]

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
    {"name": "Collected Data", "required": True},
    {"name": "Collectors", "required": False},  # Optional: only if multiple collectors
    {"name": "Inputs", "required": True},
    {"name": "Secrets", "required": False},  # Optional: only if secrets are needed
    {"name": "Installation", "required": True},
    {"name": "Related Policies", "required": True},
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


def normalize_name(name: str) -> str:
    """Normalize a name for comparison (lowercase, remove common suffixes, hyphens)."""
    name = name.lower()
    # Remove common suffixes/prefixes for collector titles
    for suffix in (" collector", "-collector", "_collector", " vcs", "-vcs", "_vcs"):
        if name.endswith(suffix):
            name = name[:-len(suffix)]
    # Replace hyphens/underscores with nothing for comparison
    name = name.replace("-", "").replace("_", "")
    return name


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


def extract_collector_names(content: str) -> list[str]:
    """Extract collector names from the Collectors section table."""
    # Match: | `collector-name` | description |
    pattern = re.compile(r"^\|\s*`([^`]+)`\s*\|", re.MULTILINE)
    return pattern.findall(content)


def get_collector_names_from_yaml(collector_dir: Path) -> set[str]:
    """Get collector names from lunar-collector.yml file."""
    yaml_file = collector_dir / "lunar-collector.yml"
    if not yaml_file.exists():
        return set()
    
    collector_names = set()
    content = yaml_file.read_text()
    
    # Simple YAML parsing - look for "- name: collector-name" patterns under collectors:
    name_pattern = re.compile(r"^\s*-\s*name:\s*(.+)$", re.MULTILINE)
    matches = name_pattern.findall(content)
    
    for match in matches:
        collector_names.add(match.strip())
    
    return collector_names


def get_inputs_from_yaml(yaml_file: Path) -> set[str]:
    """Get input names from a lunar-collector.yml file."""
    if not yaml_file.exists():
        return set()
    
    input_names = set()
    content = yaml_file.read_text()
    
    # Find the inputs: section and extract input names
    # Inputs are defined as top-level keys under "inputs:"
    in_inputs_section = False
    lines = content.split("\n")
    
    for line in lines:
        # Check if we're entering the inputs section
        if re.match(r"^inputs:\s*$", line):
            in_inputs_section = True
            continue
        
        # Check if we're leaving the inputs section (new top-level key)
        if in_inputs_section and re.match(r"^[a-zA-Z]", line) and not line.startswith(" "):
            in_inputs_section = False
            continue
        
        # Extract input names (2-space indented keys under inputs:)
        if in_inputs_section:
            match = re.match(r"^  ([a-zA-Z_][a-zA-Z0-9_]*):\s*$", line)
            if match:
                input_names.add(match.group(1))
    
    return input_names


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
                    required = cols[2].lower() == "yes"
                    inputs.append(InputInfo(name=name, required=required))
    
    return inputs


def validate_readme(
    readme_path: Path,
    collector_name: str,
    policies_dir: Path,
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
    
    # Validate title
    if not title:
        result.errors.append("Missing title (# heading)")
    else:
        # Title must relate to the collector directory name
        normalized_title = normalize_name(title)
        normalized_dir = normalize_name(collector_name)
        if normalized_title != normalized_dir:
            result.errors.append(
                f"Title '{title}' does not match collector directory '{collector_name}'. "
                f"Expected title like '{collector_name}' or '{collector_name.title()} Collector'"
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
    
    # Validate Collected Data section
    collected_data = next((s for s in sections if s.name == "Collected Data"), None)
    if collected_data:
        body = collected_data.content
        
        # Must have a <details> block with example JSON
        if "<details>" not in body:
            result.errors.append(
                "## Collected Data must have a <details> block with example JSON"
            )
        else:
            # Check for proper structure: <details> with <summary> and json code block
            if "<summary>" not in body:
                result.errors.append(
                    "## Collected Data <details> must have a <summary> element"
                )
            if "```json" not in body:
                result.errors.append(
                    "## Collected Data <details> must contain a ```json code block"
                )
        
        # Must have a path table
        if "| Path |" not in body:
            result.errors.append(
                "## Collected Data must have a table with Path, Type, Description columns"
            )
        else:
            # Validate that paths in the Path table start with `.`
            paths = extract_path_table_paths(body)
            invalid_paths = [p for p in paths if not p.startswith(".")]
            if invalid_paths:
                result.errors.append(
                    f"## Collected Data paths must start with '.': {invalid_paths}"
                )
    
    # Get collector names from lunar-collector.yml for validation
    collector_dir = readme_path.parent
    yaml_collectors = get_collector_names_from_yaml(collector_dir)
    
    # Validate Collectors section (when present) has proper table format
    collectors_section = next((s for s in sections if s.name == "Collectors"), None)
    
    # If there are multiple collectors in YAML, Collectors section is required
    if len(yaml_collectors) > 1 and not collectors_section:
        result.errors.append(
            f"## Collectors section is required since lunar-collector.yml has "
            f"{len(yaml_collectors)} collectors: {sorted(yaml_collectors)}"
        )
    
    if collectors_section:
        body = collectors_section.content
        # Check for table header with Collector and Description columns (flexible spacing)
        has_collector_table = re.search(r"\|\s*Collector\s*\|.*Description\s*\|", body)
        if not has_collector_table:
            result.errors.append(
                "## Collectors must have a table with Collector, Description columns"
            )
        else:
            # Check table has at least one data row (not just header)
            collector_names_in_readme = set(extract_collector_names(body))
            if not collector_names_in_readme:
                result.errors.append(
                    "## Collectors table must have at least one collector listed"
                )
            elif yaml_collectors:
                # Verify completeness against lunar-collector.yml
                missing_from_readme = yaml_collectors - collector_names_in_readme
                extra_in_readme = collector_names_in_readme - yaml_collectors
                
                if missing_from_readme:
                    result.errors.append(
                        f"## Collectors table is missing collectors from lunar-collector.yml: "
                        f"{sorted(missing_from_readme)}"
                    )
                if extra_in_readme:
                    result.errors.append(
                        f"## Collectors table lists collectors not in lunar-collector.yml: "
                        f"{sorted(extra_in_readme)}"
                    )
    
    # Get inputs from lunar-collector.yml for validation
    yaml_file = collector_dir / "lunar-collector.yml"
    yaml_inputs = get_inputs_from_yaml(yaml_file)
    
    # Validate Inputs section has a table or "no configurable inputs" note
    inputs_section = next((s for s in sections if s.name == "Inputs"), None)
    if inputs_section:
        body = inputs_section.content
        has_table = "| Input |" in body
        # Only consider "no configurable inputs" if there's NO table
        has_no_inputs = not has_table and "no configurable inputs" in body.lower()
        
        if yaml_inputs and has_no_inputs:
            result.errors.append(
                f"## Inputs says 'no configurable inputs' but lunar-collector.yml has inputs: "
                f"{sorted(yaml_inputs)}"
            )
        elif not yaml_inputs and has_table:
            result.warnings.append(
                "## Inputs has a table but lunar-collector.yml has no inputs defined"
            )
        elif not has_table and not has_no_inputs:
            result.errors.append(
                "## Inputs must have a table or state 'no configurable inputs'"
            )
        elif has_table and yaml_inputs:
            # Verify all inputs from YAML are documented
            inputs_in_readme = set(i.name for i in extract_inputs(body))
            
            missing_from_readme = yaml_inputs - inputs_in_readme
            extra_in_readme = inputs_in_readme - yaml_inputs
            
            if missing_from_readme:
                result.errors.append(
                    f"## Inputs table is missing inputs from lunar-collector.yml: "
                    f"{sorted(missing_from_readme)}"
                )
            if extra_in_readme:
                result.errors.append(
                    f"## Inputs table lists inputs not in lunar-collector.yml: "
                    f"{sorted(extra_in_readme)}"
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
            # Validate the uses: path matches the collector directory
            # Match: uses: github.com/earthly/lunar-lib/collectors/{name}@...
            uses_pattern = re.compile(
                r"uses:\s*github\.com://earthly/lunar-lib/collectors/([^@\s]+)"
            )
            uses_match = uses_pattern.search(body)
            if not uses_match:
                result.errors.append(
                    "## Installation must have 'uses: github.com://earthly/lunar-lib/collectors/{name}@...'"
                )
            else:
                uses_path = uses_match.group(1)
                if uses_path != collector_name:
                    result.errors.append(
                        f"## Installation 'uses:' path '{uses_path}' does not match "
                        f"collector directory '{collector_name}'"
                    )
            
            # Check for include suggestion if multiple collectors exist
            if collectors_section:
                collector_names = extract_collector_names(collectors_section.content)
                if len(collector_names) > 1:
                    # Should have a commented include line with a valid collector name
                    include_pattern = re.compile(r"#\s*include:\s*\[([^\]]+)\]")
                    include_match = include_pattern.search(body)
                    if not include_match:
                        result.errors.append(
                            f"## Installation should have '# include: [{collector_names[0]}]' "
                            f"comment since there are {len(collector_names)} sub-collectors"
                        )
                    else:
                        # Validate the example collector name exists
                        include_example = include_match.group(1).strip()
                        if include_example not in collector_names:
                            result.errors.append(
                                f"## Installation include example '{include_example}' is not a valid "
                                f"collector. Available: {collector_names}"
                            )
            
            # Check for with: section if there are inputs
            if inputs_section:
                inputs = extract_inputs(inputs_section.content)
                if inputs:
                    required_inputs = [i for i in inputs if i.required]
                    optional_inputs = [i for i in inputs if not i.required]
                    
                    # Required inputs must be uncommented in with: block
                    for inp in required_inputs:
                        # Check for uncommented input (not starting with #)
                        req_pattern = re.compile(rf"^\s+{inp.name}:", re.MULTILINE)
                        if not req_pattern.search(body):
                            result.errors.append(
                                f"## Installation must have required input '{inp.name}:' "
                                f"uncommented in with: block"
                            )
                    
                    # Optional inputs should be shown as comments
                    if optional_inputs:
                        has_with_section = "with:" in body or "# with:" in body
                        if not has_with_section:
                            result.errors.append(
                                "## Installation should have a 'with:' section (commented or not) "
                                "showing available optional inputs"
                            )
                        else:
                            # Check that all optional inputs are shown as comments
                            missing_optional = []
                            for inp in optional_inputs:
                                # Look for commented input: #   input_name: or # input_name:
                                opt_pattern = re.compile(rf"#\s*{inp.name}:", re.MULTILINE)
                                if not opt_pattern.search(body):
                                    missing_optional.append(inp.name)
                            if missing_optional:
                                result.errors.append(
                                    f"## Installation should show optional inputs as comments: "
                                    f"{missing_optional}"
                                )
    
    # Validate Related Policies section
    related_policies = next((s for s in sections if s.name == "Related Policies"), None)
    if related_policies:
        body = get_section_body(related_policies)
        
        # Must have either "None." or a bulleted list with markdown links
        has_none = body.strip().lower() in ("none.", "none")
        
        # Check for markdown links in bullet points: - [`name`](url) or - [name](url)
        link_pattern = re.compile(r"^-\s+\[.*?\]\(.*?\)", re.MULTILINE)
        links = link_pattern.findall(body)
        
        if not has_none and not links:
            result.errors.append(
                "## Related Policies must have either 'None.' or a bulleted list "
                "with markdown links: - [`policy-name`](url) - description"
            )
        
        # Validate that linked policies actually exist
        if links and policies_dir.exists():
            # Extract policy names from links
            # Match: [name](https://github.com/earthly/lunar-lib/tree/main/policies/{policy})
            policy_link_pattern = re.compile(
                r"\[.*?\]\(https://github\.com/earthly/lunar-lib/tree/main/policies/([^/)]+)"
            )
            linked_policies = policy_link_pattern.findall(body)
            
            existing_policies = {d.name for d in policies_dir.iterdir() if d.is_dir()}
            missing_policies = [p for p in linked_policies if p not in existing_policies]
            
            if missing_policies:
                result.errors.append(
                    f"## Related Policies links to non-existent policies: {missing_policies}. "
                    f"Available: {sorted(existing_policies)}"
                )
    
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Validate collector README structure against template"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed information about each README",
    )
    parser.add_argument(
        "--collectors-dir",
        type=Path,
        default=Path(__file__).parent.parent / "collectors",
        help="Path to collectors directory",
    )
    args = parser.parse_args()
    
    collectors_dir = args.collectors_dir.resolve()
    if not collectors_dir.exists():
        print(f"Error: Collectors directory not found: {collectors_dir}")
        sys.exit(1)
    
    # Policies directory is sibling to collectors
    policies_dir = collectors_dir.parent / "policies"
    
    # Find all README.md files in collector directories
    readme_files = sorted(collectors_dir.glob("*/README.md"))
    
    if not readme_files:
        print(f"No README.md files found in {collectors_dir}")
        sys.exit(0)
    
    print(f"Validating {len(readme_files)} collector README(s)...\n")
    
    all_valid = True
    
    for readme_path in readme_files:
        collector_name = readme_path.parent.name
        result = validate_readme(readme_path, collector_name, policies_dir)
        
        # Print status
        status = "✓" if result.is_valid else "✗"
        print(f"{status} {collector_name}/README.md")
        
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
        print("All collector READMEs follow the template structure.")
        sys.exit(0)
    else:
        print("Some collector READMEs have structural issues.")
        print("\nExpected section order (from template):")
        for section in TEMPLATE_SECTIONS:
            req = "required" if section["required"] else "optional"
            print(f"  ## {section['name']} ({req})")
        print(f"\nConstraints:")
        print(f"  Title: must match collector directory name")
        print(f"  One-liner: {ONE_LINER_MIN_LENGTH}-{ONE_LINER_MAX_LENGTH} chars")
        print(f"  Overview: {OVERVIEW_MIN_SENTENCES}-{OVERVIEW_MAX_SENTENCES} sentences, "
              f"{OVERVIEW_MIN_LENGTH}-{OVERVIEW_MAX_LENGTH} chars")
        print(f"  Collected Data: table with paths starting with '.' + <details> JSON example")
        print(f"  Collectors: table with Collector/Description columns (when present)")
        print(f"  Secrets: only include if secrets exist (bullet list)")
        print(f"  Installation: YAML with correct 'uses:' path matching collector directory")
        print(f"  Related Policies: 'None.' or bulleted links to existing policies")
        sys.exit(1)


if __name__ == "__main__":
    main()

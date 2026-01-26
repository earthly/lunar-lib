#!/usr/bin/env python3
"""
Enforce policy README structure based on the template.

This script validates that all policy README.md files follow the structure
defined in ai-context/policy-README-template.md.

Usage:
    python scripts/enforce_policy_readme_structure.py [--verbose]

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
    {"name": "Policies", "required": True},
    {"name": "Required Data", "required": True},
    {"name": "Inputs", "required": True},
    {"name": "Installation", "required": True},
    {"name": "Examples", "required": True},
    {"name": "Related Collectors", "required": True},
    {"name": "Remediation", "required": True},
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
    sentences = re.split(r'[.!?]+(?:\s|$)', text.strip())
    return len([s for s in sentences if s.strip()])


def validate_title(title: str, directory_name: str) -> tuple[bool, str]:
    """
    Validate that title follows the exact format: `directory-name` Policies
    
    Returns:
        tuple of (is_valid, error_message)
    """
    expected = f"`{directory_name}` Policies"
    if title == expected:
        return True, ""
    return False, f"Title must be exactly '{expected}', got '{title}'"


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


def extract_policy_names(content: str) -> list[str]:
    """Extract policy names from the Policies section table."""
    # Match: | `policy-name` | description |
    pattern = re.compile(r"^\|\s*`([^`]+)`\s*\|", re.MULTILINE)
    return pattern.findall(content)


def extract_path_table_paths(content: str) -> list[str]:
    """Extract paths from the '| Path |' table."""
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
    has_required_column = False
    
    for line in lines:
        # Check if this is the header of the Input table
        if "| Input |" in line:
            in_table = True
            has_required_column = "| Required |" in line
            continue
        
        if in_table and (line.strip().startswith("|--") or line.strip().startswith("| --")):
            continue
        
        if in_table and (not line.strip() or line.startswith("#")):
            in_table = False
            continue
        
        if in_table and line.strip().startswith("|"):
            cols = [c.strip() for c in line.split("|")]
            if len(cols) >= 3:
                name_match = re.match(r"`([^`]+)`", cols[1])
                if name_match:
                    name = name_match.group(1)
                    # Determine if required based on column structure
                    if has_required_column and len(cols) >= 4:
                        required = cols[2].lower() == "yes"
                    else:
                        required = False  # If no Required column, assume optional
                    inputs.append(InputInfo(name=name, required=required))
    
    return inputs


def get_section_body(section: Section) -> str:
    """Extract the body content of a section (excluding the heading)."""
    lines = section.content.split("\n")
    body_lines = lines[1:]
    return "\n".join(body_lines).strip()


def parse_readme(content: str) -> tuple[Optional[str], Optional[str], list[Section]]:
    """Parse a README into its title, one-liner description, and sections."""
    lines = content.split("\n")
    title = None
    one_liner = None
    sections: list[Section] = []
    
    i = 0
    
    while i < len(lines) and lines[i].strip() == "":
        i += 1
    
    if i < len(lines) and lines[i].startswith("# "):
        title = lines[i][2:].strip()
        i += 1
        
        while i < len(lines) and lines[i].strip() == "":
            i += 1
        
        if i < len(lines) and lines[i].strip() and not lines[i].startswith("#"):
            one_liner = lines[i].strip()
    
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


def get_policy_names_from_yaml(policy_dir: Path) -> set[str]:
    """Get policy names from lunar-policy.yml file."""
    yaml_file = policy_dir / "lunar-policy.yml"
    if not yaml_file.exists():
        return set()
    
    policy_names = set()
    content = yaml_file.read_text()
    
    # Simple YAML parsing - look for "- name: policy-name" patterns
    name_pattern = re.compile(r"^\s*-\s*name:\s*(.+)$", re.MULTILINE)
    matches = name_pattern.findall(content)
    
    for match in matches:
        policy_names.add(match.strip())
    
    return policy_names


def get_inputs_from_yaml(yaml_file: Path) -> set[str]:
    """Get input names from a lunar-policy.yml or lunar-collector.yml file."""
    if not yaml_file.exists():
        return set()
    
    input_names = set()
    content = yaml_file.read_text()
    
    # Find the inputs: section and extract input names
    # Inputs are defined as top-level keys under "inputs:"
    # Format:
    # inputs:
    #   input_name:
    #     description: ...
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


def validate_readme(
    readme_path: Path,
    policy_name: str,
    collectors_dir: Path,
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
    policy_dir = readme_path.parent
    yaml_file = policy_dir / "lunar-policy.yml"
    yaml_name = get_plugin_name_from_yaml(yaml_file)
    if yaml_name is None:
        result.errors.append("Missing lunar-policy.yml or 'name' field in YAML")
    elif yaml_name != policy_name:
        result.errors.append(
            f"YAML 'name: {yaml_name}' does not match directory name '{policy_name}'"
        )
    
    # Validate title
    if not title:
        result.errors.append("Missing title (# heading)")
    else:
        # Title must be exactly: `directory-name` Policies
        is_valid, error_msg = validate_title(title, policy_name)
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
    
    # Validate Policies section
    policies_section = next((s for s in sections if s.name == "Policies"), None)
    if policies_section:
        body = policies_section.content
        # Check for table header with Policy and Description columns
        has_policy_table = re.search(r"\|\s*Policy\s*\|.*Description\s*\|", body)
        if not has_policy_table:
            result.errors.append(
                "## Policies must have a table with Policy, Description columns"
            )
        else:
            policy_names_in_readme = set(extract_policy_names(body))
            if not policy_names_in_readme:
                result.errors.append(
                    "## Policies table must have at least one policy listed"
                )
            else:
                # Verify all policies from lunar-policy.yml are documented
                policy_dir = readme_path.parent
                actual_policies = get_policy_names_from_yaml(policy_dir)
                
                if actual_policies:
                    missing_from_readme = actual_policies - policy_names_in_readme
                    extra_in_readme = policy_names_in_readme - actual_policies
                    
                    if missing_from_readme:
                        result.errors.append(
                            f"## Policies table is missing policies from lunar-policy.yml: "
                            f"{sorted(missing_from_readme)}"
                        )
                    if extra_in_readme:
                        result.errors.append(
                            f"## Policies table lists policies not in lunar-policy.yml: "
                            f"{sorted(extra_in_readme)}"
                        )
                else:
                    result.warnings.append(
                        "Could not find or parse lunar-policy.yml to verify policy completeness"
                    )
    
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
    
    # Get inputs from lunar-policy.yml for validation
    policy_dir = readme_path.parent
    yaml_file = policy_dir / "lunar-policy.yml"
    yaml_inputs = get_inputs_from_yaml(yaml_file)
    
    # Validate Inputs section
    inputs_section = next((s for s in sections if s.name == "Inputs"), None)
    if inputs_section:
        body = inputs_section.content
        has_table = "| Input |" in body
        # Only consider "no configurable inputs" if there's NO table
        has_no_inputs = not has_table and "no configurable inputs" in body.lower()
        
        if yaml_inputs and has_no_inputs:
            result.errors.append(
                f"## Inputs says 'no configurable inputs' but lunar-policy.yml has inputs: "
                f"{sorted(yaml_inputs)}"
            )
        elif not yaml_inputs and has_table:
            result.warnings.append(
                "## Inputs has a table but lunar-policy.yml has no inputs defined"
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
                    f"## Inputs table is missing inputs from lunar-policy.yml: "
                    f"{sorted(missing_from_readme)}"
                )
            if extra_in_readme:
                result.errors.append(
                    f"## Inputs table lists inputs not in lunar-policy.yml: "
                    f"{sorted(extra_in_readme)}"
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
            # Validate the uses: path matches the policy directory
            # Match: uses: github://earthly/lunar-lib/policies/{name}@...
            uses_pattern = re.compile(
                r"uses:\s*github://earthly/lunar-lib/policies/([^@\s]+)"
            )
            uses_match = uses_pattern.search(body)
            if not uses_match:
                result.errors.append(
                    "## Installation must have 'uses: github://earthly/lunar-lib/policies/{name}@...'"
                )
            else:
                uses_path = uses_match.group(1)
                if uses_path != policy_name:
                    result.errors.append(
                        f"## Installation 'uses:' path '{uses_path}' does not match "
                        f"policy directory '{policy_name}'"
                    )
            
            # Check for enforcement line
            if "enforcement:" not in body:
                result.errors.append(
                    "## Installation must show 'enforcement:' option"
                )
            
            # Check for include suggestion if multiple policies exist
            if policies_section:
                policy_names_list = extract_policy_names(policies_section.content)
                if len(policy_names_list) > 1:
                    # Match both formats: include: [...] or include:\n  - item
                    include_pattern = re.compile(r"#?\s*include:", re.MULTILINE)
                    if not include_pattern.search(body):
                        result.errors.append(
                            f"## Installation should have 'include:' (commented or not) "
                            f"since there are {len(policy_names_list)} policies"
                        )
            
            # Check for with: section if there are inputs
            if inputs_section:
                inputs = extract_inputs(inputs_section.content)
                if inputs:
                    required_inputs = [i for i in inputs if i.required]
                    optional_inputs = [i for i in inputs if not i.required]
                    
                    for inp in required_inputs:
                        req_pattern = re.compile(rf"^\s+{inp.name}:", re.MULTILINE)
                        if not req_pattern.search(body):
                            result.errors.append(
                                f"## Installation must have required input '{inp.name}:' "
                                f"uncommented in with: block"
                            )
                    
                    if optional_inputs:
                        has_with_section = "with:" in body or "# with:" in body
                        if not has_with_section:
                            result.errors.append(
                                "## Installation should have a 'with:' section (commented or not) "
                                "showing available optional inputs"
                            )
                        else:
                            # Check that optional inputs are shown (commented OR uncommented)
                            missing_optional = []
                            for inp in optional_inputs:
                                # Match either commented or uncommented
                                opt_pattern = re.compile(rf"#?\s*{inp.name}:", re.MULTILINE)
                                if not opt_pattern.search(body):
                                    missing_optional.append(inp.name)
                            if missing_optional:
                                result.errors.append(
                                    f"## Installation should show optional inputs: "
                                    f"{missing_optional}"
                                )
    
    # Validate Examples section
    examples = next((s for s in sections if s.name == "Examples"), None)
    if examples:
        body = examples.content
        
        # Must have passing example
        has_passing = "passing" in body.lower()
        if not has_passing:
            result.errors.append(
                "## Examples must have a 'Passing Example' subsection"
            )
        
        # Must have failing example
        has_failing = "failing" in body.lower()
        if not has_failing:
            result.errors.append(
                "## Examples must have a 'Failing Example' subsection"
            )
        
        # Must have JSON code blocks
        if "```json" not in body:
            result.errors.append(
                "## Examples must have ```json code blocks showing Component JSON"
            )
    
    # Validate Related Collectors section
    related_collectors = next((s for s in sections if s.name == "Related Collectors"), None)
    if related_collectors:
        body = get_section_body(related_collectors)
        
        # Check for markdown links in bullet points
        link_pattern = re.compile(r"^-\s+\[.*?\]\(.*?\)", re.MULTILINE)
        links = link_pattern.findall(body)
        
        if not links:
            result.errors.append(
                "## Related Collectors must have a bulleted list with markdown links: "
                "- [`collector-name`](url) - description"
            )
        
        # Validate that linked collectors actually exist
        if links and collectors_dir.exists():
            collector_link_pattern = re.compile(
                r"\[.*?\]\(https://github\.com/earthly/lunar-lib/tree/main/collectors/([^/)]+)"
            )
            linked_collectors = collector_link_pattern.findall(body)
            
            existing_collectors = {d.name for d in collectors_dir.iterdir() if d.is_dir()}
            missing_collectors = [c for c in linked_collectors if c not in existing_collectors]
            
            if missing_collectors:
                result.errors.append(
                    f"## Related Collectors links to non-existent collectors: {missing_collectors}. "
                    f"Available: {sorted(existing_collectors)}"
                )
    
    # Validate Remediation section
    remediation = next((s for s in sections if s.name == "Remediation"), None)
    if remediation:
        body = get_section_body(remediation)
        if len(body) < 50:
            result.errors.append(
                "## Remediation section is too short. Provide actionable steps to fix failures."
            )
    
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Validate policy README structure against template"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed information about each README",
    )
    parser.add_argument(
        "--policies-dir",
        type=Path,
        default=Path(__file__).parent.parent / "policies",
        help="Path to policies directory",
    )
    args = parser.parse_args()
    
    policies_dir = args.policies_dir.resolve()
    if not policies_dir.exists():
        print(f"Error: Policies directory not found: {policies_dir}")
        sys.exit(1)
    
    collectors_dir = policies_dir.parent / "collectors"
    
    readme_files = sorted(policies_dir.glob("*/README.md"))
    
    if not readme_files:
        print(f"No README.md files found in {policies_dir}")
        sys.exit(0)
    
    print(f"Validating {len(readme_files)} policy README(s)...\n")
    
    all_valid = True
    
    for readme_path in readme_files:
        policy_name = readme_path.parent.name
        result = validate_readme(readme_path, policy_name, collectors_dir)
        
        status = "✓" if result.is_valid else "✗"
        print(f"{status} {policy_name}/README.md")
        
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
    
    print("-" * 60)
    if all_valid:
        print("All policy READMEs follow the template structure.")
        sys.exit(0)
    else:
        print("Some policy READMEs have structural issues.")
        print("\nExpected section order (from template):")
        for section in TEMPLATE_SECTIONS:
            req = "required" if section["required"] else "optional"
            print(f"  ## {section['name']} ({req})")
        print(f"\nConstraints:")
        print(f"  Title: must match policy directory name")
        print(f"  One-liner: {ONE_LINER_MIN_LENGTH}-{ONE_LINER_MAX_LENGTH} chars")
        print(f"  Overview: {OVERVIEW_MIN_SENTENCES}-{OVERVIEW_MAX_SENTENCES} sentences, "
              f"{OVERVIEW_MIN_LENGTH}-{OVERVIEW_MAX_LENGTH} chars")
        print(f"  Policies: table with Policy/Description columns")
        print(f"  Required Data: table with paths starting with '.'")
        print(f"  Installation: YAML with correct 'uses:' path + enforcement option")
        print(f"  Examples: Passing + Failing examples with JSON")
        print(f"  Related Collectors: bulleted links to existing collectors")
        print(f"  Remediation: actionable steps to fix failures")
        sys.exit(1)


if __name__ == "__main__":
    main()

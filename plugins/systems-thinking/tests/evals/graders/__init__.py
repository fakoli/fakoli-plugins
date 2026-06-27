"""Graders for systems-thinking eval framework.

Each grader returns a result dict with at minimum:
    - "pass": bool
    - "score": float (0.0 to 1.0)

Additional fields vary by grader type.
"""

from .composite import grade_composite
from .cross_reference_consistency import grade_cross_reference_consistency
from .evidence_labels import grade_evidence_labels
from .file_exists import grade_files_exist
from .forbidden_check import grade_no_forbidden_files, grade_no_forbidden_patterns
from .quantitative_claims import grade_quantitative_claims
from .schema_match import grade_json_schema, grade_markdown_structure
from .section_check import grade_sections
from .source_anchor_coverage import grade_source_anchor_coverage

__all__ = [
    "grade_files_exist",
    "grade_sections",
    "grade_json_schema",
    "grade_markdown_structure",
    "grade_no_forbidden_patterns",
    "grade_no_forbidden_files",
    "grade_composite",
    "grade_source_anchor_coverage",
    "grade_evidence_labels",
    "grade_quantitative_claims",
    "grade_cross_reference_consistency",
]

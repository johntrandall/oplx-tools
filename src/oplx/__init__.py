"""oplx-tools: generate, lint, and parse OmniPlan .oplx files.

See https://github.com/johntrandall/oplx-format for the spec this implements.
"""

from .generate import from_yaml, from_yaml_file, generate
from .lint import LintFinding, lint
from .models import Assignment, Attachment, Dependency, Project, Resource, Scenario, Task
from .parse import parse

__version__ = "0.2.0"

__all__ = [
    "Assignment",
    "Attachment",
    "Dependency",
    "LintFinding",
    "Project",
    "Resource",
    "Scenario",
    "Task",
    "__version__",
    "from_yaml",
    "from_yaml_file",
    "generate",
    "lint",
    "parse",
]

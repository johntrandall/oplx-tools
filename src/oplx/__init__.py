"""oplx-tools: generate, lint, and parse OmniPlan .oplx files.

See https://github.com/johntrandall/oplx-format for the spec this implements.
"""

from .generate import generate
from .lint import LintFinding, lint
from .models import Assignment, Dependency, Project, Resource, Scenario, Task
from .parse import parse

__version__ = "0.1.1"

__all__ = [
    "Assignment",
    "Dependency",
    "LintFinding",
    "Project",
    "Resource",
    "Scenario",
    "Task",
    "__version__",
    "generate",
    "lint",
    "parse",
]

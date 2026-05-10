from dataclasses import dataclass, field
from typing import Optional

@dataclass
class TaskMeta:
    task_id: str
    root_path: str
    dry_run: bool = True
    status: str = "created"
    created_at: str = ""
    updated_at: str = ""

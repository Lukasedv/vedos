"""Simple in-memory store for processing jobs and intermediate results."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from vedos.models import ProcessingConfig


@dataclass
class ProcessingJob:
    job_id: str
    config: ProcessingConfig
    status: str = "queued"
    progress: float = 0.0
    current_file: Optional[str] = None
    images: dict[int, np.ndarray] = field(default_factory=dict)
    corrected_images: dict[int, np.ndarray] = field(default_factory=dict)
    preview_paths: dict[int, str] = field(default_factory=dict)


class JobStore:
    """Simple in-memory store for processing jobs and intermediate results."""

    def __init__(self) -> None:
        self.jobs: dict[str, ProcessingJob] = {}

    def create_job(self, config: ProcessingConfig) -> str:
        """Create a new job and return its ID."""
        job_id = str(uuid.uuid4())
        self.jobs[job_id] = ProcessingJob(job_id=job_id, config=config)
        return job_id

    def get_job(self, job_id: str) -> ProcessingJob:
        """Return the job for *job_id*, or raise KeyError."""
        return self.jobs[job_id]

    def update_status(
        self,
        job_id: str,
        status: str,
        progress: float = 0.0,
        current_file: Optional[str] = None,
    ) -> None:
        job = self.jobs[job_id]
        job.status = status
        job.progress = progress
        job.current_file = current_file

    def store_image(
        self, job_id: str, file_index: int, image_data: np.ndarray
    ) -> None:
        self.jobs[job_id].images[file_index] = image_data

    def get_image(self, job_id: str, file_index: int) -> np.ndarray:
        return self.jobs[job_id].images[file_index]


# Global singleton used by the app
job_store = JobStore()

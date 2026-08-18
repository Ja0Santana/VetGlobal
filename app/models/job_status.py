from enum import Enum


class JobStatus(str, Enum):
    ENQUEUED = "ENQUEUED"
    DONE = "DONE"
    FAILED = "FAILED"

"""Job progress reporting — async skills report progress mid-execution.

    from agentos import progress

    def op_review(document, **params):
        progress.set_job_id(params.get("__job_id__", ""))
        for step in range(total_steps):
            # ... do work ...
            progress.progress(step + 1, total_steps, f"Round {n}: scored {score}/500")

The engine handles the dispatch, emits to JOB_EVENTS, and forwards to
MCP notifications/progress for task-aware clients.
"""

from agentos._bridge import dispatch

_job_id = None


def set_job_id(job_id):
    """Set the current job ID for progress reporting.

    Call this at the start of an async operation with the __job_id__
    injected by the engine into **params.
    """
    global _job_id
    _job_id = job_id


def progress(current, total, message=""):
    """Report progress for the current async job.

    Args:
        current: Current step number (1-indexed).
        total: Total number of steps.
        message: Human-readable progress description.
    """
    dispatch("__progress__", {
        "job_id": _job_id or "",
        "current": current,
        "total": total,
        "message": message,
    })

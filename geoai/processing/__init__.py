"""Fundação de jobs geoespaciais desacoplados da interface."""

from geoai.processing.contract import JOB_TYPES, JobContractError, JobRecord
from geoai.processing.jobs import execute_job
from geoai.processing.ndvi import SENTINEL_SEARCH_POLICY, ndvi_window

__all__ = [
    "JOB_TYPES",
    "JobContractError",
    "JobRecord",
    "SENTINEL_SEARCH_POLICY",
    "execute_job",
    "ndvi_window",
]

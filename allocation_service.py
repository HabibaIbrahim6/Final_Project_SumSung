"""Backward-compatible imports for the allocation service."""

from services.allocation_service import AllocationService, default_matrix, default_ngos, to_item

__all__ = ["AllocationService", "default_matrix", "default_ngos", "to_item"]

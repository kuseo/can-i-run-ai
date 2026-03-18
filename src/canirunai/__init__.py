from .schemas.cpu import CpuCatalog, CpuSpec
from .schemas.gpu import GpuCatalog, GpuSpec
from .schemas.model import ModelCatalog, ModelSpec
from .schemas.score import ScoreReport
from .sdk import CanIRunAI

__all__ = [
    "CanIRunAI",
    "CpuCatalog",
    "CpuSpec",
    "GpuCatalog",
    "GpuSpec",
    "ModelCatalog",
    "ModelSpec",
    "ScoreReport",
]

__version__ = "0.1.0"

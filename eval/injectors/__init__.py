from eval.injectors import clr_text as _clr_text  # noqa: F401  (import registers the injector)
from eval.injectors import loc_drift as _loc_drift  # noqa: F401
from eval.injectors import loc_offset as _loc_offset  # noqa: F401
from eval.injectors import loc_readability as _loc_readability  # noqa: F401
from eval.injectors import loc_shot_change as _loc_shot_change  # noqa: F401
from eval.injectors import loc_term as _loc_term  # noqa: F401
from eval.injectors import plot_layer1 as _plot_layer1  # noqa: F401
from eval.injectors.base import REGISTRY, Injector, Label, Target, get, register, write_labels

__all__ = ["REGISTRY", "Injector", "Label", "Target", "get", "register", "write_labels"]

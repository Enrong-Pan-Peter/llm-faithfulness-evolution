"""Shared evolutionary search loop for the planning and code-repair environments.

The Contexto search lives in ``contexto_solver`` (its own population and game
bookkeeping, kept as submitted). The two newer environments share this loop
instead: one population of candidates, the harmonised settings
(``INITIAL_POPULATION`` = 15, ``SURVIVORS`` = 5, ``OFFSPRING_PER_PARENT`` = 2),
(mu + lambda) survivor selection with the ``random`` and ``report_rewarded``
controls, the S/M/ML/L operator ladder drawn uniformly, self-reports parsed
the Contexto way, three rationale channels for the slot in every mutation
prompt (``inherited``, ``prospective``, ``corrective_hint``, or ``none``),
and one trace format whose events carry the same names and fields as the
Contexto traces plus an ``outcome`` block with the environment's exact grade.

Modules: ``environment`` (what an environment must provide), ``individual``
(the per-candidate record), ``reports`` (self-report parsing with the
environment's bucket vocabulary), ``model`` (model calls through the Contexto
client, plus a scripted stand-in for offline tests), ``settings``, ``loop``
(the search), ``run`` (command line).
"""

from .environment import RATIONALE_CHANNELS, SearchEnvironment
from .individual import Individual
from .loop import EvolutionarySearch, SearchResult
from .settings import SELECTION_CHOICES, SearchSettings

__all__ = [
    "RATIONALE_CHANNELS",
    "SELECTION_CHOICES",
    "EvolutionarySearch",
    "Individual",
    "SearchEnvironment",
    "SearchResult",
    "SearchSettings",
]

"""Settings for the Contexto environment, read from the process environment at import.

Every value below can be set in ``.env`` (loaded once, never overriding variables
that are already exported) or exported in the shell before ``python`` starts.
Command-line flags do not change these; they are read here exactly once.
"""

from __future__ import annotations

import os
from pathlib import Path


def _env_value(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    return int(_env_value(name, str(default)))


def load_dotenv(path: str | Path = ".env") -> None:
    """Load simple KEY=VALUE pairs into the process environment if absent."""
    env_path = Path(path)
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_dotenv()

# --- Paths ------------------------------------------------------------------
TRACE_DIR = _env_value("TRACE_DIR", "traces")
# GloVe vectors are used only by the offline embedding comparison
# (scripts/calibration_glove_comparison.py); the search never loads them.
GLOVE_PATH = _env_value("GLOVE_PATH", "data/glove.6B.300d.txt")

# --- Contexto game service --------------------------------------------------
API_BASE_URL = os.getenv("API_BASE_URL", "https://api.contexto.me/machado/en/game")
API_RATE_LIMIT = float(os.getenv("API_RATE_LIMIT", "0.5"))
# Persistent per-game cache of returned ranks (only definitive "unknown word"
# answers are cached as invalid; transient failures are never cached).
RANK_CACHE_DIR = _env_value("RANK_CACHE_DIR", "data/rank_cache")
RANK_CACHE_ENABLED = _env_bool("RANK_CACHE_ENABLED", True)

# --- Language model serving -------------------------------------------------
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:14b")
OLLAMA_REQUEST_TIMEOUT_SECONDS = _env_int("OLLAMA_REQUEST_TIMEOUT_SECONDS", 900)
# Models used in the submitted Contexto study; the list is informational only
# (any tag the Ollama server has pulled is accepted).
STUDY_OLLAMA_MODELS = ("qwen3:14b", "gemma4:12b", "ministral-3:14b")
# Only for --provider openai / anthropic (not used by the study).
LLM_MODEL = os.getenv("LLM_MODEL", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
LLM_API_KEY = os.getenv("LLM_API_KEY", OPENAI_API_KEY if LLM_PROVIDER == "openai" else ANTHROPIC_API_KEY)
# Parallel model calls when several individuals are queried in one step.
LLM_WORKERS = _env_int("LLM_WORKERS", 4)

# --- Evolutionary search: population settings (shared naming across environments)
# The pool that survivor selection sees is INITIAL_POPULATION at generation 0
# and SURVIVORS + offspring afterwards. Choose the numbers so both are equal:
#   INITIAL_POPULATION == SURVIVORS * OFFSPRING_PER_PARENT + CROSSOVER_CHILDREN + SURVIVORS
# The default 15 = 5 survivors + 5*2 mutation children + 0 crossover children keeps
# the pool at 15 in every generation.
MAX_GENERATIONS = _env_int("MAX_GENERATIONS", 50)
INITIAL_POPULATION = _env_int("INITIAL_POPULATION", 15)
SURVIVORS = _env_int("SURVIVORS", 5)
OFFSPRING_PER_PARENT = _env_int("OFFSPRING_PER_PARENT", 2)
CROSSOVER_CHILDREN = _env_int("CROSSOVER_CHILDREN", 0)
# Words proposed with each new category (graded immediately; they define the
# individual's fitness).
WORDS_PER_INDIVIDUAL = _env_int("WORDS_PER_INDIVIDUAL", 3)
# When on, surviving parents also propose PARENT_REFRESH_WORDS new words each
# generation (the submitted Contexto study did this, so a parent's fitness kept
# improving). Off means fitness is fixed at birth, as in the planning and code
# environments.
PARENT_REFRESH = _env_bool("PARENT_REFRESH", False)
PARENT_REFRESH_WORDS = _env_int("PARENT_REFRESH_WORDS", 3)

# Survivor selection for ea_semantic_operators.
#   mu_plus_lambda  keep the best SURVIVORS of (parents + offspring); the rest are
#                   removed from the search for good (default).
#   random          keep SURVIVORS individuals drawn uniformly at random from the
#                   same pool (control for the selection-response analysis).
#   report_rewarded keep the SURVIVORS whose self-report agreed best with their
#                   outcome, |predicted_closeness - 1{best rank <= 100}| (an
#                   unparsed report counts as the worst error), ties broken by
#                   rank: the positive control that makes selection act on
#                   reporting quality directly.
SELECTION_CHOICES = ("mu_plus_lambda", "random", "report_rewarded")
SELECTION = _env_value("SELECTION", "mu_plus_lambda")

# Survivor selection for ea_semantic_operators_legacy (reproduces the submitted study).
#   tophalf  keep the best min(half of the pool, LEGACY_SURVIVORS) plus the elite;
#            culled individuals stay in the pool as dormant members.
#   random   the submitted random-selection control.
LEGACY_SELECTION_CHOICES = ("tophalf", "random")
LEGACY_SELECTION = _env_value("LEGACY_SELECTION", "tophalf")
LEGACY_SURVIVORS = 5          # MAX_ACTIVE_HYPOTHESES in the submitted study
LEGACY_ACTIVE_CAP = 15        # SELF_ADAPTIVE_MU in the submitted study
LEGACY_INITIAL_POPULATION = 15

# Operator mix: the four semantic mutation operators are drawn with fixed,
# uniform probability (the only setting used by the submitted study).
OPERATOR_MIX = "fixed_uniform"

# Self-reports appended to every operator prompt (logged only; never used by
# selection or fitness). Off renders the prompts byte-identical to the
# no-report prompts.
SELF_REPORT = _env_bool("SELF_REPORT", False)
# When on, a mutation prompt carries the parent's stored basis words and reason.
# Crossover never inherits.
RATIONALE_INHERITANCE = _env_bool("RATIONALE_INHERITANCE", False)

# Direct baseline (direct_llm_only_sequential): one guess per generation, so
# MAX_GENERATIONS is its guess budget (350 in the submitted study).

# Kept from the original code base: after a word reaches this rank the legacy
# base class would run a local search; every migrated method disables it.
LOCAL_SEARCH_RANK_THRESHOLD = _env_int("LOCAL_SEARCH_RANK_THRESHOLD", 100)

# Random seed for operator sampling and random selection (the model itself is
# unseeded). In batch runs the seed of repeat k is RANDOM_SEED + k.
RANDOM_SEED = os.getenv("RANDOM_SEED")

# Embed the full per-call network log in the NETWORK_METRICS trace event.
PERSIST_CALL_LOG = _env_bool("PERSIST_CALL_LOG", False)

# Trace format version.
#   3: the submitted Contexto study (self_report records with predicted_bucket).
#   4: llm-faithfulness-evolution run records (plain-name settings, serving info,
#      SELECT events carry the selection policy); the event bodies that the
#      analysis reads are unchanged, so format-3 traces still load.
TRACE_FORMAT_VERSION = 4

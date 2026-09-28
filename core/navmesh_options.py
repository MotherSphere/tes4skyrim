"""Which navmesh generator the import stage runs: the lattice or the corridor.

The ``TESCONV_NAVMESH_GENERATOR`` env var carries the choice from convert.py
(``--navmesh-generator``) and the GUI's Settings menu down to the navmesh pool
workers, which inherit the environment.  Anything unset or unrecognised reads
as the default.
"""
import os

NAVMESH_GENERATOR_ENV_VAR = "TESCONV_NAVMESH_GENERATOR"
LATTICE, CORRIDOR = "lattice", "corridor"
GENERATORS = (LATTICE, CORRIDOR)
DEFAULT_GENERATOR = CORRIDOR


def set_navmesh_generator(name) -> None:
    """Pin the generator for this process and its children; None leaves it alone."""
    if name:
        os.environ[NAVMESH_GENERATOR_ENV_VAR] = name


def navmesh_generator() -> str:
    """The generator this process should build navmeshes with."""
    raw = os.environ.get(NAVMESH_GENERATOR_ENV_VAR, "").strip().lower()
    return raw if raw in GENERATORS else DEFAULT_GENERATOR

# Third-party notices

The project uses third-party software listed in `pyproject.toml` and
resolved in `uv.lock`, including Pydantic, MCP, Hatchling, Ruff, Pyright,
pytest, and (for the plugin-load check) the OpenHands SDK/tools. Consult
each distribution's license and notice files for its applicable terms.

The tools image uses the Debian base image and Astral uv distribution
declared in `docker/prodeng-tools.Dockerfile`. GitHub Actions dependencies
are pinned by commit SHA in workflow files. This project does not vendor
their source code.

# erf8_analysis

Brief description: Replace this paragraph with a short overview of your dataset and experiment goals. Include links to data sources if public, and summarize the key questions you answer.

## Quick install

<!-- QUICK_INSTALL_START -->

Run one of these commands in a terminal to clone and set up the project (requires that git is installed):

⚠️ Warning: Only use single line installers like these if you trust the creator of this repository. 

macOS/Linux (curl):

```zsh
curl -fsSL https://sansseriff.github.io/erf8_analysis/dl.sh | bash
```

macOS/Linux (wget):

```zsh
wget -qO- https://sansseriff.github.io/erf8_analysis/dl.sh | bash
```

Windows (PowerShell):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -Command "iwr -UseBasicParsing https://sansseriff.github.io/erf8_analysis/dl.ps1 | iex"
```

### Security: Verify before running

To verify the integrity of `dl.sh` before running it:

```zsh
# Download the script without executing
curl -o dl.sh __RAW_BASE_URL__/dl.sh

# Verify SHA256 hash matches the one below
shasum -a 256 dl.sh

# Inspect the script content
cat dl.sh

# Inspect what will be installed
curl -s __RAW_BASE_URL__/dl-util/install_and_sync.sh | less

# If everything looks good, run it
sh dl.sh
```

Integrity (SHA256 of dl.sh):

```text
ec9a1a78b92909760bdae036ee0efd94b4c9b711491049f425a6278717deb894
```

<!-- QUICK_INSTALL_END -->

## Project notes

- Data: Describe where data comes from and any preprocessing requirements.
- Experiment: Outline the main analysis/experiment steps and expected outputs.
- Environment: Dependencies are managed with uv (see dl-util/install_and_sync.sh for details).

## Next steps

- Edit this README to document your specific analysis.
- See the original template guide in README.template.md for advanced usage and maintenance tips.
- Optionally delete the template_images/ folder in dl-util/ and the README.template.md. (but don't delete other files in dl-util/)

## uv Usage hints

- Add a Python package with `uv add <package-name>`
- Create a local virtual environment `.venv` from the `uv.lock` and `pyproject.toml` files. (already done by install script)
- Run a Python file using the local environment with `uv run <python-file>`
- Run a Jupyter Lab server using the local environment with `uv run --with jupyter jupyter lab`
- Learn more about using uv here: https://docs.astral.sh/uv/guides/projects/#creating-a-new-project

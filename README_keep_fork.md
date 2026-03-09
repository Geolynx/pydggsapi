# Fork Maintenance Workflow

This document describes how to manage this fork of `pydggsapi` to keep it synced with the upstream repository while maintaining Geoinformatics-specific optimizations.

## Branch Strategy

We use a "Downstream Trunk" workflow to isolate upstream updates from our high-performance refactors.

### Core Branches

1.  **`main`**: A pure mirror of the upstream repository (`LandscapeGeoinformatics/pydggsapi`). 
    *   **Rule**: Never commit project-specific code (Pixi, DuckDB, etc.) directly to this branch.
2.  **`fork-main`**: Our internal production branch.
    *   This is where our specialized optimizations live.
    *   All internal releases are built from this branch.
3.  **`wip-*` or `feature/*`**: Short-lived branches for development.
    *   Always branch from `fork-main`.
    *   Merge back into `fork-main` once validated.

---

## Common Workflows

### 1. Syncing with Upstream
When the original project releases updates, pull them into our optimized version:

```bash
# Update the local mirror
git checkout main
git pull upstream main
git push origin main

# Integrate fixes into our optimized trunk
git checkout fork-main
git merge main
```

### 2. Contributing Back (Surgical Bugfixes)
If you fix a general bug (e.g., MVT winding order) that should go back to the original authors:

1.  Create a clean branch from the upstream mirror:
    ```bash
    git checkout main
    git checkout -b fix/bug-description
    ```
2.  Apply **only** the relevant fix (use `git cherry-pick` if the fix was already committed to a WIP branch).
3.  Push and open a Pull Request from this branch.

### 3. Starting New Internal Work
Always base new features on our optimized trunk:

```bash
git checkout fork-main
git checkout -b wip/my-new-optimization
```

---

## Key Maintenance Files

*   **`pixi.lock`**: **MUST** be committed to version control. It ensures that every developer and server uses the exact same binary tools and python packages across Linux, macOS, and Windows.
*   **`dggs_api_config_example.json`**: Use this as a reference for the `DuckDBCollectionProvider` and other performance features.

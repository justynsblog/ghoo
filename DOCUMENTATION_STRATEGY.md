# Documentation Strategy

This document outlines the official strategy for creating, organizing, and maintaining documentation for the `ghoo` project. Its purpose is to ensure that documentation is clear, concise, consistently up-to-date, and easily navigable for both human developers and AI agents.

## Guiding Principles

1.  **Clarity over Exhaustiveness**: Documentation should be easy to understand and to the point.
2.  **Single Source of Truth**: For any given component, there should be one authoritative place to find documentation.
3.  **Documentation as Code**: Documentation is not an afterthought. It lives in the repository and is updated with the code as part of the development workflow.
4.  **Clear Separation of Concerns**: We must clearly distinguish between what is *planned* versus what is *implemented*.

## Documentation Structure

To achieve these goals, we will adopt a two-part structure, separating the project's vision from its current, implemented state.

### 1. The Vision: `spec.md`

-   **Purpose**: The `spec.md` file serves as the single source of truth for the **complete project vision**. It describes how `ghoo` is intended to work once all features are complete.
-   **Content**: It should contain the full CLI command structure, feature descriptions, and architectural goals.
-   **Rule**: This document is forward-looking. It represents the target state, not necessarily the current state of the `main` branch. It is the primary resource for understanding the "why" behind development work.

### 2. The Reality: The `/docs` Directory

-   **Purpose**: This directory contains documentation for features that are **actually implemented, tested, and available** in the current version of the tool. It is the source of truth for "what works right now."
-   **Rule**: Nothing should exist in the `/docs` directory that is not implemented in the codebase.

The `/docs` directory will be organized as follows:

-   **/docs/user-guide/**: Practical, how-to guides for end-users (including developers using the tool). This is where we document implemented commands and workflows.
    -   *Example: `docs/user-guide/creating-issues.md` would be created once the `ghoo create epic|task|sub-task` commands are fully functional.*
-   **/docs/development/**: Documentation for contributors. This includes the development setup, testing strategy, and architectural patterns.
-   **/docs/research/**: An archive for exploratory documents, analyses, and findings. This keeps the root directory clean while preserving historical context.
    -   *Example: `PYGITHUB_GRAPHQL_FINDINGS.md` and `REST_VS_GRAPHQL_ANALYSIS.md` belong here.*

## The Golden Rule: How We Keep Documentation Current

1.  **Documentation is part of the task**: Any code change that alters, adds, or removes user-facing functionality **must** include corresponding updates to the documentation in the `/docs` directory.
2.  **Update within the same commit/PR**: The documentation change must be part of the same commit or Pull Request as the code change it relates to. This ensures the codebase and its documentation never drift apart.
3.  **The `bootstrap-mvp-workflow.md` is temporary**: Once `ghoo` is self-hosting, the process defined in this file will be deprecated and archived. The core principles (e.g., updating docs with code) will be formalized in `docs/development/contributing.md`.

## How to Distinguish Planned vs. Implemented Features

The separation is simple and explicit:

-   **To see what's PLANNED**: Read `spec.md`.
-   **To see what's IMPLEMENTED**: Read the files in `docs/user-guide/`.

If a feature is described in `spec.md` but does not have a corresponding guide in `/docs/user-guide`, it is not yet implemented.

## Naming Conventions

-   **Root Directory**: High-level, project-defining documents should use `ALL_CAPS_SNAKE_CASE.md` or `PascalCase.md` for visibility (e.g., `README.md`, `DOCUMENTATION_STRATEGY.md`).
-   **Subdirectories (`/docs`)**: Granular documentation files should use `lowercase-kebab-case.md` for clarity and consistency within their organized structure (e.g., `docs/user-guide/creating-issues.md`).

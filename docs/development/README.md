# Development Documentation

Welcome to the ghoo development documentation. This guide helps contributors understand the codebase, architecture, and development practices.

## Quick Start for Contributors

New contributor? Follow this path:

1. **[Architecture](./architecture.md)** - Understand the system design
2. **[API Reference](./api-reference.md)** - Learn the core APIs and modules
3. **[Testing](./testing.md)** - Run and write tests
4. **[GraphQL Client Architecture](./graphql-client-architecture.md)** - Understand GitHub integration

## Documentation Overview

### [Architecture](./architecture.md)
**Purpose:** High-level system design and component overview  
**Read this if:** You're new to the codebase or planning major changes  
**Key topics:** System components, data flow, design patterns, module responsibilities

### [API Reference](./api-reference.md)
**Purpose:** Detailed documentation of public APIs and core modules  
**Read this if:** You're implementing features or integrating with ghoo  
**Key topics:** Core module APIs, GraphQLClient, IssueParser, command implementations

### [GraphQL Client Architecture](./graphql-client-architecture.md)
**Purpose:** Deep dive into GitHub GraphQL integration  
**Read this if:** You're working on GitHub API features or troubleshooting integration  
**Key topics:** Query patterns, mutation handling, feature detection, fallback strategies

### [Testing](./testing.md)
**Purpose:** Testing strategy, guidelines, and practices  
**Read this if:** You're writing tests or setting up test environments  
**Key topics:** Test structure, E2E testing with live GitHub, mocking strategies

### [Testing Results](./testing/)
**Purpose:** Historical test execution reports and validation results  
**Contains:** E2E validation reports, test execution logs  
**Note:** These are point-in-time snapshots for reference

## Recommended Reading Order

### For New Contributors
1. Architecture - Get the big picture
2. API Reference - Understand the interfaces
3. Testing - Learn how to validate changes
4. GraphQL Client - Dive into GitHub integration

### For Feature Development
1. API Reference - Find relevant modules
2. GraphQL Client - If working with GitHub
3. Testing - Write comprehensive tests

### For Bug Fixes
1. API Reference - Locate the issue
2. Testing - Reproduce and fix
3. Architecture - Ensure fix aligns with design

## Development Workflow

1. **Understand the Issue**: Read issue requirements thoroughly
2. **Review Relevant Docs**: Check architecture and API docs
3. **Write Tests First**: Follow TDD practices when possible
4. **Implement Solution**: Follow existing patterns
5. **Update Documentation**: Keep docs in sync with code
6. **Run Full Test Suite**: Ensure no regressions

## Key Development Principles

- **Hybrid API Strategy**: REST (PyGithub) + GraphQL for optimal functionality
- **Graceful Degradation**: Always provide fallbacks for missing features
- **Type Safety**: Use Pydantic models and type hints throughout
- **Test Coverage**: E2E tests against live GitHub are critical
- **Documentation**: Update docs with every significant change

## Project Structure Reference

```
src/ghoo/
├── main.py           # CLI entry point (Typer commands)
├── core.py           # GitHub API integration layer
├── models.py         # Pydantic data models
├── graphql_client.py # GraphQL client implementation
├── parser.py         # Issue body parser
├── commands/         # Command implementations
├── templates/        # Jinja2 templates
└── exceptions.py     # Custom exceptions
```

## Testing Infrastructure

- **Unit Tests**: `/tests/unit/` - Fast, isolated component tests
- **Integration Tests**: `/tests/integration/` - Module interaction tests
- **E2E Tests**: `/tests/e2e/` - Live GitHub validation
- **Test Reports**: `/docs/development/testing/` - Historical results

## Getting Help

- Check [User Guide](../user-guide/README.md) for usage documentation
- Review [Research](../research/README.md) for design decisions
- Consult CLAUDE.md for AI assistant guidelines
- See SPEC.md for detailed technical specifications
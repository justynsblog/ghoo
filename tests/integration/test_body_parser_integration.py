"""Integration tests for body parser with real-world GitHub markdown examples."""

import pytest
from ghoo.core import IssueParser


class TestBodyParserIntegration:
    """Integration tests with real-world GitHub issue examples."""
    
    def test_github_issue_template_epic(self):
        """Test parsing a typical GitHub issue using the Epic template."""
        body = """This epic covers the implementation of user authentication for the application.

The goal is to provide secure, scalable authentication that integrates with existing systems.

## Summary

Implement comprehensive user authentication system including:
- OAuth 2.0 integration with GitHub and Google
- JWT token management with refresh tokens
- Role-based access control (RBAC)
- Multi-factor authentication (MFA) support

## Acceptance Criteria

- [x] OAuth integration works with GitHub
- [ ] OAuth integration works with Google
- [x] JWT tokens are properly generated and validated
- [ ] Refresh token rotation is implemented
- [x] RBAC system allows role assignment
- [ ] MFA can be enabled per user
- [ ] All authentication endpoints have proper rate limiting
- [x] Security audit passes

## Milestone Plan

### Phase 1: Core Authentication (Week 1-2)
- [x] OAuth provider setup
- [ ] Basic login/logout flows  
- [ ] User model and database schema

### Phase 2: Advanced Features (Week 3-4)
- [ ] JWT refresh token mechanism
- [ ] RBAC implementation
- [ ] MFA integration

### Phase 3: Security & Polish (Week 5)
- [ ] Rate limiting implementation
- [ ] Security audit and fixes
- [ ] Documentation and testing

## Technical Notes

The implementation should follow OWASP guidelines and use industry-standard libraries:
- `passport.js` for OAuth strategies
- `jsonwebtoken` for JWT handling
- `bcrypt` for password hashing (if local auth is added later)

Related issues: #123, #124, #125"""
        
        result = IssueParser.parse_body(body)
        
        # Validate pre-section description
        assert 'This epic covers the implementation' in result['pre_section_description']
        assert 'existing systems' in result['pre_section_description']
        
        # Validate sections
        assert len(result['sections']) == 4
        section_titles = [s.title for s in result['sections']]
        assert 'Summary' in section_titles
        assert 'Acceptance Criteria' in section_titles
        assert 'Milestone Plan' in section_titles
        assert 'Technical Notes' in section_titles
        
        # Validate Acceptance Criteria todos
        ac_section = next(s for s in result['sections'] if s.title == 'Acceptance Criteria')
        assert ac_section.total_todos == 8
        assert ac_section.completed_todos == 4
        
        # Check specific todos
        todo_texts = [t.text for t in ac_section.todos]
        assert 'OAuth integration works with GitHub' in todo_texts
        assert 'Security audit passes' in todo_texts
        
        # Validate Milestone Plan todos
        mp_section = next(s for s in result['sections'] if s.title == 'Milestone Plan')
        assert mp_section.total_todos > 0
        
        # Check that technical notes section has no todos
        tn_section = next(s for s in result['sections'] if s.title == 'Technical Notes')
        assert tn_section.total_todos == 0
        assert 'OWASP guidelines' in tn_section.body
    
    def test_github_issue_with_code_blocks(self):
        """Test parsing issue with code blocks that should not interfere."""
        body = """## Problem Description

The current API endpoint returns inconsistent data formats.

```javascript
// Current problematic response
{
  "user": {
    "id": 123,
    "name": "John"
  }
}
```

## Solution

We need to standardize the response format:

```javascript  
// Desired response format
{
  "data": {
    "user": {
      "id": 123,
      "name": "John",
      "email": "john@example.com"
    }
  },
  "meta": {
    "timestamp": "2023-01-01T00:00:00Z"
  }
}
```

## Implementation Tasks

- [ ] Update user controller to return standardized format
- [x] Create response wrapper utility
- [ ] Update all API endpoints to use new format
- [ ] Update API documentation

## Code Notes

Remember to handle backwards compatibility:

```javascript
// Legacy support code
if (request.headers['api-version'] === 'v1') {
  return legacyFormat(data);
}
```

The migration should be gradual."""
        
        result = IssueParser.parse_body(body)
        
        # Should have 4 sections
        assert len(result['sections']) == 4
        
        # Check that code blocks didn't interfere with parsing
        impl_section = next(s for s in result['sections'] if s.title == 'Implementation Tasks')
        assert impl_section.total_todos == 4
        assert impl_section.completed_todos == 1
        
        # Verify code blocks are preserved in body content
        problem_section = next(s for s in result['sections'] if s.title == 'Problem Description')
        assert '```javascript' in problem_section.body
        assert '"user": {' in problem_section.body
        
        solution_section = next(s for s in result['sections'] if s.title == 'Solution')
        assert 'standardize the response format' in solution_section.body
        assert '```javascript' in solution_section.body
    
    def test_github_issue_with_nested_lists(self):
        """Test parsing issue with nested lists and indented todos."""
        body = """## Feature Request: Enhanced Search

Improve the search functionality with advanced filters.

## Requirements

The search should support:

1. **Text Search**
   - [x] Full-text search across titles
   - [ ] Full-text search across descriptions  
   - [ ] Search syntax highlighting

2. **Filter Options**
   - [x] Filter by status (open/closed)
   - [x] Filter by assignee
   - [ ] Filter by labels
   - [ ] Filter by date range
   - [ ] Custom filter combinations

3. **Performance**
   - [ ] Search results load in <2 seconds
   - [x] Implement search result pagination
   - [ ] Cache frequently searched terms

## Technical Details

Implementation approach:
- Use Elasticsearch for full-text search
- Implement faceted search for filters
- Add search analytics tracking

## Additional Notes

Consider accessibility:
- Screen reader compatibility
- Keyboard navigation support
- High contrast mode compatibility"""
        
        result = IssueParser.parse_body(body)
        
        # Should have 4 sections
        assert len(result['sections']) == 4
        
        # Find requirements section and check todos
        req_section = next(s for s in result['sections'] if s.title == 'Requirements')
        assert req_section.total_todos == 11
        assert req_section.completed_todos == 4
        
        # Verify all todos are captured despite being in nested lists
        todo_texts = [t.text for t in req_section.todos]
        assert 'Full-text search across titles' in todo_texts
        assert 'Filter by labels' in todo_texts
        assert 'Search results load in <2 seconds' in todo_texts
        
        # Check that nested list structure is preserved in body
        assert '1. **Text Search**' in req_section.body
        assert '2. **Filter Options**' in req_section.body
    
    def test_github_issue_with_tables_and_links(self):
        """Test parsing issue with GitHub markdown tables and links."""
        body = """## Database Migration Plan

We need to migrate from MySQL 5.7 to MySQL 8.0. See [MySQL 8.0 migration guide](https://dev.mysql.com/doc/refman/8.0/en/upgrading.html).

## Migration Schedule

| Phase | Duration | Tasks |
|-------|----------|-------|  
| Phase 1 | 2 weeks | Setup and testing |
| Phase 2 | 1 week | Data migration |
| Phase 3 | 3 days | Cutover and validation |

## Pre-Migration Checklist

- [x] Backup all production databases
- [x] Test migration scripts on staging
- [ ] Update application code for MySQL 8.0 compatibility
- [ ] Review and update all stored procedures
- [x] Plan rollback procedures
- [ ] Coordinate with ops team for maintenance window
- [ ] Update monitoring and alerting rules

## Risk Assessment

**High Risk Items:**
- Application compatibility issues
- Stored procedure syntax changes
- Performance regressions

**Mitigation:**
- Comprehensive testing in staging environment  
- Gradual rollout with quick rollback capability
- Performance benchmarking before and after

Related: #456 (performance monitoring) and #789 (backup procedures)."""
        
        result = IssueParser.parse_body(body)
        
        # Should have 4 sections
        assert len(result['sections']) == 4
        
        # Verify table is preserved in Migration Schedule section
        schedule_section = next(s for s in result['sections'] if s.title == 'Migration Schedule')
        assert '| Phase | Duration |' in schedule_section.body
        assert 'Phase 1 | 2 weeks |' in schedule_section.body
        
        # Check Pre-Migration Checklist todos
        checklist_section = next(s for s in result['sections'] if s.title == 'Pre-Migration Checklist')
        assert checklist_section.total_todos == 7
        assert checklist_section.completed_todos == 3
        
        # Verify links are preserved in the Database Migration Plan section
        migration_plan_section = next(s for s in result['sections'] if s.title == 'Database Migration Plan')
        assert '[MySQL 8.0 migration guide]' in migration_plan_section.body
        
        # Check that markdown formatting in risk assessment is preserved
        risk_section = next(s for s in result['sections'] if s.title == 'Risk Assessment')
        assert '**High Risk Items:**' in risk_section.body
        assert 'Related: #456' in risk_section.body
    
    def test_real_world_complex_issue(self):
        """Test parsing a complex real-world issue with multiple formatting patterns."""
        body = """This issue tracks the implementation of the new CI/CD pipeline using GitHub Actions.

**Context:** Our current Jenkins-based CI is slow and hard to maintain. We want to migrate to GitHub Actions for better integration and faster builds.

## Summary

Migrate CI/CD pipeline from Jenkins to GitHub Actions with the following goals:
- Reduce build times by 50%
- Improve developer experience
- Add automated security scanning
- Implement blue-green deployments

## Current State Analysis

### Problems with Jenkins:
1. **Performance Issues**
   - Builds taking 15+ minutes
   - Queue delays during peak hours
   - Resource contention between jobs

2. **Maintenance Overhead** 
   - Plugin management is complex
   - Security updates are frequent
   - Configuration drift between environments

### Success Metrics:
- Build time: < 8 minutes (currently 15-20 min)
- Developer satisfaction: > 4.5/5 (currently 2.8/5)
- Security scan coverage: 100% (currently 0%)

## Implementation Plan

### Phase 1: Foundation (Sprint 1-2)

**Setup & Configuration:**
- [x] Create GitHub Actions workflows repository
- [x] Set up development environment
- [ ] Configure secrets management
- [ ] Set up artifact storage

**Basic Pipeline:**
- [x] Implement basic CI workflow (build, test, lint)
- [ ] Add code quality checks (SonarQube integration)
- [ ] Set up notification system (Slack, email)

### Phase 2: Advanced Features (Sprint 3-4)

**Security & Compliance:**
- [ ] Integrate SAST tools (CodeQL, Semgrep)
- [ ] Add dependency vulnerability scanning
- [ ] Implement compliance checks (SOX, GDPR)
- [x] Set up secret scanning

**Deployment Automation:**
- [ ] Blue-green deployment strategy
- [ ] Automated rollback mechanisms  
- [ ] Environment-specific configurations
- [ ] Database migration automation

### Phase 3: Migration & Optimization (Sprint 5-6)

**Migration Tasks:**
- [ ] Migrate staging environment
- [ ] Parallel run Jenkins vs GitHub Actions
- [ ] Migrate production environment  
- [ ] Decommission Jenkins infrastructure

**Performance Optimization:**
- [ ] Implement build caching strategies
- [ ] Optimize Docker image layers
- [x] Set up build matrix for parallel execution
- [ ] Fine-tune resource allocation

## Acceptance Criteria

### Functional Requirements:
- [x] All existing Jenkins jobs have GitHub Actions equivalents
- [ ] Build times are consistently under 8 minutes
- [x] All tests pass in new pipeline
- [ ] Security scans run on every commit
- [ ] Deployments work for all environments (dev, staging, prod)

### Non-Functional Requirements:  
- [ ] 99.9% pipeline availability
- [ ] Zero false positives in security scans
- [x] Developer onboarding takes < 30 minutes
- [ ] Full audit trail for compliance

## Technical Considerations

**GitHub Actions Features to Use:**
```yaml
# Example workflow structure
name: CI/CD Pipeline
on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]
    
jobs:
  test:
    runs-on: ubuntu-latest
    # ... rest of workflow
```

**Security Best Practices:**
- Use OpenID Connect (OIDC) for AWS authentication
- Implement least-privilege access policies
- Regular rotation of secrets and tokens
- Audit all third-party actions used

## Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| GitHub Actions outage | High | Low | Maintain Jenkins as backup for 30 days |
| Performance regression | Medium | Medium | Comprehensive benchmarking |
| Security vulnerabilities | High | Low | Security review and penetration testing |

## Dependencies

- [ ] AWS infrastructure updates (blocked by #123)
- [x] SonarQube license renewal
- [ ] Security team approval for new tools
- [x] DevOps team training on GitHub Actions

## Success Criteria

The migration will be considered successful when:
1. All builds complete in < 8 minutes
2. Zero production incidents related to CI/CD
3. Developer satisfaction score > 4.5/5
4. All security and compliance requirements met

---

**Related Issues:** #100 (Jenkins maintenance), #200 (build performance), #300 (security scanning)
**Documentation:** [Migration Runbook](https://wiki.company.com/cicd-migration)
**Slack Channel:** #cicd-migration"""
        
        result = IssueParser.parse_body(body)
        
        # Validate pre-section description
        pre_section = result['pre_section_description']
        assert 'This issue tracks the implementation' in pre_section
        assert 'GitHub Actions for better integration' in pre_section
        
        # Should have many sections due to complex structure
        assert len(result['sections']) >= 8
        section_titles = [s.title for s in result['sections']]
        assert 'Summary' in section_titles
        assert 'Implementation Plan' in section_titles
        assert 'Acceptance Criteria' in section_titles
        
        # Count all todos across all sections
        total_todos = sum(s.total_todos for s in result['sections'])
        completed_todos = sum(s.completed_todos for s in result['sections'])
        
        assert total_todos > 30  # Should be many todos
        assert completed_todos > 5  # Some should be completed
        
        # Check that code blocks and tables are preserved
        tech_section = next((s for s in result['sections'] if 'Technical Considerations' in s.title), None)
        assert tech_section is not None
        assert '```yaml' in tech_section.body
        assert 'runs-on: ubuntu-latest' in tech_section.body
        
        # Check that table is preserved in Risks section
        risks_section = next((s for s in result['sections'] if 'Risks' in s.title), None)
        assert risks_section is not None
        assert '| Risk | Impact |' in risks_section.body
    
    def test_performance_with_large_issue(self):
        """Test parser performance with a large issue body."""
        import time
        
        # Generate a large issue body
        sections = []
        for i in range(50):
            section_content = f"""## Section {i}

This is section {i} with some content that includes multiple paragraphs
and various formatting elements.

Here are some todos for section {i}:
- [ ] Task {i}.1 - implement feature
- [x] Task {i}.2 - write tests  
- [ ] Task {i}.3 - update documentation
- [ ] Task {i}.4 - review code

And some more content with **bold text** and *italic text* and `code snippets`.

Here's a code block:
```python
def function_{i}():
    return "Hello from section {i}"
```

Final paragraph for section {i}."""
            sections.append(section_content)
        
        large_body = "Large issue description with lots of content.\n\n" + "\n\n".join(sections)
        
        # Time the parsing
        start_time = time.time()
        result = IssueParser.parse_body(large_body)
        end_time = time.time()
        
        parse_time = end_time - start_time
        
        # Validate results
        assert len(result['sections']) == 50
        assert result['pre_section_description'] == 'Large issue description with lots of content.'
        
        # Each section should have 4 todos
        total_todos = sum(s.total_todos for s in result['sections'])
        assert total_todos == 200  # 50 sections * 4 todos each
        
        # Performance check: should parse in under 1 second
        assert parse_time < 1.0, f"Parser took {parse_time:.2f}s, expected < 1.0s"
        
        print(f"Parser performance: {len(large_body)} chars in {parse_time:.3f}s")
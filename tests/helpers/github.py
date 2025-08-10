"""GitHub API testing utilities for ghoo."""

import time
from typing import Optional, List, Dict, Any
from github import Github, Repository, Issue, Label
from github.GithubException import GithubException


def create_test_issue(repo: Repository, 
                     title: str,
                     body: str = "",
                     labels: Optional[List[str]] = None) -> Issue:
    """Create a test issue in the repository.
    
    Args:
        repo: GitHub repository object
        title: Issue title
        body: Issue body content
        labels: Optional list of label names
        
    Returns:
        Created Issue object
    """
    try:
        issue = repo.create_issue(title=title, body=body, labels=labels or [])
        return issue
    except GithubException as e:
        raise AssertionError(f"Failed to create test issue: {e}")


def verify_issue_exists(repo: Repository, issue_number: int) -> Issue:
    """Verify that an issue exists and return it.
    
    Args:
        repo: GitHub repository object
        issue_number: Issue number to verify
        
    Returns:
        Issue object if found
        
    Raises:
        AssertionError if issue not found
    """
    try:
        return repo.get_issue(issue_number)
    except GithubException:
        raise AssertionError(f"Issue #{issue_number} not found in {repo.full_name}")


def verify_issue_has_label(issue: Issue, label_name: str):
    """Verify that an issue has a specific label.
    
    Args:
        issue: GitHub Issue object
        label_name: Name of label to check for
        
    Raises:
        AssertionError if label not found
    """
    label_names = [label.name for label in issue.labels]
    assert label_name in label_names, (
        f"Label '{label_name}' not found on issue #{issue.number}. "
        f"Found labels: {label_names}"
    )


def verify_issue_body_contains(issue: Issue, expected_text: str):
    """Verify that an issue body contains expected text.
    
    Args:
        issue: GitHub Issue object
        expected_text: Text that should be in the body
        
    Raises:
        AssertionError if text not found
    """
    assert expected_text in (issue.body or ""), (
        f"Expected text not found in issue body.\n"
        f"Expected: {expected_text}\n"
        f"Actual body: {issue.body}"
    )


def create_or_get_label(repo: Repository, name: str, color: str = "0366d6") -> Label:
    """Create a label or return it if it already exists.
    
    Args:
        repo: GitHub repository object
        name: Label name
        color: Label color (hex without #)
        
    Returns:
        Label object
    """
    try:
        return repo.get_label(name)
    except GithubException:
        try:
            return repo.create_label(name=name, color=color)
        except GithubException as e:
            raise AssertionError(f"Failed to create label '{name}': {e}")


def cleanup_test_issues(repo: Repository, title_prefix: str = "TEST:"):
    """Close all issues with a specific title prefix.
    
    Args:
        repo: GitHub repository object
        title_prefix: Prefix to identify test issues
    """
    for issue in repo.get_issues(state='open'):
        if issue.title.startswith(title_prefix):
            try:
                issue.edit(state='closed')
            except Exception:
                pass  # Best effort cleanup


def wait_for_issue_state(repo: Repository, issue_number: int, 
                        expected_state: str, timeout: int = 10):
    """Wait for an issue to reach a specific state.
    
    Args:
        repo: GitHub repository object
        issue_number: Issue number to check
        expected_state: Expected state ('open' or 'closed')
        timeout: Maximum seconds to wait
        
    Raises:
        AssertionError if timeout reached
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            issue = repo.get_issue(issue_number)
            if issue.state == expected_state:
                return
        except GithubException:
            pass
        time.sleep(1)
    
    raise AssertionError(
        f"Issue #{issue_number} did not reach state '{expected_state}' "
        f"within {timeout} seconds"
    )


def run_graphql_query(github_client: Github, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Run a GraphQL query against GitHub API.
    
    Args:
        github_client: Authenticated GitHub client
        query: GraphQL query string
        variables: Optional query variables
        
    Returns:
        Query response data
    """
    import requests
    
    headers = {
        "Authorization": f"Bearer {github_client._Github__requester._Requester__authorizationHeader.split()[1]}",
        "Content-Type": "application/json"
    }
    
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    
    response = requests.post(
        "https://api.github.com/graphql",
        json=payload,
        headers=headers
    )
    
    if response.status_code != 200:
        raise AssertionError(f"GraphQL query failed: {response.text}")
    
    data = response.json()
    if "errors" in data:
        raise AssertionError(f"GraphQL query errors: {data['errors']}")
    
    return data["data"]
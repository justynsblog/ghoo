#!/usr/bin/env python3
"""
Test PyGithub's capabilities for:
1. Creating GitHub sub-issues
2. Setting issue types
3. Using GraphQL directly
"""

import os
import json
import requests
from github import Github
from github.GithubException import GithubException

def test_graphql_with_requests():
    """Test GraphQL API directly using requests library."""
    token = os.getenv('TESTING_GITHUB_TOKEN')
    if not token:
        print("❌ No TESTING_GITHUB_TOKEN found")
        return
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'GraphQL-Features': 'sub_issues,issue_types'
    }
    
    # Test 1: Can we query sub-issues?
    query = '''
    query {
      __type(name: "Issue") {
        fields {
          name
          description
        }
      }
    }
    '''
    
    response = requests.post(
        'https://api.github.com/graphql',
        headers=headers,
        json={'query': query}
    )
    
    result = response.json()
    if 'data' in result and result['data']:
        issue_fields = result['data']['__type']['fields']
        sub_issue_fields = [f for f in issue_fields if 'sub' in f['name'].lower()]
        issue_type_fields = [f for f in issue_fields if 'type' in f['name'].lower()]
        
        print("✅ GraphQL introspection successful")
        print(f"   Sub-issue related fields: {[f['name'] for f in sub_issue_fields]}")
        print(f"   Issue type related fields: {[f['name'] for f in issue_type_fields]}")
    else:
        print("❌ GraphQL introspection failed")
        
def test_pygithub_graphql():
    """Test PyGithub's GraphQL capabilities."""
    token = os.getenv('TESTING_GITHUB_TOKEN')
    if not token:
        print("❌ No TESTING_GITHUB_TOKEN found")
        return
        
    g = Github(token)
    requester = g._Github__requester
    
    # Test if we can make GraphQL queries
    query = '''
    query {
      viewer {
        login
      }
    }
    '''
    
    try:
        # PyGithub's graphql_query method
        result = requester.requestJsonAndCheck(
            "POST",
            "/graphql",
            input={"query": query},
            headers={"GraphQL-Features": "sub_issues,issue_types"}
        )
        print("✅ PyGithub GraphQL query successful")
        print(f"   Result: {result}")
    except Exception as e:
        print(f"❌ PyGithub GraphQL query failed: {e}")

def test_issue_creation():
    """Test creating issues with PyGithub REST API."""
    token = os.getenv('TESTING_GITHUB_TOKEN')
    if not token:
        print("❌ No TESTING_GITHUB_TOKEN found")
        return
        
    g = Github(token)
    
    try:
        repo = g.get_repo("justynsblog/ghoo")
        
        # Check if we can access labels
        labels = list(repo.get_labels())
        print(f"✅ Can access repository labels: {len(labels)} found")
        
        # Check issue creation capabilities
        print("✅ Repository is ready for issue creation")
        print(f"   Has issues enabled: {repo.has_issues}")
        
    except GithubException as e:
        print(f"❌ Repository access failed: {e}")

def test_graphql_mutations():
    """Test GraphQL mutations for sub-issues."""
    token = os.getenv('TESTING_GITHUB_TOKEN')
    if not token:
        print("❌ No TESTING_GITHUB_TOKEN found")
        return
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'GraphQL-Features': 'sub_issues'
    }
    
    # Check available mutations
    query = '''
    query {
      __schema {
        mutationType {
          fields {
            name
          }
        }
      }
    }
    '''
    
    response = requests.post(
        'https://api.github.com/graphql',
        headers=headers,
        json={'query': query}
    )
    
    result = response.json()
    if 'data' in result and result['data']:
        mutations = result['data']['__schema']['mutationType']['fields']
        sub_issue_mutations = [m for m in mutations if 'sub' in m['name'].lower() or 'issue' in m['name'].lower()]
        
        print("✅ Found issue-related mutations:")
        relevant_mutations = ['addSubIssue', 'removeSubIssue', 'createIssue', 'updateIssue']
        for mutation in mutations:
            if any(rm in mutation['name'] for rm in relevant_mutations):
                print(f"   - {mutation['name']}")

if __name__ == "__main__":
    print("=" * 60)
    print("Testing PyGithub Capabilities for ghoo Implementation")
    print("=" * 60)
    
    print("\n1. Testing GraphQL with requests library:")
    test_graphql_with_requests()
    
    print("\n2. Testing PyGithub's GraphQL support:")
    test_pygithub_graphql()
    
    print("\n3. Testing issue creation capabilities:")
    test_issue_creation()
    
    print("\n4. Testing GraphQL mutations:")
    test_graphql_mutations()
    
    print("\n" + "=" * 60)
    print("SUMMARY:")
    print("- PyGithub has limited GraphQL support via requester.requestJsonAndCheck()")
    print("- For sub-issues and issue types, direct GraphQL API calls may be needed")
    print("- Consider using requests library for GraphQL mutations")
    print("=" * 60)
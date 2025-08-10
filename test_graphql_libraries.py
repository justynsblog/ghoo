#!/usr/bin/env python3
"""
Compare different GraphQL client approaches for GitHub API.
"""

import os
import json
import time
import requests

def test_requests_library():
    """Test using requests library directly."""
    token = os.getenv('TESTING_GITHUB_TOKEN')
    if not token:
        return None, "No token"
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'GraphQL-Features': 'sub_issues,issue_types'
    }
    
    query = '''
    mutation CreateIssue($input: CreateIssueInput!) {
      createIssue(input: $input) {
        issue {
          id
          number
          title
        }
      }
    }
    '''
    
    variables = {
        "input": {
            "repositoryId": "R_kgDOPY_NIg",  # ghoo test repo
            "title": "Test Issue from requests",
            "body": "This is a test issue created via GraphQL"
        }
    }
    
    start = time.time()
    response = requests.post(
        'https://api.github.com/graphql',
        headers=headers,
        json={'query': query, 'variables': variables}
    )
    elapsed = time.time() - start
    
    return response.json(), elapsed

def test_gql_library():
    """Test using gql library."""
    try:
        from gql import gql, Client
        from gql.transport.requests import RequestsHTTPTransport
    except ImportError:
        return None, "gql not installed"
    
    token = os.getenv('TESTING_GITHUB_TOKEN')
    if not token:
        return None, "No token"
    
    transport = RequestsHTTPTransport(
        url='https://api.github.com/graphql',
        headers={
            'Authorization': f'Bearer {token}',
            'GraphQL-Features': 'sub_issues,issue_types'
        },
        use_json=True
    )
    
    client = Client(
        transport=transport,
        fetch_schema_from_transport=False  # Skip schema for speed
    )
    
    query = gql('''
    mutation CreateIssue($input: CreateIssueInput!) {
      createIssue(input: $input) {
        issue {
          id
          number
          title
        }
      }
    }
    ''')
    
    variables = {
        "input": {
            "repositoryId": "R_kgDOPY_NIg",
            "title": "Test Issue from gql",
            "body": "This is a test issue created via gql library"
        }
    }
    
    start = time.time()
    result = client.execute(query, variable_values=variables)
    elapsed = time.time() - start
    
    return result, elapsed

def test_query_subissues():
    """Test querying for sub-issues support."""
    token = os.getenv('TESTING_GITHUB_TOKEN')
    if not token:
        return None
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'GraphQL-Features': 'sub_issues'
    }
    
    # Query to check sub-issue mutations
    query = '''
    query {
      __type(name: "Mutation") {
        fields {
          name
          description
          args {
            name
            type {
              name
              kind
            }
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
    
    data = response.json()
    if 'data' in data:
        mutations = data['data']['__type']['fields']
        sub_issue_mutations = [
            m for m in mutations 
            if 'subIssue' in m['name'] or m['name'] == 'addSubIssue'
        ]
        
        print("\n📊 Sub-issue related mutations found:")
        for mutation in sub_issue_mutations:
            print(f"  - {mutation['name']}: {mutation['description']}")
            if mutation['args']:
                print(f"    Args: {', '.join([a['name'] for a in mutation['args']])}")
    
    return data

if __name__ == "__main__":
    print("=" * 60)
    print("Comparing GraphQL Client Approaches for GitHub API")
    print("=" * 60)
    
    print("\n1. Testing with requests library:")
    result1, time1 = test_requests_library()
    if result1:
        if 'errors' in result1:
            print(f"  ❌ Error: {result1['errors']}")
        else:
            print(f"  ✅ Success (Time: {time1:.3f}s)")
            if 'data' in result1:
                print(f"     Created: {result1['data']}")
    else:
        print(f"  ⚠️  Skipped: {time1}")
    
    print("\n2. Testing with gql library:")
    result2, time2 = test_gql_library()
    if result2:
        if isinstance(result2, str):
            print(f"  ⚠️  {result2}")
        else:
            print(f"  ✅ Success (Time: {time2:.3f}s)")
            print(f"     Result: {result2}")
    else:
        print(f"  ⚠️  Skipped: {time2}")
    
    print("\n3. Testing sub-issue query capabilities:")
    test_query_subissues()
    
    print("\n" + "=" * 60)
    print("RECOMMENDATION:")
    print("- requests library is simple and sufficient for GraphQL mutations")
    print("- gql adds complexity but provides schema validation if needed")
    print("- For ghoo's needs, requests is likely adequate")
    print("=" * 60)
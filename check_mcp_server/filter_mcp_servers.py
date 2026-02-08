import os
import csv
import subprocess
import json
import argparse
import shutil
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed

def clone_repository(full_name: str, target_dir: str) -> bool:
    """Clone a GitHub repository if it doesn't exist"""
    repo_name = full_name.replace('/', '_')
    repo_path = os.path.join(target_dir, repo_name)
    
    if os.path.exists(repo_path):
        print(f"Repository {full_name} already exists, skipping clone")
        return True
    
    github_url = f"https://github.com/{full_name}.git"
    print(f"Cloning {github_url}...")
    
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", github_url, repo_path],
            check=True,
            capture_output=True
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to clone {full_name}: {e}")
        return False

def verify_repository(repo_path: str) -> dict:
    """Run verify_mcp.py on a repository"""
    try:
        result = subprocess.run(
            ["python3", "verify_mcp.py", repo_path, "--json"],
            capture_output=True,
            text=True,
            check=True
        )
        return json.loads(result.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
        print(f"Error verifying {repo_path}: {e}")
        return {"is_mcp": False, "confidence": "low", "error": str(e)}

def parse_repo_input(repo_input: str) -> str:
    """
    Parse repository input from either URL or full_name format.
    
    Examples:
        https://github.com/Mintplex-Labs/anything-llm -> Mintplex-Labs/anything-llm
        Mintplex-Labs/anything-llm -> Mintplex-Labs/anything-llm
    """
    # If it's a URL, extract the full_name
    if repo_input.startswith('http'):
        # Remove trailing .git if present
        repo_input = repo_input.rstrip('.git')
        # Extract owner/repo from URL
        parts = repo_input.split('github.com/')
        if len(parts) == 2:
            return parts[1].strip('/')
    
    # Otherwise assume it's already in full_name format
    return repo_input.strip('/')

def process_repository(repo_dict: dict, servers_dir: str) -> dict:
    """Process a single repository - clone and verify"""
    full_name = repo_dict['full_name']
    print(f"\n{'='*60}")
    print(f"Processing: {full_name}")
    print(f"{'='*60}")
    
    # Clone repository
    repo_name = full_name.replace('/', '_')
    repo_path = os.path.join(servers_dir, repo_name)
    
    if not clone_repository(full_name, servers_dir):
        return {
            'full_name': full_name,
            'is_mcp': False,
            'confidence': 'low',
            'error': 'Failed to clone'
        }
    
    # Verify if it's an MCP server
    verification = verify_repository(repo_path)
    verification['full_name'] = full_name
    verification['csv_tools'] = repo_dict.get('tools', '').split('; ') if repo_dict.get('tools') else []
    
    print(f"Is MCP: {verification['is_mcp']}")
    print(f"Confidence: {verification['confidence']}")
    
    return verification

def main():
    parser = argparse.ArgumentParser(description="Filter MCP servers from CSV or check a single repository")
    parser.add_argument("--csv", default="mcp_servers_top_100.csv", help="Input CSV file")
    parser.add_argument("--output", default="verified_mcp_servers.json", help="Output JSON file")
    parser.add_argument("--limit", type=int, help="Limit number of repositories to process")
    parser.add_argument("--servers-dir", default="servers", help="Directory to store cloned repos")
    parser.add_argument("--repo", type=str, help="Check a single repository by URL or full_name (e.g., 'https://github.com/owner/repo' or 'owner/repo')")
    parser.add_argument("--workers", type=int, default=4, help="Number of parallel workers (default: 4)")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing results instead of appending (default: append)")
    args = parser.parse_args()
    
    # Create servers directory
    os.makedirs(args.servers_dir, exist_ok=True)
    
    # Load existing results by default (unless --overwrite is specified)
    existing_results = []
    existing_repos = set()
    if not args.overwrite and os.path.exists(args.output):
        try:
            with open(args.output, 'r', encoding='utf-8') as f:
                existing_results = json.load(f)
                existing_repos = {r['full_name'] for r in existing_results}
            print(f"Loaded {len(existing_results)} existing results from {args.output}")
            print("(Use --overwrite to start fresh)")
        except Exception as e:
            print(f"Warning: Could not load existing results: {e}")
            existing_results = []
            existing_repos = set()
    
    # Check if single repo mode
    if args.repo:
        # Single repository mode
        full_name = parse_repo_input(args.repo)
        repositories = [{'full_name': full_name, 'tools': ''}]
        print(f"Checking single repository: {full_name}")
    else:
        # CSV mode
        repositories = []
        with open(args.csv, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Skip if already processed (unless overwriting)
                if row['full_name'] in existing_repos:
                    print(f"Skipping {row['full_name']} (already verified)")
                    continue
                repositories.append(row)
        
        # Apply limit if specified
        if args.limit:
            repositories = repositories[:args.limit]
    
    if not repositories:
        print("No repositories to process (all already verified)")
        return
    
    results = []
    
    # Use parallel processing for multiple repositories
    if len(repositories) > 1 and not args.repo:
        print(f"\n{'='*60}")
        print(f"Starting parallel processing with {args.workers} workers")
        print(f"{'='*60}")
        
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            # Submit all tasks
            future_to_repo = {
                executor.submit(process_repository, repo, args.servers_dir): repo
                for repo in repositories
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_repo):
                repo = future_to_repo[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    print(f"Error processing {repo['full_name']}: {e}")
                    results.append({
                        'full_name': repo['full_name'],
                        'is_mcp': False,
                        'confidence': 'low',
                        'error': str(e)
                    })
    else:
        # Single repository or single repo mode - process sequentially
        for repo in repositories:
            result = process_repository(repo, args.servers_dir)
            results.append(result)
    
    # Merge with existing results (unless overwriting)
    if args.overwrite:
        all_results = results
        print(f"\nOverwriting with {len(results)} new results")
    else:
        # Combine existing and new results
        all_results = existing_results + results
        if existing_results:
            print(f"\nMerged {len(existing_results)} existing + {len(results)} new = {len(all_results)} total results")
    
    # Save results
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2)
    
    # Print summary
    print(f"\n{'='*60}")
    if args.repo:
        print("SINGLE REPOSITORY CHECK RESULT")
    else:
        print("SUMMARY")
    print(f"{'='*60}")
    
    if args.repo and len(results) == 1:
        # Special output for single repo mode
        result = results[0]
        print(f"Repository: {result['full_name']}")
        print(f"Is MCP Server: {result['is_mcp']}")
        print(f"Confidence: {result['confidence']}")
        if result.get('has_imports'):
            print(f"Has MCP Imports: {result['has_imports']}")
        if result.get('has_decorators'):
            print(f"Has MCP Decorators: {result['has_decorators']}")
        if result.get('evidence_files'):
            print(f"\nEvidence files ({len(result['evidence_files'])}):")
            for f in result['evidence_files'][:5]:  # Show first 5
                print(f"  - {f}")
            if len(result['evidence_files']) > 5:
                print(f"  ... and {len(result['evidence_files']) - 5} more")
    else:
        # Summary for batch mode
        total = len(all_results)
        mcp_servers = [r for r in all_results if r['is_mcp']]
        high_confidence = [r for r in mcp_servers if r['confidence'] == 'high']
        medium_confidence = [r for r in mcp_servers if r['confidence'] == 'medium']
        
        print(f"Total repositories in output: {total}")
        if not args.overwrite and existing_results:
            print(f"  - Previously verified: {len(existing_results)}")
            print(f"  - Newly verified: {len(results)}")
        print(f"MCP servers found: {len(mcp_servers)}")
        print(f"  - High confidence: {len(high_confidence)}")
        print(f"  - Medium confidence: {len(medium_confidence)}")
        print(f"Non-MCP repositories: {total - len(mcp_servers)}")
    
    print(f"\nResults saved to: {args.output}")
    
    # Print MCP servers list (only in batch mode)
    if not args.repo:
        mcp_servers = [r for r in all_results if r['is_mcp']]
        if mcp_servers:
            print(f"\n{'='*60}")
            print("VERIFIED MCP SERVERS")
            print(f"{'='*60}")
            for server in mcp_servers:
                print(f"  [{server['confidence'].upper()}] {server['full_name']}")

if __name__ == "__main__":
    main()

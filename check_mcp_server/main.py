import csv
import os
import subprocess
import json
import shutil
import sys

CSV_FILE = 'mcp_servers_top_100.csv'
SERVERS_DIR = 'servers'
SCANNER_SCRIPT = 'scan_engine.py'

def read_csv(filepath):
    servers = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                servers.append(row)
    except Exception as e:
        print(f"Error reading CSV: {e}")
    return servers

def clone_repo(full_name, target_dir):
    repo_url = f"https://github.com/{full_name}.git"
    if os.path.exists(target_dir):
        # print(f"Directory {target_dir} already exists, skipping clone (or updating).")
        # For simplicity, we might just pull or skip. Let's skip if exists to save time during dev.
        return True
    
    try:
        print(f"Cloning {repo_url}...")
        subprocess.run(['git', 'clone', '--depth', '1', repo_url, target_dir], check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to clone {repo_url}: {e}")
        return False

def run_scanner(target_dir):
    try:
        result = subprocess.run(
            [sys.executable, SCANNER_SCRIPT, target_dir],
            capture_output=True,
            text=True,
            check=True
        )
        return json.loads(result.stdout)
    except Exception as e:
        print(f"Error running scanner on {target_dir}: {e}")
        return []

def main():
    parser = argparse.ArgumentParser(description="MCP Server Downloader and Scanner")
    parser.add_argument("--limit", type=int, help="Limit the number of servers to process", default=None)
    args = parser.parse_args()

    if not os.path.exists(SERVERS_DIR):
        os.makedirs(SERVERS_DIR)

    servers = read_csv(CSV_FILE)
    
    if args.limit:
        servers = servers[:args.limit]
    
    results = []

    for server in servers:
        full_name = server.get('full_name')
        if not full_name:
            continue
            
        repo_name = full_name.replace('/', '_')
        target_dir = os.path.join(SERVERS_DIR, repo_name)
        
        if clone_repo(full_name, target_dir):
            tools = run_scanner(target_dir)
            print(f"Server: {full_name}")
            print(f"Found Tools: {tools}")
            print("-" * 40)
            
            results.append({
                "full_name": full_name,
                "found_tools": tools,
                "csv_tools": server.get('tools', '').split('; ')
            })

    # Optional: Save results to a file
    with open('scan_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
    print("Scan complete. Results saved to scan_results.json")

if __name__ == "__main__":
    import argparse
    main()

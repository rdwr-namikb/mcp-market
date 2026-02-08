#!/bin/bash
# Script to import MongoDB data from compressed JSON files
# Usage: ./import_data.sh

set -e

DATA_DIR="$(dirname "$0")/data"
DB_NAME="mcp_servers"

echo "=== MCP Servers Database Import Script ==="
echo ""

# Check if MongoDB is running
if ! mongosh --quiet --eval "db.version()" > /dev/null 2>&1; then
    echo "Error: MongoDB is not running or not accessible"
    echo "Please start MongoDB first: sudo systemctl start mongod"
    exit 1
fi

# Check if data directory exists
if [ ! -d "$DATA_DIR" ]; then
    echo "Error: Data directory not found at $DATA_DIR"
    exit 1
fi

echo "Importing data into '$DB_NAME' database..."
echo ""

# Collections to import
COLLECTIONS=("repositories" "is_mcp_server" "tools_cache" "readmes")

for collection in "${COLLECTIONS[@]}"; do
    gz_file="$DATA_DIR/${collection}.json.gz"
    
    if [ -f "$gz_file" ]; then
        echo "Importing $collection..."
        gunzip -c "$gz_file" | mongoimport --db "$DB_NAME" --collection "$collection" --jsonArray --drop
        echo "  ✓ $collection imported successfully"
    else
        echo "  ⚠ Warning: $gz_file not found, skipping..."
    fi
done

echo ""
echo "=== Import completed! ==="
echo ""
echo "Collection counts:"
mongosh --quiet --eval "
    db = db.getSiblingDB('$DB_NAME');
    db.getCollectionNames().forEach(function(c) {
        print('  ' + c + ': ' + db[c].countDocuments({}) + ' documents');
    });
"

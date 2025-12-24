#!/bin/zsh

# Parse all Draw Steel data from markdown to JSON
# This script runs all parser scripts in the scripts directory

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/.."

echo "=================================="
echo "Draw Steel Data Parser - Full Run"
echo "=================================="
echo ""

START_TIME=$(date +%s)

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Array of all parser scripts in execution order
PARSERS=(
    "parse_classes.py"
    "parse_abilities.py"
    "parse_features.py"
    "parse_ancestries.py"
    "parse_careers.py"
    "parse_upbringings.py"
    "parse_chapters.py"
    "parse_complications.py"
    "parse_conditions.py"
    "parse_environments.py"
    "parse_kits.py"
    "parse_languages.py"
    "parse_motivations_and_pitfalls.py"
    "parse_movement.py"
    "parse_organizations.py"
    "parse_perks.py"
    "parse_skills.py"
    "parse_titles.py"
    "parse_treasures.py"
)

SUCCESSFUL=0
FAILED=0
FAILED_PARSERS=()

# Run each parser
for parser in "${PARSERS[@]}"; do
    if [ -f "scripts/$parser" ]; then
        echo "Running $parser..."
        echo "---"
        
        if python "scripts/$parser"; then
            ((SUCCESSFUL++))
            echo ""
        else
            ((FAILED++))
            FAILED_PARSERS+=("$parser")
            echo "❌ FAILED: $parser"
            echo ""
        fi
    else
        echo "⚠️  Warning: scripts/$parser not found, skipping..."
        echo ""
    fi
done

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo "=================================="
echo "Summary"
echo "=================================="
echo "Duration: ${DURATION}s"
echo "Successful: $SUCCESSFUL"
echo "Failed: $FAILED"

if [ $FAILED -gt 0 ]; then
    echo ""
    echo "Failed parsers:"
    for parser in "${FAILED_PARSERS[@]}"; do
        echo "  - $parser"
    done
    exit 1
fi

echo ""
echo "✓ All parsers completed successfully!"
echo ""
echo "Output files in data/ directory"

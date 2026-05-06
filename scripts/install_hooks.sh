#!/bin/bash
# Install pre-commit hooks for pLayStorE project
# This script sets up git hooks for secret scanning and other checks

set -e

echo "🔧 Installing pLayStorE pre-commit hooks..."

# Get the project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Create hooks directory if it doesn't exist
HOOKS_DIR="$PROJECT_ROOT/.git/hooks"
if [ ! -d "$HOOKS_DIR" ]; then
    echo "❌ .git/hooks directory not found. Are you in a git repository?"
    exit 1
fi

# Install secret scanner as pre-commit hook
echo "📝 Installing secret scanner pre-commit hook..."
cat > "$HOOKS_DIR/pre-commit" << 'EOF'
#!/bin/bash
# Pre-commit hook for pLayStorE project
# Runs secret scanning before each commit

# Get the directory where this script is located
HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$HOOK_DIR/../.." && pwd)"

# Run the secret scanner
python3 "$PROJECT_ROOT/scripts/secret_scanner.py"
exit_code=$?

if [ $exit_code -ne 0 ]; then
    echo ""
    echo "⛔ Commit blocked due to potential secrets in staged files."
    echo "   Please remove secrets or use environment variables instead."
    exit 1
fi

exit 0
EOF

chmod +x "$HOOKS_DIR/pre-commit"

echo "✅ Pre-commit hook installed successfully!"
echo ""
echo "📋 To manually run the secret scanner:"
echo "   python scripts/secret_scanner.py"
echo ""
echo "📚 For more information, see: docs/SECURITY.md"

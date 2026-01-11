#!/bin/bash
# Script to update generator.py with Cloudflare Worker URL

if [ -z "$1" ]; then
    echo "Usage: ./update-generator.sh <your-worker-url>"
    echo ""
    echo "Example:"
    echo "  ./update-generator.sh https://cal-vgp-proxy.myname.workers.dev"
    echo ""
    echo "To get your worker URL, run: wrangler deploy"
    exit 1
fi

WORKER_URL="$1"
GENERATOR_FILE="../scraper/src/website/generator.py"

if [ ! -f "$GENERATOR_FILE" ]; then
    echo "❌ Error: Cannot find $GENERATOR_FILE"
    exit 1
fi

echo "📝 Updating generator.py with worker URL: $WORKER_URL"
echo ""

# Backup the original file
cp "$GENERATOR_FILE" "$GENERATOR_FILE.backup"
echo "✓ Created backup: $GENERATOR_FILE.backup"

# Update Anthropic API call
sed -i '' "s|https://api.anthropic.com/v1/messages|${WORKER_URL}/anthropic|g" "$GENERATOR_FILE"
echo "✓ Updated Anthropic API endpoint"

# Update OpenAI API call
sed -i '' "s|https://api.openai.com/v1/chat/completions|${WORKER_URL}/openai|g" "$GENERATOR_FILE"
echo "✓ Updated OpenAI API endpoint"

# Also update the test connection function
sed -i '' "s|'https://api.anthropic.com/v1/messages'|'${WORKER_URL}/anthropic'|g" "$GENERATOR_FILE"
echo "✓ Updated Anthropic test connection"

sed -i '' "s|'https://api.openai.com/v1/models'|'${WORKER_URL}/openai'|g" "$GENERATOR_FILE"
echo "✓ Updated OpenAI test connection"

echo ""
echo "✅ Update complete!"
echo ""
echo "Next steps:"
echo "  1. cd ../scraper"
echo "  2. make website"
echo "  3. cd .."
echo "  4. git add ."
echo "  5. git commit -m 'Update chat to use Cloudflare proxy'"
echo "  6. git push"

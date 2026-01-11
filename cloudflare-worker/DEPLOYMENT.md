# Cloudflare Worker Deployment Guide

This guide explains how to deploy the API proxy worker to Cloudflare.

## What This Worker Does

The Cloudflare Worker acts as a CORS proxy for AI API calls:
- **Receives** requests from your website with user's API key
- **Forwards** to Anthropic or OpenAI APIs
- **Returns** responses with CORS headers enabled
- **Zero storage**: API keys pass through but are never stored
- **Zero cost**: Free tier supports 100,000 requests/day

## Prerequisites

1. **Cloudflare Account**: Create free account at [cloudflare.com](https://cloudflare.com)
2. **Node.js**: Ensure you have Node.js installed (check with `node --version`)

## Step 1: Install Wrangler CLI

```bash
# Install Wrangler globally
npm install -g wrangler

# Verify installation
wrangler --version
```

## Step 2: Login to Cloudflare

```bash
# This will open your browser to authenticate
wrangler login
```

Follow the browser prompts to authorize Wrangler.

## Step 3: Deploy the Worker

```bash
# Navigate to the cloudflare-worker directory
cd /Users/igorgeyn/Desktop/personal/cal_vgp/cloudflare-worker

# Deploy to Cloudflare
wrangler deploy
```

After deployment, you'll see output like:
```
✨ Success! Uploaded 1 files (0.51 sec)
✨ Uploaded cal-vgp-proxy (1.23 sec)
✨ Published cal-vgp-proxy (0.45 sec)
   https://cal-vgp-proxy.YOUR-SUBDOMAIN.workers.dev
```

**Save this URL!** You'll need it in Step 4.

## Step 4: Update Website Configuration

Once deployed, you need to update the chat JavaScript to use your worker URL.

Open `/Users/igorgeyn/Desktop/personal/cal_vgp/scraper/src/website/generator.py` and find these two functions:

### Update callAnthropic (around line 2817):

**Replace:**
```javascript
async function callAnthropic(prompt) {
    const response = await fetch('https://api.anthropic.com/v1/messages', {
```

**With:**
```javascript
async function callAnthropic(prompt) {
    const response = await fetch('https://cal-vgp-proxy.YOUR-SUBDOMAIN.workers.dev/anthropic', {
```

### Update callOpenAI (around line 2794):

**Replace:**
```javascript
async function callOpenAI(prompt) {
    const response = await fetch('https://api.openai.com/v1/chat/completions', {
```

**With:**
```javascript
async function callOpenAI(prompt) {
    const response = await fetch('https://cal-vgp-proxy.YOUR-SUBDOMAIN.workers.dev/openai', {
```

**Important**: Replace `YOUR-SUBDOMAIN` with your actual Cloudflare subdomain from Step 3.

## Step 5: Rebuild and Deploy Website

```bash
cd /Users/igorgeyn/Desktop/personal/cal_vgp/scraper
make website
cd ..
git add .
git commit -m "Update chat to use Cloudflare proxy"
git push
```

Wait ~1 minute for GitHub Pages to deploy.

## Step 6: Test the Chat Interface

1. Open your website: [cal_vgp.igorgeyn.com](https://cal_vgp.igorgeyn.com)
2. Click the chat button in bottom-right
3. Click the settings ⚙️ icon
4. Select "Anthropic (Claude)" as provider
5. Enter your Anthropic API key
6. Click "Test Connection" - should show "✓ Connected"
7. Click "Save"
8. Try an example question: "What were the 10 closest ballot measures in the last 5 years?"

## Troubleshooting

### "Worker not found"
- Make sure you deployed with `wrangler deploy`
- Check the URL matches exactly (including https://)

### "Failed to fetch"
- Verify the worker URL in generator.py is correct
- Check browser console (F12) for specific error messages
- Make sure you rebuilt the website after changing generator.py

### "Invalid API key"
- Test your API key directly at [console.anthropic.com](https://console.anthropic.com)
- Make sure there are no extra spaces when pasting

### "Rate limit exceeded"
- Cloudflare free tier: 100,000 requests/day
- Anthropic API has separate rate limits based on your plan

## Monitoring Usage

View your worker's usage in Cloudflare dashboard:
1. Go to [dash.cloudflare.com](https://dash.cloudflare.com)
2. Click "Workers & Pages"
3. Click "cal-vgp-proxy"
4. View requests, errors, and performance metrics

## Updating the Worker

If you need to modify the worker code:

```bash
# Edit worker.js
nano /Users/igorgeyn/Desktop/personal/cal_vgp/cloudflare-worker/worker.js

# Deploy changes
wrangler deploy
```

No need to rebuild the website unless you're changing the URLs.

## Cost Information

**Cloudflare Worker (Free Tier)**:
- 100,000 requests per day
- More than enough for typical usage
- If exceeded: $0.50 per million requests

**API Costs (Paid by Users)**:
- Anthropic Claude 3.5 Sonnet: ~$3 per million input tokens
- OpenAI GPT-4: ~$10 per million input tokens
- Each chat message: ~500-1000 tokens = $0.0015-$0.010

**Your cost**: $0 (users provide their own API keys)

## Security Notes

- API keys are **never stored** by the worker
- Keys pass through in request headers only
- Worker source code is visible at worker URL + `/.well-known/worker.js`
- Consider adding rate limiting if abuse becomes an issue

## Next Steps

After successful deployment:
1. Add API setup instructions to your website
2. Document how users can get API keys:
   - Anthropic: [console.anthropic.com](https://console.anthropic.com)
   - OpenAI: [platform.openai.com](https://platform.openai.com)
3. Consider adding usage tips (cost estimates, recommended questions)

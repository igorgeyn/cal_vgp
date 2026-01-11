# California VGP - Cloudflare API Proxy

This Cloudflare Worker enables your website's chat interface to work with AI APIs without CORS issues.

## 🚀 Quick Start

Run these commands to deploy:

```bash
# 1. Install Wrangler (Cloudflare CLI)
npm install -g wrangler

# 2. Login to Cloudflare
wrangler login

# 3. Deploy the worker
cd /Users/igorgeyn/Desktop/personal/cal_vgp/cloudflare-worker
wrangler deploy
```

You'll get a URL like: `https://cal-vgp-proxy.YOUR-NAME.workers.dev`

## 🔧 Update Your Website

After deploying, run:

```bash
# Replace YOUR-WORKER-URL with the URL from wrangler deploy
./update-generator.sh https://cal-vgp-proxy.YOUR-NAME.workers.dev
```

Then rebuild and deploy your website:

```bash
cd ../scraper
make website
cd ..
git add .
git commit -m "Enable chat with Cloudflare proxy"
git push
```

## 📖 Full Documentation

See [DEPLOYMENT.md](DEPLOYMENT.md) for:
- Detailed step-by-step instructions
- Troubleshooting guide
- Cost information
- Security notes

## 🎯 What This Does

**Problem**: Browsers block direct API calls to Anthropic/OpenAI (CORS errors)

**Solution**: This worker acts as a proxy:
1. Your website → Cloudflare Worker (with user's API key)
2. Cloudflare Worker → Anthropic/OpenAI API
3. Response flows back with CORS headers enabled

**Privacy**: API keys pass through but are **never stored**

**Cost**:
- Cloudflare Worker: **FREE** (100k requests/day)
- API usage: **Paid by users** (they provide their own keys)
- Your cost: **$0**

## 🔍 How It Works

The worker handles two routes:

- `POST /anthropic` → Proxies to Anthropic Claude API
- `POST /openai` → Proxies to OpenAI GPT API

It extracts the API key from request headers, forwards the request, and returns the response with CORS headers.

## 📊 Monitoring

View usage at [dash.cloudflare.com](https://dash.cloudflare.com) → Workers & Pages → cal-vgp-proxy

## 🛟 Support

If you encounter issues:
1. Check [DEPLOYMENT.md](DEPLOYMENT.md) troubleshooting section
2. Verify worker is deployed: visit your worker URL (should show "Method not allowed")
3. Check browser console (F12) for specific error messages

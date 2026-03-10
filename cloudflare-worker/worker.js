/**
 * Cloudflare Worker - API Proxy for California Ballot Measures
 *
 * This worker proxies requests to AI APIs (Anthropic, OpenAI) to bypass CORS restrictions.
 * Users provide their own API keys - this worker just passes them through.
 *
 * Zero cost to you - users pay for their own API usage.
 */

// Simple in-memory rate limiter (per-isolate; resets on cold start)
const RATE_LIMIT_WINDOW_MS = 60_000; // 1 minute
const RATE_LIMIT_MAX = 30; // max requests per window per IP
const rateLimitMap = new Map();

function isRateLimited(ip) {
  const now = Date.now();
  let entry = rateLimitMap.get(ip);

  // Clean up stale entries periodically
  if (rateLimitMap.size > 10_000) {
    for (const [key, val] of rateLimitMap) {
      if (now - val.windowStart > RATE_LIMIT_WINDOW_MS) rateLimitMap.delete(key);
    }
  }

  if (!entry || now - entry.windowStart > RATE_LIMIT_WINDOW_MS) {
    entry = { windowStart: now, count: 0 };
    rateLimitMap.set(ip, entry);
  }

  entry.count++;
  return entry.count > RATE_LIMIT_MAX;
}

// Allowed origin pattern — restrict to your GitHub Pages domain and localhost dev
const ALLOWED_ORIGINS = [
  'https://igorgeyn.github.io',
  'http://localhost',
  'http://127.0.0.1',
];

function isAllowedOrigin(origin) {
  if (!origin) return false;
  return ALLOWED_ORIGINS.some(allowed => origin.startsWith(allowed));
}

function corsHeaders(origin) {
  return {
    'Access-Control-Allow-Origin': origin || '*',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, x-api-key, Authorization, anthropic-version',
  };
}

export default {
  async fetch(request, env, ctx) {
    const origin = request.headers.get('Origin') || '';
    const cors = corsHeaders(isAllowedOrigin(origin) ? origin : ALLOWED_ORIGINS[0]);

    // Handle CORS preflight
    if (request.method === 'OPTIONS') {
      return new Response(null, {
        headers: { ...cors, 'Access-Control-Max-Age': '86400' }
      });
    }

    // Only allow POST requests
    if (request.method !== 'POST') {
      return new Response('Method not allowed', { status: 405 });
    }

    // Rate limit by IP
    const ip = request.headers.get('CF-Connecting-IP') || 'unknown';
    if (isRateLimited(ip)) {
      return new Response(JSON.stringify({ error: 'Rate limit exceeded. Please wait a moment.' }), {
        status: 429,
        headers: { 'Content-Type': 'application/json', ...cors }
      });
    }

    try {
      const url = new URL(request.url);
      const provider = url.pathname.split('/')[1]; // /anthropic or /openai

      let targetUrl, headers;

      if (provider === 'anthropic') {
        targetUrl = 'https://api.anthropic.com/v1/messages';
        const apiKey = request.headers.get('x-api-key');

        if (!apiKey) {
          return new Response('Missing API key', { status: 400 });
        }

        headers = {
          'x-api-key': apiKey,
          'anthropic-version': '2023-06-01',
          'content-type': 'application/json',
        };

      } else if (provider === 'openai') {
        targetUrl = 'https://api.openai.com/v1/chat/completions';
        const apiKey = request.headers.get('authorization');

        if (!apiKey) {
          return new Response('Missing API key', { status: 400 });
        }

        headers = {
          'authorization': apiKey,
          'content-type': 'application/json',
        };

      } else {
        return new Response('Unknown provider. Use /anthropic or /openai', { status: 400 });
      }

      // Forward the request to the AI API
      const body = await request.text();
      const apiResponse = await fetch(targetUrl, {
        method: 'POST',
        headers: headers,
        body: body,
      });

      // Get the response
      const responseBody = await apiResponse.text();

      // Return with CORS headers
      return new Response(responseBody, {
        status: apiResponse.status,
        headers: { 'Content-Type': 'application/json', ...cors }
      });

    } catch (error) {
      return new Response(JSON.stringify({ error: 'Proxy error' }), {
        status: 500,
        headers: { 'Content-Type': 'application/json', ...cors }
      });
    }
  }
};

/**
 * Cloudflare Worker - API Proxy for California Ballot Measures
 *
 * This worker proxies requests to AI APIs (Anthropic, OpenAI) to bypass CORS restrictions.
 * Users provide their own API keys - this worker just passes them through.
 *
 * Zero cost to you - users pay for their own API usage.
 */

export default {
  async fetch(request, env, ctx) {
    // Handle CORS preflight
    if (request.method === 'OPTIONS') {
      return new Response(null, {
        headers: {
          'Access-Control-Allow-Origin': '*',
          'Access-Control-Allow-Methods': 'POST, OPTIONS',
          'Access-Control-Allow-Headers': 'Content-Type, x-api-key, Authorization, anthropic-version',
          'Access-Control-Max-Age': '86400',
        }
      });
    }

    // Only allow POST requests
    if (request.method !== 'POST') {
      return new Response('Method not allowed', { status: 405 });
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
        headers: {
          'Content-Type': 'application/json',
          'Access-Control-Allow-Origin': '*',
          'Access-Control-Allow-Methods': 'POST, OPTIONS',
          'Access-Control-Allow-Headers': 'Content-Type, x-api-key, Authorization, anthropic-version',
        }
      });

    } catch (error) {
      return new Response(JSON.stringify({ error: error.message }), {
        status: 500,
        headers: {
          'Content-Type': 'application/json',
          'Access-Control-Allow-Origin': '*',
        }
      });
    }
  }
};

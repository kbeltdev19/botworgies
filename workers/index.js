/**
 * Job Applier - Cloudflare Workers Entry Point
 * 
 * This worker serves as an API proxy and handles simple operations.
 * Complex operations (browser automation, AI) run on the backend server.
 * 
 * For full functionality, deploy:
 * 1. This worker for API routing
 * 2. Frontend to Cloudflare Pages
 * 3. Backend (Python) to a server with BrowserBase access
 */

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname;

    // CORS headers
    const corsHeaders = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    };

    // Handle CORS preflight
    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: corsHeaders });
    }

    // Health check
    if (path === '/health' || path === '/') {
      return Response.json({
        status: 'healthy',
        service: 'job-applier-worker',
        timestamp: new Date().toISOString(),
        note: 'For full functionality, ensure backend server is running'
      }, { headers: corsHeaders });
    }

    // API routes - proxy to backend
    if (path.startsWith('/api/')) {
      const backendUrl = env.BACKEND_URL || 'http://localhost:8000';
      const apiPath = path.replace('/api', '');
      
      try {
        const backendResponse = await fetch(`${backendUrl}${apiPath}${url.search}`, {
          method: request.method,
          headers: request.headers,
          body: request.method !== 'GET' ? await request.text() : undefined,
        });

        const responseHeaders = new Headers(backendResponse.headers);
        Object.entries(corsHeaders).forEach(([k, v]) => responseHeaders.set(k, v));

        return new Response(backendResponse.body, {
          status: backendResponse.status,
          headers: responseHeaders,
        });
      } catch (error) {
        return Response.json({
          error: 'Backend unavailable',
          message: error.message,
          hint: 'Ensure the Python backend server is running'
        }, { 
          status: 503,
          headers: corsHeaders 
        });
      }
    }

    // Simple in-worker operations (no backend needed)
    
    // Resume parsing hint (actual parsing needs backend)
    if (path === '/api/resume/parse-hint') {
      return Response.json({
        message: 'Resume parsing requires the full backend with Kimi AI',
        supported_formats: ['pdf', 'docx', 'txt'],
        max_size_mb: 10
      }, { headers: corsHeaders });
    }

    // Job platforms info
    if (path === '/api/platforms') {
      return Response.json({
        platforms: [
          { id: 'linkedin', name: 'LinkedIn', easy_apply: true, status: 'supported' },
          { id: 'indeed', name: 'Indeed', easy_apply: true, status: 'supported' },
          { id: 'greenhouse', name: 'Greenhouse', easy_apply: false, status: 'planned' },
          { id: 'workday', name: 'Workday', easy_apply: false, status: 'planned' },
          { id: 'lever', name: 'Lever', easy_apply: false, status: 'planned' },
        ]
      }, { headers: corsHeaders });
    }

    // Static file serving (for development)
    // In production, use Cloudflare Pages for the frontend
    if (path === '/app' || path === '/app/') {
      return Response.redirect(`${url.origin}/`, 301);
    }

    // 404 for unknown routes
    return Response.json({
      error: 'Not Found',
      path: path,
      available_routes: [
        'GET /',
        'GET /health',
        'GET /api/platforms',
        'POST /api/resume/upload',
        'POST /api/profile',
        'POST /api/jobs/search',
        'POST /api/apply',
        'GET /api/applications'
      ]
    }, { 
      status: 404,
      headers: corsHeaders 
    });
  },
};

/**
 * Durable Object for managing application queue (optional)
 * Uncomment and configure in wrangler.toml to use
 */
/*
export class ApplicationQueue {
  constructor(state, env) {
    this.state = state;
    this.env = env;
  }

  async fetch(request) {
    const url = new URL(request.url);
    
    if (url.pathname === '/enqueue' && request.method === 'POST') {
      const job = await request.json();
      const queue = await this.state.storage.get('queue') || [];
      queue.push({ ...job, id: crypto.randomUUID(), queued_at: Date.now() });
      await this.state.storage.put('queue', queue);
      return Response.json({ success: true, queue_length: queue.length });
    }

    if (url.pathname === '/dequeue' && request.method === 'POST') {
      const queue = await this.state.storage.get('queue') || [];
      if (queue.length === 0) {
        return Response.json({ job: null });
      }
      const job = queue.shift();
      await this.state.storage.put('queue', queue);
      return Response.json({ job });
    }

    if (url.pathname === '/status') {
      const queue = await this.state.storage.get('queue') || [];
      return Response.json({ queue_length: queue.length });
    }

    return new Response('Not Found', { status: 404 });
  }
}
*/

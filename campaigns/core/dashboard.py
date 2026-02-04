#!/usr/bin/env python3
"""
Real-Time Dashboard - WebSocket-based campaign monitoring.

Usage:
    python -m campaigns dashboard --port 8080
"""

import asyncio
import json
from typing import Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)

# Optional FastAPI import
try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect
    from fastapi.responses import HTMLResponse
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    logger.warning("FastAPI not available - dashboard disabled")


@dataclass
class CampaignStats:
    """Real-time campaign statistics."""
    campaign_id: str
    status: str  # 'running', 'paused', 'completed', 'error'
    
    # Progress
    jobs_scraped: int = 0
    jobs_processed: int = 0
    jobs_succeeded: int = 0
    jobs_failed: int = 0
    jobs_remaining: int = 0
    
    # Performance
    success_rate: float = 0.0
    avg_time_per_job: float = 0.0
    jobs_per_minute: float = 0.0
    
    # Resources
    active_sessions: int = 0
    queued_jobs: int = 0
    cache_hit_rate: float = 0.0
    
    # Timing
    started_at: Optional[str] = None
    estimated_completion: Optional[str] = None
    elapsed_seconds: float = 0.0
    
    # Current job
    current_job_title: str = ""
    current_job_company: str = ""
    current_job_platform: str = ""


class CampaignDashboard:
    """
    Real-time campaign monitoring dashboard.
    
    Features:
    - WebSocket for real-time updates
    - HTTP endpoint for current stats
    - Simple HTML dashboard
    """
    
    def __init__(self, port: int = 8080):
        self.port = port
        self.app: Optional[Any] = None
        self.active_connections: list = []
        self.campaign_stats: Dict[str, CampaignStats] = {}
        
        if FASTAPI_AVAILABLE:
            self._setup_fastapi()
    
    def _setup_fastapi(self):
        """Setup FastAPI application."""
        self.app = FastAPI(title="Campaign Dashboard")
        
        @self.app.get("/")
        async def get_dashboard():
            return HTMLResponse(self._get_html_dashboard())
        
        @self.app.get("/api/stats")
        async def get_stats():
            return {
                campaign_id: asdict(stats)
                for campaign_id, stats in self.campaign_stats.items()
            }
        
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await self._handle_websocket(websocket)
    
    async def _handle_websocket(self, websocket: WebSocket):
        """Handle WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        
        try:
            while True:
                # Send current stats
                stats_data = {
                    campaign_id: asdict(stats)
                    for campaign_id, stats in self.campaign_stats.items()
                }
                await websocket.send_json(stats_data)
                
                # Wait before next update
                await asyncio.sleep(5)
                
        except WebSocketDisconnect:
            self.active_connections.remove(websocket)
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
    
    def update_stats(self, campaign_id: str, **kwargs):
        """Update campaign stats."""
        if campaign_id not in self.campaign_stats:
            self.campaign_stats[campaign_id] = CampaignStats(
                campaign_id=campaign_id,
                status='running',
                started_at=datetime.now().isoformat()
            )
        
        stats = self.campaign_stats[campaign_id]
        for key, value in kwargs.items():
            if hasattr(stats, key):
                setattr(stats, key, value)
        
        # Calculate derived stats
        if stats.jobs_processed > 0:
            stats.success_rate = (stats.jobs_succeeded / stats.jobs_processed) * 100
    
    async def broadcast_update(self):
        """Broadcast stats to all connected clients."""
        if not self.active_connections:
            return
        
        stats_data = {
            campaign_id: asdict(stats)
            for campaign_id, stats in self.campaign_stats.items()
        }
        
        disconnected = []
        for conn in self.active_connections:
            try:
                await conn.send_json(stats_data)
            except:
                disconnected.append(conn)
        
        # Remove disconnected clients
        for conn in disconnected:
            if conn in self.active_connections:
                self.active_connections.remove(conn)
    
    def _get_html_dashboard(self) -> str:
        """Get HTML dashboard."""
        return '''
<!DOCTYPE html>
<html>
<head>
    <title>Campaign Dashboard</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }
        h1 { color: #333; }
        .campaign-card {
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .status-running { color: #28a745; }
        .status-paused { color: #ffc107; }
        .status-completed { color: #17a2b8; }
        .status-error { color: #dc3545; }
        .metric {
            display: inline-block;
            margin: 10px 20px 10px 0;
        }
        .metric-value {
            font-size: 24px;
            font-weight: bold;
            color: #333;
        }
        .metric-label {
            font-size: 12px;
            color: #666;
            text-transform: uppercase;
        }
        .progress-bar {
            width: 100%;
            height: 20px;
            background: #e9ecef;
            border-radius: 10px;
            overflow: hidden;
            margin-top: 10px;
        }
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #28a745, #20c997);
            transition: width 0.3s;
        }
        #connection-status {
            position: fixed;
            top: 10px;
            right: 10px;
            padding: 5px 10px;
            border-radius: 4px;
            font-size: 12px;
        }
        .connected { background: #d4edda; color: #155724; }
        .disconnected { background: #f8d7da; color: #721c24; }
    </style>
</head>
<body>
    <h1>🚀 Campaign Dashboard</h1>
    <div id="connection-status" class="disconnected">Disconnected</div>
    <div id="campaigns"></div>

    <script>
        const campaignsDiv = document.getElementById('campaigns');
        const statusDiv = document.getElementById('connection-status');
        
        function connect() {
            const ws = new WebSocket(`ws://${window.location.host}/ws`);
            
            ws.onopen = () => {
                statusDiv.textContent = 'Connected';
                statusDiv.className = 'connected';
            };
            
            ws.onclose = () => {
                statusDiv.textContent = 'Disconnected';
                statusDiv.className = 'disconnected';
                // Reconnect after 5 seconds
                setTimeout(connect, 5000);
            };
            
            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                renderCampaigns(data);
            };
        }
        
        function renderCampaigns(campaigns) {
            campaignsDiv.innerHTML = Object.entries(campaigns).map(([id, stats]) => `
                <div class="campaign-card">
                    <h2>Campaign: ${id}</h2>
                    <p>Status: <span class="status-${stats.status}">${stats.status.toUpperCase()}</span></p>
                    
                    <div class="metric">
                        <div class="metric-value">${stats.jobs_scraped}</div>
                        <div class="metric-label">Jobs Scraped</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">${stats.jobs_processed}</div>
                        <div class="metric-label">Processed</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">${stats.jobs_succeeded}</div>
                        <div class="metric-label">Succeeded</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">${stats.success_rate.toFixed(1)}%</div>
                        <div class="metric-label">Success Rate</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">${stats.jobs_per_minute.toFixed(1)}</div>
                        <div class="metric-label">Jobs/Min</div>
                    </div>
                    
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: ${(stats.jobs_processed / stats.jobs_scraped * 100) || 0}%"></div>
                    </div>
                    
                    ${stats.current_job_title ? `
                    <p style="margin-top: 10px; color: #666;">
                        Current: ${stats.current_job_title} at ${stats.current_job_company} (${stats.current_job_platform})
                    </p>
                    ` : ''}
                </div>
            `).join('');
        }
        
        connect();
    </script>
</body>
</html>
        '''
    
    async def start(self):
        """Start dashboard server."""
        if not FASTAPI_AVAILABLE:
            logger.error("FastAPI not available - cannot start dashboard")
            return
        
        import uvicorn
        
        logger.info(f"Starting dashboard on port {self.port}")
        config = uvicorn.Config(self.app, host="0.0.0.0", port=self.port, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()


# Singleton
dashboard: Optional[CampaignDashboard] = None


def get_dashboard(port: int = 8080) -> CampaignDashboard:
    """Get global dashboard instance."""
    global dashboard
    if dashboard is None:
        dashboard = CampaignDashboard(port=port)
    return dashboard


async def start_dashboard(port: int = 8080):
    """Start dashboard server."""
    dash = get_dashboard(port)
    await dash.start()

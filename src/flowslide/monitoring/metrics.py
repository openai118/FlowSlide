"""
FlowSlide Monitoring Metrics
Prometheus metrics collection for application monitoring
"""

import time
import logging
from typing import Dict, Any, Optional
from functools import wraps
from prometheus_client import (
    Counter, Histogram, Gauge, Info, 
    CollectorRegistry, generate_latest,
    CONTENT_TYPE_LATEST
)
from fastapi import Request, Response
from fastapi.responses import PlainTextResponse

logger = logging.getLogger(__name__)

# Create custom registry for FlowSlide metrics
flowslide_registry = CollectorRegistry()

# Application info
app_info = Info(
    'flowslide_app_info',
    'FlowSlide application information',
    registry=flowslide_registry
)

# HTTP metrics
http_requests_total = Counter(
    'flowslide_http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status'],
    registry=flowslide_registry
)

http_request_duration = Histogram(
    'flowslide_http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint'],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
    registry=flowslide_registry
)

# User metrics
active_users = Gauge(
    'flowslide_active_users',
    'Number of currently active users',
    registry=flowslide_registry
)

user_sessions_total = Counter(
    'flowslide_user_sessions_total',
    'Total user sessions created',
    registry=flowslide_registry
)

failed_logins_total = Counter(
    'flowslide_failed_logins_total',
    'Total failed login attempts',
    ['reason'],
    registry=flowslide_registry
)

# PPT generation metrics
ppt_generation_total = Counter(
    'flowslide_ppt_generation_total',
    'Total PPT generations',
    ['scenario', 'status'],
    registry=flowslide_registry
)

ppt_generation_duration = Histogram(
    'flowslide_ppt_generation_duration_seconds',
    'PPT generation duration in seconds',
    ['scenario'],
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0],
    registry=flowslide_registry
)

ppt_generation_failures_total = Counter(
    'flowslide_ppt_generation_failures_total',
    'Total PPT generation failures',
    ['scenario', 'error_type'],
    registry=flowslide_registry
)

# AI service metrics
ai_requests_total = Counter(
    'flowslide_ai_requests_total',
    'Total AI service requests',
    ['provider', 'model', 'status'],
    registry=flowslide_registry
)

ai_request_duration = Histogram(
    'flowslide_ai_request_duration_seconds',
    'AI request duration in seconds',
    ['provider', 'model'],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
    registry=flowslide_registry
)

ai_service_available = Gauge(
    'flowslide_ai_service_available',
    'AI service availability (1=available, 0=unavailable)',
    ['provider'],
    registry=flowslide_registry
)

ai_tokens_used_total = Counter(
    'flowslide_ai_tokens_used_total',
    'Total AI tokens used',
    ['provider', 'model', 'type'],
    registry=flowslide_registry
)

# File processing metrics
file_uploads_total = Counter(
    'flowslide_file_uploads_total',
    'Total file uploads',
    ['file_type', 'status'],
    registry=flowslide_registry
)

file_upload_size_bytes = Histogram(
    'flowslide_file_upload_size_bytes',
    'File upload size in bytes',
    ['file_type'],
    buckets=[1024, 10240, 102400, 1048576, 10485760, 104857600],  # 1KB to 100MB
    registry=flowslide_registry
)

file_processing_duration = Histogram(
    'flowslide_file_processing_duration_seconds',
    'File processing duration in seconds',
    ['file_type'],
    buckets=[0.1, 0.5, 1.0, 5.0, 10.0, 30.0],
    registry=flowslide_registry
)

file_upload_failures_total = Counter(
    'flowslide_file_upload_failures_total',
    'Total file upload failures',
    ['file_type', 'error_type'],
    registry=flowslide_registry
)

# Database metrics
database_connections_active = Gauge(
    'flowslide_database_connections_active',
    'Number of active database connections',
    registry=flowslide_registry
)

database_query_duration = Histogram(
    'flowslide_database_query_duration_seconds',
    'Database query duration in seconds',
    ['operation'],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5],
    registry=flowslide_registry
)

database_errors_total = Counter(
    'flowslide_database_errors_total',
    'Total database errors',
    ['error_type'],
    registry=flowslide_registry
)

# Cache metrics
cache_hits_total = Counter(
    'flowslide_cache_hits_total',
    'Total cache hits',
    ['cache_type'],
    registry=flowslide_registry
)

cache_misses_total = Counter(
    'flowslide_cache_misses_total',
    'Total cache misses',
    ['cache_type'],
    registry=flowslide_registry
)

# Security metrics
suspicious_requests_total = Counter(
    'flowslide_suspicious_requests_total',
    'Total suspicious requests detected',
    ['type'],
    registry=flowslide_registry
)

rate_limit_exceeded_total = Counter(
    'flowslide_rate_limit_exceeded_total',
    'Total rate limit exceeded events',
    ['endpoint'],
    registry=flowslide_registry
)


class MetricsCollector:
    """Metrics collection utilities"""
    
    def __init__(self):
        self.start_time = time.time()
        self._active_users_count = 0
        
        # Set application info
        app_info.info({
            'version': '1.0.0',
            'environment': 'production',
            'start_time': str(int(self.start_time))
        })
    
    def track_http_request(self, method: str, endpoint: str, status_code: int, duration: float):
        """Track HTTP request metrics"""
        http_requests_total.labels(
            method=method,
            endpoint=endpoint,
            status=str(status_code)
        ).inc()
        
        http_request_duration.labels(
            method=method,
            endpoint=endpoint
        ).observe(duration)
    
    def track_user_session(self, action: str, reason: Optional[str] = None):
        """Track user session metrics"""
        if action == "login_success":
            user_sessions_total.inc()
            self._active_users_count += 1
            active_users.set(self._active_users_count)
        elif action == "login_failed":
            failed_logins_total.labels(reason=reason or "unknown").inc()
        elif action == "logout":
            self._active_users_count = max(0, self._active_users_count - 1)
            active_users.set(self._active_users_count)
    
    def track_ppt_generation(self, scenario: str, status: str, duration: Optional[float] = None, 
                           error_type: Optional[str] = None):
        """Track PPT generation metrics"""
        ppt_generation_total.labels(scenario=scenario, status=status).inc()
        
        if duration is not None:
            ppt_generation_duration.labels(scenario=scenario).observe(duration)
        
        if status == "failed" and error_type:
            ppt_generation_failures_total.labels(
                scenario=scenario,
                error_type=error_type
            ).inc()
    
    def track_ai_request(self, provider: str, model: str, status: str, duration: float,
                        tokens_used: Optional[Dict[str, int]] = None):
        """Track AI service request metrics"""
        ai_requests_total.labels(
            provider=provider,
            model=model,
            status=status
        ).inc()
        
        ai_request_duration.labels(
            provider=provider,
            model=model
        ).observe(duration)
        
        if tokens_used:
            for token_type, count in tokens_used.items():
                ai_tokens_used_total.labels(
                    provider=provider,
                    model=model,
                    type=token_type
                ).inc(count)
    
    def set_ai_service_status(self, provider: str, available: bool):
        """Set AI service availability status"""
        ai_service_available.labels(provider=provider).set(1 if available else 0)
    
    def track_file_upload(self, file_type: str, status: str, size_bytes: int,
                         processing_duration: Optional[float] = None,
                         error_type: Optional[str] = None):
        """Track file upload metrics"""
        file_uploads_total.labels(file_type=file_type, status=status).inc()
        file_upload_size_bytes.labels(file_type=file_type).observe(size_bytes)
        
        if processing_duration is not None:
            file_processing_duration.labels(file_type=file_type).observe(processing_duration)
        
        if status == "failed" and error_type:
            file_upload_failures_total.labels(
                file_type=file_type,
                error_type=error_type
            ).inc()
    
    def track_database_operation(self, operation: str, duration: float, error_type: Optional[str] = None):
        """Track database operation metrics"""
        database_query_duration.labels(operation=operation).observe(duration)
        
        if error_type:
            database_errors_total.labels(error_type=error_type).inc()
    
    def track_cache_operation(self, cache_type: str, hit: bool):
        """Track cache operation metrics"""
        if hit:
            cache_hits_total.labels(cache_type=cache_type).inc()
        else:
            cache_misses_total.labels(cache_type=cache_type).inc()
    
    def track_security_event(self, event_type: str, endpoint: Optional[str] = None):
        """Track security-related events"""
        if event_type == "suspicious_request":
            suspicious_requests_total.labels(type="general").inc()
        elif event_type == "rate_limit_exceeded" and endpoint:
            rate_limit_exceeded_total.labels(endpoint=endpoint).inc()


# Global metrics collector instance
metrics_collector = MetricsCollector()


def metrics_endpoint():
    """Prometheus metrics endpoint"""
    return PlainTextResponse(
        generate_latest(flowslide_registry),
        headers={"Content-Type": CONTENT_TYPE_LATEST}
    )


def track_request_metrics(func):
    """Decorator to track request metrics"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        
        try:
            result = await func(*args, **kwargs)
            duration = time.time() - start_time
            
            # Extract request info if available
            request = kwargs.get('request') or (args[0] if args and isinstance(args[0], Request) else None)
            if request:
                metrics_collector.track_http_request(
                    method=request.method,
                    endpoint=request.url.path,
                    status_code=200,  # Assume success if no exception
                    duration=duration
                )
            
            return result
        except Exception as e:
            duration = time.time() - start_time
            
            # Track error
            request = kwargs.get('request') or (args[0] if args and isinstance(args[0], Request) else None)
            if request:
                metrics_collector.track_http_request(
                    method=request.method,
                    endpoint=request.url.path,
                    status_code=500,  # Assume server error
                    duration=duration
                )
            
            raise
    
    return wrapper

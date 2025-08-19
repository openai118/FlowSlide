"""
FlowSlide API Performance Tests
Focused on API endpoints only (no web interface)
"""

import json
import random
import time

from locust import HttpUser, between, events, task
from locust.exception import RescheduleTask


class APIOnlyUser(HttpUser):
    """Pure API user - no web interface interaction"""

    wait_time = between(0.5, 2)

    def on_start(self):
        """Login via API to get session"""
        self.login()

    def login(self):
        """API login"""
        response = self.client.post(
            "/auth/login",
            data={"username": "admin", "password": "admin123456"},
            allow_redirects=False,
        )

        if response.status_code not in [200, 302]:
            raise RescheduleTask()

    @task(10)
    def health_check(self):
        """Health check endpoint"""
        self.client.get("/health")

    @task(8)
    def get_version(self):
        """Version endpoint"""
        self.client.get("/api/version")

    @task(6)
    def list_projects(self):
        """List projects"""
        self.client.get("/api/projects")

    @task(4)
    def get_ai_providers(self):
        """Get AI providers configuration"""
        self.client.get("/api/config/ai-providers")

    @task(3)
    def search_images(self):
        """Image search API"""
        queries = ["business", "technology", "chart", "graph", "presentation"]
        query = random.choice(queries)
        self.client.get(f"/api/images/search?query={query}&count=5")

    @task(2)
    def generate_presentation(self):
        """Generate presentation via API"""
        scenarios = ["business_report", "academic_presentation", "training_material"]
        topics = ["API Performance Test", "System Analysis", "Technical Review"]

        payload = {
            "scenario": random.choice(scenarios),
            "topic": random.choice(topics),
            "requirements": "Performance test presentation",
            "slide_count": random.randint(3, 8),
            "ai_provider": "openai",
        }

        with self.client.post("/api/generate", json=payload, catch_response=True) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if data.get("success"):
                        response.success()
                        self.project_id = data.get("project_id")
                    else:
                        response.failure(f"Generation failed: {data.get('message')}")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            else:
                response.failure(f"HTTP {response.status_code}")

    @task(1)
    def check_generation_status(self):
        """Check generation status"""
        if hasattr(self, "project_id") and self.project_id:
            self.client.get(f"/api/generate/status/{self.project_id}")


class OpenAICompatibleUser(HttpUser):
    """Test OpenAI-compatible API endpoints"""

    wait_time = between(1, 3)
    weight = 2

    def on_start(self):
        """Setup for OpenAI API testing"""
        self.api_key = "test-api-key"

    @task(5)
    def chat_completions(self):
        """Test chat completions endpoint"""
        prompts = [
            "Generate a presentation outline about AI",
            "Create slides about data analysis",
            "Outline a business proposal presentation",
            "Generate content for a technical review",
        ]

        payload = {
            "model": "gpt-3.5-turbo",
            "messages": [{"role": "user", "content": random.choice(prompts)}],
            "max_tokens": 200,
            "temperature": 0.7,
        }

        headers = {"Authorization": f"Bearer {self.api_key}"}

        with self.client.post(
            "/v1/chat/completions", json=payload, headers=headers, catch_response=True
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if "choices" in data:
                        response.success()
                    else:
                        response.failure("Invalid response format")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            else:
                response.failure(f"HTTP {response.status_code}")


class DatabaseAPIUser(HttpUser):
    """Test database-related API endpoints"""

    wait_time = between(1, 4)
    weight = 1

    def on_start(self):
        """Login for database API access"""
        response = self.client.post(
            "/auth/login",
            data={"username": "admin", "password": "admin123456"},
            allow_redirects=False,
        )

        if response.status_code not in [200, 302]:
            raise RescheduleTask()

    @task(3)
    def database_status(self):
        """Check database status"""
        self.client.get("/api/database/status")

    @task(2)
    def database_health(self):
        """Database health check"""
        self.client.get("/api/database/health")

    @task(1)
    def database_stats(self):
        """Get database statistics"""
        self.client.get("/api/database/stats")


class FileUploadAPIUser(HttpUser):
    """Test file upload API performance"""

    wait_time = between(2, 6)
    weight = 1

    def on_start(self):
        """Login for file upload"""
        response = self.client.post(
            "/auth/login",
            data={"username": "admin", "password": "admin123456"},
            allow_redirects=False,
        )

        if response.status_code not in [200, 302]:
            raise RescheduleTask()

    @task(1)
    def upload_small_file(self):
        """Upload small text file"""
        content = "Performance test document. " * 50  # Small file
        files = {"file": ("small_test.txt", content, "text/plain")}

        with self.client.post("/api/upload", files=files, catch_response=True) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if data.get("success"):
                        response.success()
                        self.file_id = data.get("file_id")
                    else:
                        response.failure(f"Upload failed: {data.get('message')}")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            else:
                response.failure(f"HTTP {response.status_code}")

    @task(1)
    def upload_medium_file(self):
        """Upload medium-sized file"""
        content = "Performance test document with more content. " * 500  # Medium file
        files = {"file": ("medium_test.txt", content, "text/plain")}

        with self.client.post("/api/upload", files=files, catch_response=True) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if data.get("success"):
                        response.success()
                    else:
                        response.failure(f"Upload failed: {data.get('message')}")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            else:
                response.failure(f"HTTP {response.status_code}")


class MetricsUser(HttpUser):
    """Test monitoring and metrics endpoints"""

    wait_time = between(5, 15)  # Less frequent metrics checking
    weight = 1

    @task(1)
    def prometheus_metrics(self):
        """Get Prometheus metrics"""
        self.client.get("/metrics")

    @task(1)
    def health_detailed(self):
        """Detailed health check"""
        self.client.get("/health")


# Performance test events for API testing
@events.test_start.add_listener
def on_api_test_start(environment, **kwargs):
    """Called when API test starts"""
    print("🚀 Starting FlowSlide API Performance Test")
    print(f"Target: {environment.host}")
    print("Focus: API endpoints only")


@events.test_stop.add_listener
def on_api_test_stop(environment, **kwargs):
    """Called when API test stops"""
    print("🏁 FlowSlide API Performance Test Completed")

    stats = environment.runner.stats
    print(f"\n📊 API Performance Summary:")
    print(f"Total API requests: {stats.total.num_requests}")
    print(f"Failed API requests: {stats.total.num_failures}")
    print(f"Average API response time: {stats.total.avg_response_time:.2f}ms")
    print(f"95th percentile: {stats.total.get_response_time_percentile(0.95):.2f}ms")
    print(f"API requests per second: {stats.total.current_rps:.2f}")

    # API-specific performance thresholds
    if stats.total.avg_response_time > 1000:  # 1 second
        print("⚠️ WARNING: Average API response time exceeds 1 second")

    if stats.total.get_response_time_percentile(0.95) > 3000:  # 3 seconds
        print("⚠️ WARNING: 95th percentile API response time exceeds 3 seconds")

    failure_rate = (
        (stats.total.num_failures / stats.total.num_requests) * 100
        if stats.total.num_requests > 0
        else 0
    )
    if failure_rate > 1:  # 1% failure rate
        print(f"⚠️ WARNING: API failure rate is {failure_rate:.2f}%")


@events.request.add_listener
def on_api_request(
    request_type, name, response_time, response_length, exception, context, **kwargs
):
    """Monitor API requests"""
    # Log slow API requests
    if response_time > 2000:  # 2 seconds
        print(f"🐌 Slow API request: {name} - {response_time:.2f}ms")

    # Log API errors
    if exception:
        print(f"❌ API request failed: {name} - {exception}")


if __name__ == "__main__":
    print("FlowSlide API Performance Test Configuration:")
    print("- APIOnlyUser: Core API endpoints")
    print("- OpenAICompatibleUser: OpenAI-compatible API")
    print("- DatabaseAPIUser: Database-related endpoints")
    print("- FileUploadAPIUser: File upload performance")
    print("- MetricsUser: Monitoring endpoints")
    print("\nRun with: locust -f api_performance.py --host=http://localhost:8000")

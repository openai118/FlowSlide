"""
FlowSlide Performance Tests using Locust
Run with: locust -f tests/performance/locustfile.py --host=http://localhost:8000
"""

import json
import random
import time

from locust import HttpUser, between, events, task
from locust.exception import RescheduleTask


class FlowSlideUser(HttpUser):
    """Simulates a FlowSlide user performing various operations"""

    wait_time = between(1, 5)  # Wait 1-5 seconds between tasks

    def on_start(self):
        """Called when a user starts - login to get session"""
        self.login()

    def login(self):
        """Login to get session cookie"""
        response = self.client.post(
            "/auth/login",
            data={"username": "admin", "password": "admin123456"},
            allow_redirects=False,
        )

        if response.status_code not in [200, 302]:
            print(f"Login failed with status {response.status_code}")
            raise RescheduleTask()

    @task(3)
    def view_home_page(self):
        """View the home page"""
        self.client.get("/home")

    @task(2)
    def check_health(self):
        """Check application health"""
        self.client.get("/health")

    @task(2)
    def get_version(self):
        """Get application version"""
        self.client.get("/api/version")

    @task(1)
    def view_scenarios(self):
        """View available scenarios"""
        self.client.get("/scenarios")

    @task(4)
    def list_projects(self):
        """List user projects"""
        self.client.get("/api/projects")

    @task(1)
    def get_ai_providers(self):
        """Get available AI providers"""
        self.client.get("/api/config/ai-providers")

    @task(2)
    def search_images(self):
        """Search for images"""
        queries = ["business", "technology", "presentation", "chart", "graph"]
        query = random.choice(queries)
        self.client.get(f"/api/images/search?query={query}&count=5")

    @task(1)
    def generate_presentation(self):
        """Generate a presentation (most resource-intensive operation)"""
        scenarios = [
            "business_report",
            "academic_presentation",
            "training_material",
            "marketing_pitch",
        ]

        topics = [
            "Q4 Sales Performance",
            "Machine Learning Overview",
            "Product Launch Strategy",
            "Team Training Program",
        ]

        payload = {
            "scenario": random.choice(scenarios),
            "topic": random.choice(topics),
            "requirements": "Include key points and visual elements",
            "slide_count": random.randint(5, 15),
            "ai_provider": "openai",
        }

        with self.client.post("/api/generate", json=payload, catch_response=True) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if data.get("success"):
                        response.success()
                        # Store project_id for status checking
                        self.project_id = data.get("project_id")
                    else:
                        response.failure(f"Generation failed: {data.get('message')}")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            else:
                response.failure(f"HTTP {response.status_code}")

    @task(1)
    def check_generation_status(self):
        """Check generation status if we have a project_id"""
        if hasattr(self, "project_id") and self.project_id:
            self.client.get(f"/api/generate/status/{self.project_id}")


class AdminUser(HttpUser):
    """Simulates admin user performing administrative tasks"""

    wait_time = between(2, 8)
    weight = 1  # Lower weight means fewer admin users

    def on_start(self):
        """Login as admin"""
        response = self.client.post(
            "/auth/login",
            data={"username": "admin", "password": "admin123456"},
            allow_redirects=False,
        )

        if response.status_code not in [200, 302]:
            raise RescheduleTask()

    @task(2)
    def view_admin_dashboard(self):
        """View admin dashboard"""
        self.client.get("/web")

    @task(1)
    def check_metrics(self):
        """Check Prometheus metrics"""
        self.client.get("/metrics")

    @task(1)
    def view_database_status(self):
        """Check database status"""
        self.client.get("/api/database/status")


class APIUser(HttpUser):
    """Simulates API-only usage (no web interface)"""

    wait_time = between(0.5, 2)
    weight = 2

    def on_start(self):
        """Login via API"""
        response = self.client.post(
            "/auth/login",
            data={"username": "admin", "password": "admin123456"},
            allow_redirects=False,
        )

        if response.status_code not in [200, 302]:
            raise RescheduleTask()

    @task(5)
    def api_health_check(self):
        """API health check"""
        self.client.get("/health")

    @task(3)
    def api_list_projects(self):
        """List projects via API"""
        self.client.get("/api/projects")

    @task(2)
    def api_get_config(self):
        """Get configuration via API"""
        self.client.get("/api/config/ai-providers")

    @task(1)
    def openai_compatible_api(self):
        """Test OpenAI-compatible API"""
        payload = {
            "model": "gpt-3.5-turbo",
            "messages": [{"role": "user", "content": "Generate a brief presentation outline"}],
            "max_tokens": 100,
        }

        self.client.post(
            "/v1/chat/completions", json=payload, headers={"Authorization": "Bearer test-key"}
        )


# Performance test event handlers
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when test starts"""
    print("🚀 Starting FlowSlide performance test")
    print(f"Target host: {environment.host}")
    print(f"Users: {environment.runner.target_user_count}")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when test stops"""
    print("🏁 FlowSlide performance test completed")

    # Print summary statistics
    stats = environment.runner.stats
    print(f"\n📊 Performance Summary:")
    print(f"Total requests: {stats.total.num_requests}")
    print(f"Failed requests: {stats.total.num_failures}")
    print(f"Average response time: {stats.total.avg_response_time:.2f}ms")
    print(f"95th percentile: {stats.total.get_response_time_percentile(0.95):.2f}ms")
    print(f"Requests per second: {stats.total.current_rps:.2f}")


@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, context, **kwargs):
    """Called for each request - can be used for custom metrics"""
    if exception:
        print(f"❌ Request failed: {name} - {exception}")
    elif response_time > 5000:  # Log slow requests (>5s)
        print(f"🐌 Slow request: {name} - {response_time:.2f}ms")


# Custom test scenarios
class StressTestUser(HttpUser):
    """High-intensity stress test user"""

    wait_time = between(0.1, 0.5)  # Very short wait times
    weight = 1

    def on_start(self):
        self.login()

    def login(self):
        response = self.client.post(
            "/auth/login",
            data={"username": "admin", "password": "admin123456"},
            allow_redirects=False,
        )

        if response.status_code not in [200, 302]:
            raise RescheduleTask()

    @task(10)
    def rapid_health_checks(self):
        """Rapid health check requests"""
        self.client.get("/health")

    @task(5)
    def rapid_api_calls(self):
        """Rapid API calls"""
        endpoints = ["/api/version", "/api/projects", "/api/config/ai-providers"]
        endpoint = random.choice(endpoints)
        self.client.get(endpoint)


class FileUploadUser(HttpUser):
    """Simulates file upload operations"""

    wait_time = between(2, 10)
    weight = 1

    def on_start(self):
        self.login()

    def login(self):
        response = self.client.post(
            "/auth/login",
            data={"username": "admin", "password": "admin123456"},
            allow_redirects=False,
        )

        if response.status_code not in [200, 302]:
            raise RescheduleTask()

    @task(1)
    def upload_file(self):
        """Simulate file upload"""
        # Create a dummy file content
        file_content = "This is a test document for performance testing. " * 100

        files = {"file": ("test_document.txt", file_content, "text/plain")}

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


# Test configuration for different scenarios
if __name__ == "__main__":
    print("FlowSlide Performance Test Configuration:")
    print("- FlowSlideUser: General user simulation")
    print("- AdminUser: Administrative operations")
    print("- APIUser: API-only usage")
    print("- StressTestUser: High-intensity stress testing")
    print("- FileUploadUser: File upload operations")
    print("\nRun with: locust -f locustfile.py --host=http://localhost:8000")

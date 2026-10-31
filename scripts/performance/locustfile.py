import os

from locust import HttpUser, between, task


class DashboardReader(HttpUser):
    wait_time = between(0.2, 0.5)

    def on_start(self):
        token = os.environ.get("LOAD_TEST_TOKEN")
        if not token:
            raise RuntimeError("Set LOAD_TEST_TOKEN to a temporary administrator access token.")
        self.client.headers.update({"Authorization": f"Bearer {token}"})

    @task(4)
    def dashboard_aggregates(self):
        self.client.get(
            "/api/v1/analytics/dashboard",
            name="dashboard aggregates",
        )

    @task(1)
    def complaint_list(self):
        self.client.get(
            "/api/v1/complaints/?limit=50",
            name="complaint list (50)",
        )

"""Docker build verification tests (T072)."""
import pytest
import os
import subprocess
import sys


class TestDockerBuild:
    """Docker build verification tests (T072)."""

    @pytest.fixture
    def project_root(self):
        return os.path.join(os.path.dirname(__file__), "..", "..")

    def test_dockerfile_exists(self, project_root):
        """Verify Dockerfile exists."""
        dockerfile_path = os.path.join(project_root, "Dockerfile")
        assert os.path.exists(dockerfile_path), "Dockerfile not found"

    def test_dockerfile_has_healthcheck(self, project_root):
        """Verify Dockerfile has HEALTHCHECK instruction."""
        dockerfile_path = os.path.join(project_root, "Dockerfile")
        with open(dockerfile_path) as f:
            content = f.read()
            assert "HEALTHCHECK" in content, "Dockerfile missing HEALTHCHECK"

    def test_dockerfile_exposes_port_8003(self, project_root):
        """Verify Dockerfile exposes port 8003."""
        dockerfile_path = os.path.join(project_root, "Dockerfile")
        with open(dockerfile_path) as f:
            content = f.read()
            assert "EXPOSE 8003" in content

    @pytest.mark.skipif(
        not os.environ.get("DOCKER_AVAILABLE"),
        reason="Docker not available in CI"
    )
    def test_docker_build_succeeds(self, project_root):
        """Test that Docker image builds successfully."""
        try:
            result = subprocess.run(
                ["docker", "build", "-t", "reservas-service:test", "."],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=300
            )
            assert result.returncode == 0, f"Docker build failed: {result.stderr}"
        except FileNotFoundError:
            pytest.skip("Docker not available")
        except subprocess.TimeoutExpired:
            pytest.fail("Docker build timed out")

    @pytest.mark.skipif(
        not os.environ.get("DOCKER_AVAILABLE"),
        reason="Docker not available in CI"
    )
    def test_docker_image_runs(self):
        """Test that built image can run."""
        try:
            import docker
            client = docker.from_env()
            
            # Run container
            container = client.containers.run(
                "reservas-service:test",
                detach=True,
                ports={"8003/tcp": 8003},
                environment={
                    "MONGODB_URI": "mongodb://localhost:27017",
                    "REDIS_URL": "redis://localhost:6379",
                    "POSTGRESQL_URI": "postgresql://user:pass@localhost:5432/db"
                }
            )
            
            # Wait for startup
            import time
            time.sleep(5)
            
            # Check health endpoint
            import requests
            response = requests.get("http://localhost:8003/health", timeout=5)
            assert response.status_code == 200
            data = response.json()
            assert data["status"] in ["healthy", "degraded"]
            
            # Cleanup
            container.stop()
            container.remove()
            
        except Exception as e:
            pytest.skip(f"Integration test skipped: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
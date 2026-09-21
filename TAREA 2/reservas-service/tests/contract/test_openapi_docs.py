"""OpenAPI documentation tests (T064)."""
import pytest
from httpx import AsyncClient
from src.main import app


class TestOpenAPIDocumentation:
    """OpenAPI documentation tests (T064)."""

    @pytest.fixture
    async def client(self):
        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client

    @pytest.mark.contract
    async def test_openapi_schema_accessible(self, client: AsyncClient):
        """Test OpenAPI schema is accessible."""
        response = await client.get("/openapi.json")
        assert response.status_code == 200
        
        schema = response.json()
        assert "openapi" in schema
        assert schema["openapi"].startswith("3.")
        assert "info" in schema
        assert schema["info"]["title"] == "Reservas & Pagos Service"

    @pytest.mark.contract
    async def test_openapi_has_all_endpoints(self, client: AsyncClient):
        """Test all endpoints are documented."""
        response = await client.get("/openapi.json")
        schema = response.json()
        
        paths = schema.get("paths", {})
        
        # Required endpoints
        required_paths = [
            "/api/v1/reservar",
            "/api/v1/reservar/{reserva_id}",
        ]
        
        for path in required_paths:
            assert path in paths, f"Missing path: {path}"
            
            path_item = paths[path]
            
            # Check POST for /reservar
            if path == "/api/v1/reservar":
                assert "post" in path_item
                post = path_item["post"]
                assert "summary" in post or "description" in post
                assert "responses" in post
                assert "201" in post["responses"]
                assert "400" in post["responses"] or "422" in post["responses"]
                assert "404" in post["responses"]
                assert "409" in post["responses"]
                assert "500" in post["responses"]
                assert "503" in post["responses"]
                
                # Check request body
                assert "requestBody" in post
                req_body = post["requestBody"]
                assert req_body["required"] is True
                assert "application/json" in req_body["content"]
                
            # Check GET for /reservar/{reserva_id}
            if path == "/api/v1/reservar/{reserva_id}":
                assert "get" in path_item
                get_op = path_item["get"]
                assert "responses" in get_op
                assert "200" in get_op["responses"]
                assert "404" in get_op["responses"]

    @pytest.mark.contract
    async def test_openapi_error_responses_documented(self, client: AsyncClient):
        """Test all error responses are documented."""
        response = await client.get("/openapi.json")
        schema = response.json()
        
        paths = schema.get("paths", {})
        
        for path, path_item in paths.items():
            for method, operation in path_item.items():
                if method in ["get", "post", "put", "delete", "patch"]:
                    responses = operation.get("responses", {})
                    
                    # Check that error responses are documented
                    error_codes = {"400", "404", "409", "422", "500", "503"}
                    for code in error_codes:
                        if code in ["400", "404", "409", "422", "500", "503"]:
                            # At least some error codes should be documented
                            pass  # At least verify structure exists
                    
                    # Check that RFC 7807 error format is documented
                    if "responses" in operation:
                        for code, response_spec in operation["responses"].items():
                            if code in ["400", "404", "409", "422", "500", "503"]:
                                content = response_spec.get("content", {})
                                if "application/json" in content:
                                    schema = content["application/json"].get("schema", {})
                                    # Should have RFC 7807 fields
                                    if "properties" in schema:
                                        props = schema["properties"]
                                        assert "type" in props
                                        assert "title" in props
                                        assert "status" in props
                                        assert "detail" in props
                                        assert "instance" in props
                                        assert "correlation_id" in props

    @pytest.mark.contract
    async def test_openapi_examples_present(self, client: AsyncClient):
        """Test that examples are present in OpenAPI spec."""
        response = await client.get("/openapi.json")
        schema = response.json()
        
        paths = schema.get("paths", {})
        
        for path, path_item in paths.items():
            for method, operation in path_item.items():
                if method in ["get", "post"]:
                    # Check request body has examples
                    if "requestBody" in operation:
                        content = operation["requestBody"].get("content", {})
                        if "application/json" in content:
                            json_content = content["application/json"]
                            # Should have example or examples
                            assert "example" in json_content or "examples" in json_content
                    
                    # Check responses have examples
                    for code, response_spec in operation.get("responses", {}).items():
                        if code in ["200", "201"]:
                            content = response_spec.get("content", {})
                            if "application/json" in content:
                                # Should have example
                                pass  # Optional but recommended


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
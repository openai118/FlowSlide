"""
pytest configuration and fixtures for FlowSlide tests
"""
import asyncio
import os
import sys
import tempfile
from pathlib import Path
from typing import AsyncGenerator
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession
from flowslide.database.database import create_async_engine_safe
from sqlalchemy.orm import sessionmaker
from flowslide.auth.auth_service import AuthService
from flowslide.database.database import get_async_db, get_db
from flowslide.database.models import Base
from flowslide.main import app
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
@pytest.fixture
def temp_db_file():
    """Create a temporary database file for testing"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        temp_db_path = f.name

    yield temp_db_path

    # Cleanup
    if os.path.exists(temp_db_path):
        os.unlink(temp_db_path)
@pytest.fixture
def test_engine(temp_db_file):
    """Create a test database engine"""
    database_url = f"sqlite:///{temp_db_file}"
    engine = create_engine(database_url, connect_args={"check_same_thread": False}, echo=False)
    # Create all tables
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()
@pytest.fixture
def test_async_engine(temp_db_file):
    """Create a test async database engine"""
    database_url = f"sqlite+aiosqlite:///{temp_db_file}"
    async_engine = create_async_engine_safe(database_url, echo=False)
    yield async_engine
    # Note: async engine cleanup is handled by pytest-asyncio
@pytest.fixture
def test_session(test_engine):
    """Create a test database session"""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
@pytest_asyncio.fixture
async def test_async_session(test_async_engine):
    """Create a test async database session"""
    from sqlalchemy.ext.asyncio import async_sessionmaker
    # Create tables
    async with test_async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    TestingAsyncSessionLocal = async_sessionmaker(
        test_async_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with TestingAsyncSessionLocal() as session:
        yield session
@pytest.fixture
def override_get_db(test_session):
    """Override the get_db dependency for testing"""

    def _override_get_db():
        try:
            yield test_session
        finally:
            pass  # Session cleanup handled by test_session fixture
    return _override_get_db
@pytest.fixture
def override_get_async_db(test_async_session):
    """Override the get_async_db dependency for testing"""
    async def _override_get_async_db():
        yield test_async_session
    return _override_get_async_db
@pytest.fixture
def client(override_get_db, override_get_async_db):
    """Create a test client with database overrides"""
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_async_db] = override_get_async_db
    with TestClient(app) as test_client:
        yield test_client
    # Cleanup
    app.dependency_overrides.clear()
@pytest.fixture
def auth_service(test_session):
    """Create an AuthService instance for testing"""
    return AuthService()
@pytest.fixture
def test_user_data():
    """Test user data"""
    return {"username": "testuser", "password": "testpassword123", "email": "test@example.com"}
@pytest.fixture
def test_admin_data():
    """Test admin user data"""
    return {
        "username": "testadmin",
        "password": "adminpassword123",
        "email": "admin@example.com",
        "is_admin": True,
    }
@pytest.fixture
def sample_ppt_request():
    """Sample PPT generation request data"""
    return {
        "scenario": "business_report",
        "topic": "Q4 Sales Performance",
        "requirements": "Include charts and key metrics",
        "slide_count": 10,
    }
@pytest.fixture
def sample_file_upload():
    """Sample file upload data"""
    return {
        "filename": "test_document.txt",
        "content": "This is a test document content for processing.",
        "content_type": "text/plain",
    }
@pytest.fixture(autouse=True)
def setup_test_environment():
    """Setup test environment variables"""
    # Set test environment variables
    os.environ["TESTING"] = "true"
    os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only"
    os.environ["DATABASE_URL"] = "sqlite:///./test.db"
    yield
    # Cleanup test environment
    test_vars = ["TESTING", "SECRET_KEY", "DATABASE_URL"]
    for var in test_vars:
        if var in os.environ:
            del os.environ[var]
@pytest.fixture
def mock_ai_response():
    """Mock AI response for testing"""
    return {
        "choices": [{"message": {"content": "This is a mock AI response for testing purposes."}}]
    }
@pytest.fixture
def temp_upload_dir():
    """Create a temporary upload directory"""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir
# Async test utilities
@pytest_asyncio.fixture
async def async_client():
    """Create an async test client"""
    from httpx import AsyncClient
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
# Performance testing fixtures
@pytest.fixture
def performance_config():
    """Configuration for performance tests"""
    return {
        "max_response_time": 1.0,  # seconds
        "concurrent_requests": 10,
        "test_duration": 30,  # seconds
    }
# Mock fixtures for external services
@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for testing"""
    from unittest.mock import Mock
    mock_client = Mock()
    mock_client.chat.completions.create.return_value = Mock(
        choices=[Mock(message=Mock(content="Mock AI response"))]
    )
    return mock_client
@pytest.fixture
def mock_image_service():
    """Mock image service for testing"""
    from unittest.mock import Mock
    mock_service = Mock()
    mock_service.search_images.return_value = [
        {"id": "test_image_1", "url": "https://example.com/image1.jpg", "title": "Test Image 1"}
    ]
    return mock_service

# FlowSlide API Documentation

## Overview

FlowSlide provides a comprehensive REST API for AI-powered presentation generation. The API supports multiple AI providers, file processing, user management, and real-time monitoring.

## Base URL

```
http://localhost:8000
```

## Authentication

FlowSlide uses session-based authentication. Users must log in to receive a session cookie that authenticates subsequent requests.

### Login
```http
POST /auth/login
Content-Type: application/x-www-form-urlencoded

username=your_username&password=your_password
```

### Register
```http
POST /auth/register
Content-Type: application/x-www-form-urlencoded

username=new_username&password=new_password&email=user@example.com
```

### Logout
```http
POST /auth/logout
```

## Core Endpoints

### Health Check
```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "FlowSlide API"
}
```

### Version Information
```http
GET /api/version
```

**Response:**
```json
{
  "version": "1.0.0"
}
```

### Metrics (Prometheus)
```http
GET /metrics
```

Returns Prometheus-formatted metrics for monitoring.

## PPT Generation API

### Generate Presentation
```http
POST /api/generate
Content-Type: application/json
Authorization: Session cookie required

{
  "scenario": "business_report",
  "topic": "Q4 Sales Performance",
  "requirements": "Include charts and key metrics",
  "slide_count": 10,
  "ai_provider": "openai",
  "model": "gpt-3.5-turbo"
}
```

**Parameters:**
- `scenario` (string): Presentation scenario type
  - `business_report`: Business presentations
  - `academic_presentation`: Academic/research presentations
  - `training_material`: Training and educational content
  - `marketing_pitch`: Marketing and sales pitches
  - `project_proposal`: Project proposals
  - `technical_documentation`: Technical documentation

- `topic` (string): Main topic/title of the presentation
- `requirements` (string): Specific requirements and guidelines
- `slide_count` (integer): Number of slides to generate (1-50)
- `ai_provider` (string, optional): AI provider to use
  - `openai`: OpenAI GPT models
  - `anthropic`: Anthropic Claude models
  - `google`: Google Gemini models
  - `azure`: Azure OpenAI
  - `ollama`: Local Ollama models

- `model` (string, optional): Specific model to use

**Response:**
```json
{
  "success": true,
  "project_id": "proj_abc123",
  "status": "generating",
  "message": "Presentation generation started",
  "estimated_time": 30
}
```

### Get Generation Status
```http
GET /api/generate/status/{project_id}
```

**Response:**
```json
{
  "project_id": "proj_abc123",
  "status": "completed",
  "progress": 100,
  "current_step": "Finalizing presentation",
  "slides_generated": 10,
  "download_url": "/api/download/proj_abc123"
}
```

### Download Presentation
```http
GET /api/download/{project_id}
```

Returns the generated presentation file.

## File Upload API

### Upload File
```http
POST /api/upload
Content-Type: multipart/form-data
Authorization: Session cookie required

file: [binary file data]
```

**Supported file types:**
- `.docx` - Microsoft Word documents
- `.pdf` - PDF documents
- `.txt` - Plain text files
- `.md` - Markdown files

**Response:**
```json
{
  "success": true,
  "file_id": "file_xyz789",
  "filename": "document.docx",
  "size": 1024000,
  "content_preview": "Document content preview...",
  "processing_status": "completed"
}
```

### Generate from File
```http
POST /api/generate/from-file
Content-Type: application/json
Authorization: Session cookie required

{
  "file_id": "file_xyz789",
  "scenario": "business_report",
  "slide_count": 15,
  "additional_requirements": "Focus on key findings"
}
```

## Project Management API

### List Projects
```http
GET /api/projects
Authorization: Session cookie required
```

**Query Parameters:**
- `page` (integer): Page number (default: 1)
- `limit` (integer): Items per page (default: 20)
- `status` (string): Filter by status
- `scenario` (string): Filter by scenario

**Response:**
```json
{
  "projects": [
    {
      "project_id": "proj_abc123",
      "title": "Q4 Sales Report",
      "scenario": "business_report",
      "status": "completed",
      "created_at": "2023-12-01T10:00:00Z",
      "updated_at": "2023-12-01T10:30:00Z",
      "slide_count": 10
    }
  ],
  "total": 1,
  "page": 1,
  "pages": 1
}
```

### Get Project Details
```http
GET /api/projects/{project_id}
Authorization: Session cookie required
```

**Response:**
```json
{
  "project_id": "proj_abc123",
  "title": "Q4 Sales Report",
  "scenario": "business_report",
  "topic": "Q4 Sales Performance",
  "requirements": "Include charts and key metrics",
  "status": "completed",
  "outline": {
    "slides": [
      {
        "title": "Introduction",
        "content": "Welcome to Q4 Sales Review"
      }
    ]
  },
  "created_at": "2023-12-01T10:00:00Z",
  "updated_at": "2023-12-01T10:30:00Z"
}
```

### Delete Project
```http
DELETE /api/projects/{project_id}
Authorization: Session cookie required
```

## Image Search API

### Search Images
```http
GET /api/images/search
Authorization: Session cookie required
```

**Query Parameters:**
- `query` (string): Search query
- `count` (integer): Number of images (default: 10, max: 50)
- `category` (string): Image category
- `orientation` (string): Image orientation (horizontal, vertical, square)

**Response:**
```json
{
  "images": [
    {
      "id": "img_123",
      "url": "https://example.com/image.jpg",
      "thumbnail_url": "https://example.com/thumb.jpg",
      "title": "Business Meeting",
      "description": "Professional business meeting",
      "width": 1920,
      "height": 1080,
      "source": "pixabay"
    }
  ],
  "total": 100,
  "query": "business meeting"
}
```

## Configuration API

### Get AI Providers
```http
GET /api/config/ai-providers
Authorization: Session cookie required
```

**Response:**
```json
{
  "providers": [
    {
      "name": "openai",
      "display_name": "OpenAI",
      "available": true,
      "models": ["gpt-3.5-turbo", "gpt-4"],
      "default_model": "gpt-3.5-turbo"
    },
    {
      "name": "anthropic",
      "display_name": "Anthropic",
      "available": true,
      "models": ["claude-3-haiku-20240307", "claude-3-sonnet-20240229"],
      "default_model": "claude-3-haiku-20240307"
    }
  ],
  "default_provider": "openai"
}
```

### Update Configuration
```http
PUT /api/config/settings
Content-Type: application/json
Authorization: Session cookie required (admin only)

{
  "default_ai_provider": "anthropic",
  "max_slide_count": 50,
  "enable_image_search": true
}
```

## Error Handling

All API endpoints return consistent error responses:

```json
{
  "error": true,
  "message": "Error description",
  "code": "ERROR_CODE",
  "details": {
    "field": "Additional error details"
  }
}
```

### Common Error Codes

- `AUTHENTICATION_REQUIRED` (401): User not authenticated
- `PERMISSION_DENIED` (403): Insufficient permissions
- `NOT_FOUND` (404): Resource not found
- `VALIDATION_ERROR` (422): Invalid request data
- `RATE_LIMIT_EXCEEDED` (429): Too many requests
- `INTERNAL_ERROR` (500): Server error

## Rate Limiting

API endpoints are rate-limited to prevent abuse:

- **Authentication endpoints**: 5 requests per minute
- **Generation endpoints**: 10 requests per hour
- **File upload**: 20 requests per hour
- **Other endpoints**: 100 requests per minute

Rate limit headers are included in responses:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640995200
```

## WebSocket API (Real-time Updates)

### Connect to Generation Updates
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/generation/{project_id}');

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    console.log('Generation update:', data);
};
```

**Message Format:**
```json
{
  "type": "progress_update",
  "project_id": "proj_abc123",
  "progress": 45,
  "current_step": "Generating slide 5 of 10",
  "timestamp": "2023-12-01T10:15:00Z"
}
```

## OpenAI-Compatible API

FlowSlide provides an OpenAI-compatible API for easy integration:

### Chat Completions
```http
POST /v1/chat/completions
Content-Type: application/json
Authorization: Bearer your-api-key

{
  "model": "gpt-3.5-turbo",
  "messages": [
    {
      "role": "user",
      "content": "Generate a presentation about AI"
    }
  ]
}
```

## SDK and Examples

### Python SDK
```python
import flowslide

client = flowslide.Client(base_url="http://localhost:8000")
client.login("username", "password")

# Generate presentation
project = client.generate_presentation(
    scenario="business_report",
    topic="Q4 Sales Performance",
    slide_count=10
)

# Wait for completion
project.wait_for_completion()

# Download result
project.download("presentation.pptx")
```

### JavaScript SDK
```javascript
import FlowSlide from 'flowslide-js';

const client = new FlowSlide('http://localhost:8000');
await client.login('username', 'password');

const project = await client.generatePresentation({
  scenario: 'business_report',
  topic: 'Q4 Sales Performance',
  slideCount: 10
});

await project.waitForCompletion();
await project.download('presentation.pptx');
```

## Support

For API support and questions:
- Documentation: [https://flowslide.readthedocs.io](https://flowslide.readthedocs.io)
- Issues: [https://github.com/openai118/FlowSlide/issues](https://github.com/openai118/FlowSlide/issues)
- Email: support@flowslide.com

#!/bin/bash

# FlowSlide Docker Entrypoint Script
# This script handles initialization and startup of the FlowSlide application

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
}

info() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] INFO: $1${NC}"
}

# Banner
print_banner() {
    echo -e "${BLUE}"
    echo "╔══════════════════════════════════════════════════════════════════════════════╗"
    echo "║                                   FlowSlide                                 ║"
    echo "║                        AI-Powered PPT Generation Platform                   ║"
    echo "║                                Docker Container                             ║"
    echo "╚══════════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# Check environment variables
check_environment() {
    log "Checking environment configuration..."
    
    # Check if at least one AI provider is configured
    local ai_configured=false
    
    if [ -n "$OPENAI_API_KEY" ] && [ "$OPENAI_API_KEY" != "your_openai_api_key_here" ]; then
        info "✅ OpenAI API key configured"
        ai_configured=true
    fi
    
    if [ -n "$ANTHROPIC_API_KEY" ] && [ "$ANTHROPIC_API_KEY" != "your_anthropic_api_key_here" ]; then
        info "✅ Anthropic API key configured"
        ai_configured=true
    fi
    
    if [ -n "$GOOGLE_API_KEY" ] && [ "$GOOGLE_API_KEY" != "your_google_api_key_here" ]; then
        info "✅ Google API key configured"
        ai_configured=true
    fi
    
    if [ -n "$AZURE_OPENAI_API_KEY" ] && [ "$AZURE_OPENAI_API_KEY" != "your_azure_openai_key_here" ]; then
        info "✅ Azure OpenAI API key configured"
        ai_configured=true
    fi
    
    if [ "$ENABLE_LOCAL_MODELS" = "true" ] && [ -n "$OLLAMA_BASE_URL" ]; then
        info "✅ Ollama configuration detected"
        ai_configured=true
    fi
    
    if [ "$ai_configured" = false ]; then
        warn "⚠️ No AI provider API keys configured. Please set at least one:"
        warn "   - OPENAI_API_KEY"
        warn "   - ANTHROPIC_API_KEY"
        warn "   - GOOGLE_API_KEY"
        warn "   - AZURE_OPENAI_API_KEY"
        warn "   - Or enable ENABLE_LOCAL_MODELS=true with Ollama"
    fi
    
    # Check secret key
    if [ "$SECRET_KEY" = "your-very-secure-secret-key-change-this-in-production" ] || [ "$SECRET_KEY" = "dev-secret-key-not-for-production" ]; then
        warn "⚠️ Using default SECRET_KEY. Please change it for production!"
    fi
}

# Create necessary directories
create_directories() {
    log "Creating necessary directories..."
    
    local dirs=(
        "/app/data"
        "/app/uploads"
        "/app/temp/ai_responses_cache"
        "/app/temp/style_genes_cache"
        "/app/temp/summeryanyfile_cache"
        "/app/temp/templates_cache"
        "/app/research_reports"
        "/app/lib/Linux"
        "/app/lib/MacOS"
        "/app/lib/Windows"
    )
    
    for dir in "${dirs[@]}"; do
        if [ ! -d "$dir" ]; then
            mkdir -p "$dir"
            log "Created directory: $dir"
        fi
    done
}


# Import default templates
import_templates() {
    log "Checking template imports..."
    
    if [ -d "/app/template_examples" ] && [ "$(ls -A /app/template_examples/*.json 2>/dev/null)" ]; then
        info "Template examples found, they will be imported on first run"
    else
        warn "No template examples found in /app/template_examples"
    fi
}

# Wait for dependencies
wait_for_dependencies() {
    if [ -n "$OLLAMA_BASE_URL" ] && [ "$ENABLE_LOCAL_MODELS" = "true" ]; then
        log "Waiting for Ollama service..."
        
        local ollama_host=$(echo "$OLLAMA_BASE_URL" | sed 's|http://||' | sed 's|https://||' | cut -d':' -f1)
        local ollama_port=$(echo "$OLLAMA_BASE_URL" | sed 's|http://||' | sed 's|https://||' | cut -d':' -f2)
        
        if [ "$ollama_port" = "$ollama_host" ]; then
            ollama_port="11434"
        fi
        
        local max_attempts=30
        local attempt=1
        
        while [ $attempt -le $max_attempts ]; do
            if nc -z "$ollama_host" "$ollama_port" 2>/dev/null; then
                log "✅ Ollama service is ready"
                break
            fi
            
            if [ $attempt -eq $max_attempts ]; then
                warn "⚠️ Ollama service not available after $max_attempts attempts"
                break
            fi
            
            info "Waiting for Ollama... (attempt $attempt/$max_attempts)"
            sleep 2
            attempt=$((attempt + 1))
        done
    fi
}

# Fix .env file permissions
fix_env_permissions() {
    log "Checking .env file permissions..."

    if [ -f "/app/.env" ]; then
        # Check if we can read the .env file
        if [ ! -r "/app/.env" ]; then
            warn "⚠️ .env file is not readable by current user"
            info "Attempting to fix .env file permissions..."

            # Running as root, so we can fix permissions directly
            if chmod 644 "/app/.env" 2>/dev/null; then
                log "✅ .env file permissions fixed"
            else
                warn "⚠️ Could not fix .env file permissions"
                warn "   Creating a copy with correct permissions..."

                # Create a copy with correct permissions
                if cp "/app/.env" "/app/.env.tmp" 2>/dev/null && mv "/app/.env.tmp" "/app/.env" 2>/dev/null; then
                    chmod 644 "/app/.env" 2>/dev/null
                    log "✅ .env file copied with correct permissions"
                else
                    warn "⚠️ Could not create .env copy"
                    warn "   Please check the mounted .env file"
                fi
            fi
        else
            log "✅ .env file is readable"
        fi
    else
        warn "⚠️ .env file not found, using default configuration"
    fi
}

# Main initialization
main() {
    print_banner

    log "Starting FlowSlide initialization..."

    check_environment
    fix_env_permissions
    create_directories
    wait_for_dependencies
    import_templates

    log "🚀 Starting FlowSlide application..."
    info "📍 Server will be available at: http://0.0.0.0:${PORT:-8000}"
    info "🏠 Public Home: http://0.0.0.0:${PORT:-8000}/home"
    info "📚 API Documentation: http://0.0.0.0:${PORT:-8000}/docs"
    info "🌐 Web Interface: http://0.0.0.0:${PORT:-8000}/web"

    # Runtime interpreter and deps self-check
    info "Verifying Python runtime and dependencies..."
    echo "PATH=$PATH"
    which python || true
    python -V || true
    python -c 'import sys; print("sys.executable=", sys.executable)' || true

    if python - <<'PY'
import sys
try:
    import uvicorn, fastapi
    print('deps OK (default python)')
    sys.exit(0)
except Exception as e:
    print('default python deps check failed:', e)
    sys.exit(1)
PY
    then
        info "Dependencies available for default python"
        :
    else
        warn "Default python cannot import deps; checking PYTHONPATH..."
        # Since we install to /opt/venv but use system python, ensure PYTHONPATH is set
        export PYTHONPATH="/opt/venv:$PYTHONPATH"
        if python - <<'PY2'
import sys
sys.path.insert(0, '/opt/venv')
import uvicorn, fastapi
print('deps OK (with PYTHONPATH)')
PY2
        then
            info "Dependencies found with PYTHONPATH, using system python"
            # Keep the original command but ensure PYTHONPATH is set
        else
            error "Dependencies missing; printing installed packages and paths"
            echo "PYTHONPATH=$PYTHONPATH"
            python -c "import sys; print('Python path:', sys.path)"
            python -m pip freeze || true
            ls -la /opt/venv/ || true
            exit 1
        fi
    fi

    # Execute the main command (possibly adjusted to venv python)
    exec "$@"
}

# Run main function with all arguments
main "$@"

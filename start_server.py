import uvicorn
from flowslide.main import app
import os

# 设置Python路径
os.environ['PYTHONPATH'] = 'e:\\gitcas\\FlowSlide\\src'

print('Starting FlowSlide server...')
print('Host: 0.0.0.0')
print('Port: 8000')
print('Press Ctrl+C to stop')

uvicorn.run(app, host='0.0.0.0', port=8000, reload=True)

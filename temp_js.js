
// 受控日志：只有在 ?debug=1 或 window.__ai_debug 为 true 时输出 info/debug
window.__ai_log = (function(){
    const enabled = (new URLSearchParams(window.location.search).get('debug') === '1') || window.__ai_debug === true;
    return {
        debug: (...args) => { if(enabled) console.debug(...args); },
        info:  (...args) => { if(enabled) console.info(...args); },
        warn:  (...args) => console.warn(...args),
        error: (...args) => console.error(...args)
    };
})();
// 全局变量和常量
let currentConfig = {{ current_config | tojson }};
const AVAILABLE_PROVIDERS = ['openai', 'anthropic', 'google', 'azure_openai', 'ollama'];
const PROVIDER_DISPLAY_NAMES = {
    'openai': 'OpenAI',
    'anthropic': 'Anthropic Claude',
    'google': 'Google Gemini',
    'azure_openai': 'Azure OpenAI',
    'ollama': 'Ollama'
};
const API_ENDPOINTS = {
    config_all: '/api/config/all',
    config_ai_providers: '/api/config/ai_providers',
    current_provider: '/api/config/current-provider'
};
let providerTestCache = new Map();

// 进度条管理器
class ProgressManager {
    static show(buttonId, progressId, textId) {
        const elements = this.getElements(buttonId, progressId, textId);
        if (elements.button && elements.progress && elements.text) {
            elements.button.disabled = true;
            elements.text.style.opacity = '0.5';
            elements.progress.style.display = 'flex';
        }
    }

    static hide(buttonId, progressId, textId) {
        const elements = this.getElements(buttonId, progressId, textId);
        if (elements.button && elements.progress && elements.text) {
            elements.button.disabled = false;
            elements.text.style.opacity = '1';
            elements.progress.style.display = 'none';
        }
    }

    static getElements(buttonId, progressId, textId) {
        return {
            button: document.getElementById(buttonId),
            progress: document.getElementById(progressId),
            text: document.getElementById(textId)
        };
    }
}

// 向后兼容的函数
function showButtonProgress(buttonId, progressId, textId) {
    ProgressManager.show(buttonId, progressId, textId);
}

function hideButtonProgress(buttonId, progressId, textId) {
    ProgressManager.hide(buttonId, progressId, textId);
}

    const defaultProviderTemplate = "{{ current_config.get('default_ai_provider', 'openai') }}";

// 密文显示/隐藏
function toggleSecretVisibility(fieldName, btn){
    const input = document.querySelector(`#app-config input[name="${fieldName}"]`);
    if(!input) return;
    input.type = (input.type === 'password') ? 'text' : 'password';
    btn.textContent = (input.type === 'password') ? '👁️' : '🙈';
}

// 提供者测试状态缓存（已在上面定义）

// 初始化
document.addEventListener('DOMContentLoaded', function() {
    // 关键：尽快返回以提升页面响应性。非关键工作在空闲时运行。
    // 触发配置加载，但不要在此处 await（避免在DOMContentLoaded阶段顺序阻塞）
    loadAllConfigs().then(() => {
        // 在短延迟后初始化会话相关UI（仍较为重要）
        setTimeout(async () => {
            try {
                await initCurrentProviderSelect();
                await syncCurrentProviderStatus();
                initTopStatusDisplay();
            } catch (e) {
                window.__ai_log.warn('延迟初始化提供者时出错', e);
            }
        }, 100);
    }).catch(e => {
        window.__ai_log.warn('加载配置失败（非致命）', e);
    });

    // 将非关键的后台检查放到空闲回调中执行以避免影响首次交互
    const deferredStartup = () => {
        try {
            checkImageServiceStatus();
            loadCachedTestResults();
            resetAllProviderStatus();
        } catch (e) {
            window.__ai_log.warn('延迟启动任务出错', e);
        }
    };

    if ('requestIdleCallback' in window) {
        try { requestIdleCallback(deferredStartup, { timeout: 2000 }); } catch(e){ setTimeout(deferredStartup, 500); }
    } else {
        setTimeout(deferredStartup, 500);
    }
});

// 获取可用的提供者列表（只返回测试成功的提供者）
function getAvailableProviders() {
    const availableProviders = [];

    for (const provider of AVAILABLE_PROVIDERS) {
        try {
            // 只有缓存的测试结果显示成功的提供者才被认为是可用的
            const cachedResult = getCachedTestResult(provider);
            if (cachedResult && cachedResult.success) {
                availableProviders.push(provider);
            }
        } catch (error) {
            // 配置不完整，跳过
            window.__ai_log.info(`提供者 ${provider} 配置检查失败，跳过:`, error.message);
        }
    }

    return availableProviders;
}

// 初始化当前提供者下拉框（只显示可用的提供者）
async function initCurrentProviderSelect() {
    const selectElement = document.getElementById('current-provider-select');
    if (!selectElement) return;

    try {
        // 保存当前选择的提供者
        const currentSelection = selectElement.value;

        // 获取可用的提供者列表
        const availableProviders = getAvailableProviders();

        // 清空现有选项
        selectElement.innerHTML = '<option value="">选择提供者...</option>';

        // 添加可用的提供者
        availableProviders.forEach(provider => {
            const option = document.createElement('option');
            option.value = provider;
            option.textContent = getProviderDisplayName(provider);
            selectElement.appendChild(option);
        });

        // 恢复之前的选择（如果仍然可用）
        if (currentSelection && availableProviders.includes(currentSelection)) {
            selectElement.value = currentSelection;
            window.__ai_log.info('恢复提供者选择:', currentSelection);
        } else if (availableProviders.length > 0) {
            // 如果之前没有选择或选择的提供者不可用，尝试从API获取当前提供者
            try {
                const response = await fetch('/api/config/current-provider');
                if (response.ok) {
                    const result = await response.json();
                    if (result.success && result.current_provider && availableProviders.includes(result.current_provider)) {
                        selectElement.value = result.current_provider;
                        window.__ai_log.info('从API设置当前提供者:', result.current_provider);
                    }
                }
            } catch (error) {
                console.warn('获取当前提供者失败:', error);
            }
        }

        window.__ai_log.info('可用提供者:', availableProviders);

        // 更新页面显示的可用提供者数量
        updateAvailableProvidersCount(availableProviders.length);

        // 更新默认提供者单选按钮的可用性
        updateDefaultProviderRadios(availableProviders);
    } catch (error) {
        console.error('初始化提供者下拉框失败:', error);
    }
}

// 更新默认提供者单选按钮的可用性
function updateDefaultProviderRadios(availableProviders) {
    document.querySelectorAll('input[name="default_provider"]').forEach(radio => {
        const provider = radio.value;
        const isAvailable = availableProviders.includes(provider);

        // 禁用/启用单选按钮
        radio.disabled = !isAvailable;

        // 更新标签样式
        const label = radio.nextElementSibling;
        if (label) {
            if (isAvailable) {
                label.style.opacity = '1';
                label.style.cursor = 'pointer';
                label.title = '设为默认提供者';
            } else {
                label.style.opacity = '0.5';
                label.style.cursor = 'not-allowed';
                label.title = '提供者不可用，请先配置API Key';
            }
        }

        // 如果当前选中的提供者不可用，清除选中状态
        if (radio.checked && !isAvailable) {
            radio.checked = false;
        }
    });
}

// 工具函数类
class ProviderUtils {
    static getDisplayName(provider) {
        return PROVIDER_DISPLAY_NAMES[provider] || provider;
    }

    static isValidProvider(provider) {
        return AVAILABLE_PROVIDERS.includes(provider);
    }

    static getAllProviders() {
        return [...AVAILABLE_PROVIDERS];
    }
}

// API调用工具类
class ApiUtils {
    static async fetchConfig(endpoint) {
        try {
            const response = await fetch(endpoint);
            if (response.ok) {
                const result = await response.json();
                return result.success ? result : null;
            }
        } catch (error) {
            console.error(`API调用失败 ${endpoint}:`, error);
        }
        return null;
    }

    static async saveConfig(endpoint, config) {
        try {
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ config })
            });
            if (response.ok) {
                const result = await response.json();
                return result.success ? result : null;
            }
        } catch (error) {
            console.error(`保存配置失败 ${endpoint}:`, error);
        }
        return null;
    }
}

// HTML生成工具类
class HtmlUtils {
    static createProgressButton(id, text, className = 'btn btn-primary', onclick = '') {
        return `
            <button id="${id}-btn" onclick="${onclick}" class="${className}" style="position: relative;">
                <span id="${id}-text">${text}</span>
                <div id="${id}-progress" class="progress-overlay">
                    <div class="progress-spinner"></div>
                </div>
            </button>
        `;
    }

    static createProgressOverlay(id) {
        return `
            <div id="${id}-progress" class="progress-overlay">
                <div class="progress-spinner"></div>
            </div>
        `;
    }
}

// 错误处理工具类
class ErrorHandler {
    static async handleAsyncOperation(operation, errorMessage, progressConfig = null) {
        if (progressConfig) {
            ProgressManager.show(progressConfig.buttonId, progressConfig.progressId, progressConfig.textId);
        }

        try {
            const result = await operation();
            return { success: true, data: result };
        } catch (error) {
            console.error(errorMessage, error);
            showNotification(`${errorMessage}: ${error.message}`, 'error');
            return { success: false, error };
        } finally {
            if (progressConfig) {
                ProgressManager.hide(progressConfig.buttonId, progressConfig.progressId, progressConfig.textId);
            }
        }
    }
}

// 更新页面显示的可用提供者数量
function updateAvailableProvidersCount(count) {
    const countElement = document.getElementById('available-providers-count');
    if (countElement) {
        countElement.textContent = count;
    }
}

// 向后兼容的函数
function getProviderDisplayName(provider) {
    return ProviderUtils.getDisplayName(provider);
}

// 同步当前提供者状态
async function syncCurrentProviderStatus() {
    try {
        const response = await fetch('/api/config/current-provider');
        if (response.ok) {
            const result = await response.json();
            if (result.success && result.current_provider) {
                const currentProvider = result.current_provider;
                window.__ai_log.info('同步当前提供者状态:', currentProvider);

                // 更新页面显示的当前提供者
                updateCurrentProviderDisplay(currentProvider);

                // 更新顶部状态显示
                updateTopStatusDisplay(currentProvider);

                // 更新模型选择框
                loadCurrentProviderModels(currentProvider);
            } else {
                console.warn('API返回的提供者为空:', result);
                // 使用模板传入的默认提供者兜底（render时确定，非缓存）
                const defaultProvider = (typeof defaultProviderTemplate === 'string' && defaultProviderTemplate) ? defaultProviderTemplate : 'openai';
                updateCurrentProviderDisplay(defaultProvider);
                updateTopStatusDisplay(defaultProvider);
                loadCurrentProviderModels(defaultProvider);
            }
        } else {
            console.error('获取当前提供者失败，状态码:', response.status);
            if (response.status === 401 || response.status === 403) {
                console.warn('认证失败，可能需要登录');
                // 显示登录提示或重定向到登录页面
                const currentProviderSpan = document.getElementById('current-provider-display');
                if (currentProviderSpan) {
                    currentProviderSpan.textContent = '需要登录';
                    currentProviderSpan.style.background = '#e74c3c';
                }
            }
        }
    } catch (error) {
        console.warn('同步当前提供者状态失败:', error);
        // 使用默认提供者作为后备
        const defaultProvider = 'openai';
        updateCurrentProviderDisplay(defaultProvider);
        updateTopStatusDisplay(defaultProvider);
        loadCurrentProviderModels(defaultProvider);
    }
}

// 标签页切换功能
function switchTab(tabName) {
    // 隐藏所有标签页内容
    document.querySelectorAll('.tab-content').forEach(content => {
        content.style.display = 'none';
        content.classList.remove('active');
    });

    // 移除所有标签按钮的激活状态
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });

    // 显示选中的标签页内容
    const targetTab = document.getElementById(tabName);
    if (targetTab) {
        targetTab.style.display = 'block';
        targetTab.classList.add('active');
    }

    // 激活选中的标签按钮
    const targetBtn = document.querySelector(`[data-tab="${tabName}"]`);
    if (targetBtn) {
        targetBtn.classList.add('active');
    }

    // 加载对应的配置数据
    loadTabConfig(tabName);
}

// 加载标签页配置数据
async function loadTabConfig(tabName) {
    try {
        const categoryMap = {
            'ai-providers': 'ai_providers',
            'generation-params': 'generation_params',
            'app-config': 'app_config',
            'image-service': 'image_service'
        };

        const category = categoryMap[tabName];
        if (!category) return;

        const response = await fetch(`/api/config/${category}`);
        if (response.ok) {
            const result = await response.json();
            if (result.success) {
                populateTabForm(tabName, result.config);
            }
        }
    } catch (error) {
        console.error('加载配置失败:', error);
    }
}

// 填充表单数据
function populateTabForm(tabName, config) {
    const tabElement = document.getElementById(tabName);
    if (!tabElement) return;

    // 填充输入框
    tabElement.querySelectorAll('input, select, textarea').forEach(input => {
        const name = input.name;
        if (config[name] !== undefined) {
            if (input.type === 'checkbox') {
                input.checked = config[name];
            } else if (input.type === 'password') {
                // 对数据库URL等敏感字段，不回填真实值，只显示占位掩码
                if (name === 'database_url') {
                    input.value = '';
                    input.placeholder = '••••••••';
                } else {
                    if (!input.value && config[name]) {
                        input.value = config[name];
                    }
                    if (config[name]) {
                        input.placeholder = '••••••••';
                    }
                }
            } else {
                input.value = config[name];
            }
        }
    });

    // 如果是图片服务标签页，触发选项显示更新
    if (tabName === 'image-service') {
        setTimeout(() => {
            toggleImageServiceOptions();
        }, 100);
    }
}

// 带进度条的提供者测试功能
async function testProviderWithProgress(providerName) {
    if (!ProviderUtils.isValidProvider(providerName)) {
        showNotification(`无效的提供者: ${providerName}`, 'error');
        return;
    }

    const progressConfig = {
        buttonId: `test-${providerName}-btn`,
        progressId: `test-${providerName}-progress`,
        textId: `test-${providerName}-text`
    };

    const result = await ErrorHandler.handleAsyncOperation(
        () => testProviderSilently(providerName),
        `测试 ${ProviderUtils.getDisplayName(providerName)} 失败`,
        progressConfig
    );

    if (result.success) {
        const displayName = ProviderUtils.getDisplayName(providerName);
        showNotification(`${displayName} 测试成功！`, 'success');
    }
}

// AI提供者测试功能（保留原版本，用于兼容）
async function testProvider(providerName) {
    showLoading(`正在测试 ${providerName} 提供者...`);

    try {
        // 从前端页面获取配置信息
        const card = document.querySelector(`[data-provider="${providerName}"]`);
        if (!card) {
            throw new Error('找不到提供者配置卡片');
        }

        const config = {};
        const inputs = card.querySelectorAll('input, select');
        inputs.forEach(input => {
            if (input.name && input.name !== 'default_provider') {
                // 获取输入的值，不管是否为空
                const value = input.value.trim();
                if (value) {
                    config[input.name] = value;
                }
            }
        });

        // 根据不同的提供者进行测试
        let testResult;
        switch (providerName) {
            case 'openai':
                testResult = await testOpenAIProvider(config);
                break;
            case 'anthropic':
                testResult = await testAnthropicProvider(config);
                break;
            case 'google':
                testResult = await testGoogleProvider(config);
                break;
            case 'azure_openai':
                testResult = await testAzureOpenAIProvider(config);
                break;
            case 'ollama':
                testResult = await testOllamaProvider(config);
                break;
            default:
                throw new Error(`不支持的提供者: ${providerName}`);
        }

        showTestResult(testResult, testResult.success);
    } catch (error) {
        showTestResult({error: error.message}, false);
    }
}

// 测试 OpenAI 提供者（仅通过后端代理）
async function testOpenAIProvider(config) {
    try {
        // 获取配置 - 使用前端页面填写的信息
        let apiKey = config.openai_api_key;
        let baseUrl = config.openai_base_url;
        let model = config.openai_model;

        // 如果前端没有填写API Key，尝试从后端获取
        if (!apiKey) {
            const configResponse = await fetch('/api/config/ai_providers');
            if (configResponse.ok) {
                const configResult = await configResponse.json();
                if (configResult.success && configResult.config.openai_api_key) {
                    apiKey = configResult.config.openai_api_key;
                }
            }
        }

        // 如果仍然没有API Key，提示用户
        if (!apiKey) {
            throw new Error('请先配置 OpenAI API Key');
        }

        // 如果没有填写 Base URL，使用默认值
        if (!baseUrl) {
            baseUrl = 'https://api.openai.com/v1';
        }

        // 如果没有填写模型，使用默认值
        if (!model) {
            model = 'gpt-4o';
        }

        // 确保 Base URL 格式正确
        if (!baseUrl.endsWith('/v1')) {
            baseUrl = baseUrl.endsWith('/') ? baseUrl + 'v1' : baseUrl + '/v1';
        }

        // 只通过后端代理测试，避免CORS问题
        const proxyResponse = await fetch('/api/ai/providers/openai/test', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                base_url: baseUrl,
                api_key: apiKey,
                model: model
            })
        });

        if (!proxyResponse.ok) {
            // 尝试解析错误响应
            let errorMessage = `HTTP ${proxyResponse.status}: ${proxyResponse.statusText}`;
            try {
                const errorData = await proxyResponse.json();
                if (errorData.error) {
                    errorMessage = errorData.error;
                } else if (errorData.detail) {
                    errorMessage = errorData.detail;
                } else if (errorData.message) {
                    errorMessage = errorData.message;
                }
            } catch (parseError) {
                // 如果无法解析错误响应，使用默认错误信息
            }
            throw new Error(errorMessage);
        }

        const proxyResult = await proxyResponse.json();

        // 处理不同的响应格式
        // 后端可能返回 status: "success" 或 success: true
        if (proxyResult.status === 'success' || proxyResult.success === true) {
            // 获取模型列表
            let models = [];
            try {
                const modelsResponse = await fetch('/api/ai/providers/openai/models', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        base_url: baseUrl,
                        api_key: apiKey
                    })
                });
                if (modelsResponse.ok) {
                    const modelsResult = await modelsResponse.json();
                    if (modelsResult.success && modelsResult.models) {
                        models = modelsResult.models;
                    }
                }
            } catch (e) {
                window.__ai_log.info('获取模型列表失败，但测试仍然成功:', e);
            }

            // 标准化响应格式
            return {
                success: true,
                provider: proxyResult.provider || 'openai',
                model: proxyResult.model || model,
                models: models,
                response_preview: proxyResult.response_preview || '',
                usage: proxyResult.usage || {
                    prompt_tokens: 0,
                    completion_tokens: 0,
                    total_tokens: 0
                }
            };
        } else if (proxyResult.status === 'error' || proxyResult.success === false) {
            throw new Error(proxyResult.error || proxyResult.detail || proxyResult.message || '测试失败');
        } else {
            // 如果没有明确的状态字段，假设成功（因为HTTP状态码是200）
            return {
                success: true,
                provider: proxyResult.provider || 'openai',
                model: proxyResult.model || model,
                response_preview: proxyResult.response_preview || '',
                usage: proxyResult.usage || {
                    prompt_tokens: 0,
                    completion_tokens: 0,
                    total_tokens: 0
                }
            };
        }

    } catch (error) {
        return {
            success: false,
            error: error.message,
            detail: `OpenAI 测试失败: ${error.message}`
        };
    }
}

// 测试 Anthropic 提供者
async function testAnthropicProvider(config) {
    try {
        let apiKey = config.anthropic_api_key;
    let baseUrl = (config.anthropic_base_url || '').trim() || 'https://api.anthropic.com';
        let model = config.anthropic_model || 'claude-3-5-sonnet-20241022';

        // 如果前端没有输入API Key，尝试从后端获取
        if (!apiKey) {
            const configResponse = await fetch('/api/config/ai_providers');
            if (configResponse.ok) {
                const configResult = await configResponse.json();
                if (configResult.success && configResult.config.anthropic_api_key) {
                    apiKey = configResult.config.anthropic_api_key;
                }
            }
        }

        if (!apiKey) {
            throw new Error('请配置 Anthropic API Key');
        }

        // 调用 Anthropic API 进行测试
    // 允许自定义 Base URL（例如企业代理网关）。Anthropic 的 messages 路径位于 /v1/messages
    const endpoint = baseUrl.endsWith('/') ? baseUrl.slice(0, -1) : baseUrl;
    const response = await fetch(`${endpoint}/v1/messages`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'x-api-key': apiKey,
                'anthropic-version': '2023-06-01'
            },
            body: JSON.stringify({
                model: model,
                messages: [
                    {
                        role: 'user',
                        content: 'Say "Hello, I am working!" in exactly 5 words.'
                    }
                ],
                max_tokens: 20
            })
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error?.message || `HTTP ${response.status}`);
        }

        const data = await response.json();

        return {
            success: true,
            provider: 'anthropic',
            model: model,
            response_preview: data.content[0].text,
            usage: {
                prompt_tokens: data.usage?.input_tokens || 0,
                completion_tokens: data.usage?.output_tokens || 0,
                total_tokens: (data.usage?.input_tokens || 0) + (data.usage?.output_tokens || 0)
            }
        };
    } catch (error) {
        return {
            success: false,
            error: error.message,
            detail: `Anthropic 测试失败: ${error.message}`
        };
    }
}

// 测试 Google 提供者
async function testGoogleProvider(config) {
    try {
        let apiKey = config.google_api_key;
    let baseUrl = (config.google_base_url || '').trim() || 'https://generativelanguage.googleapis.com';
        let model = config.google_model || 'gemini-1.5-flash';

        // 如果前端没有输入API Key，尝试从后端获取
        if (!apiKey) {
            const configResponse = await fetch('/api/config/ai_providers');
            if (configResponse.ok) {
                const configResult = await configResponse.json();
                if (configResult.success && configResult.config.google_api_key) {
                    apiKey = configResult.config.google_api_key;
                }
            }
        }

        if (!apiKey) {
            throw new Error('请配置 Google API Key');
        }

        // 调用 Google Gemini API 进行测试
    // 允许自定义 Base URL（例如代理服务）。Google Gemini REST 路径通常为 /v1beta/models/...:generateContent
    const gbase = baseUrl.endsWith('/') ? baseUrl.slice(0, -1) : baseUrl;
    const response = await fetch(`${gbase}/v1beta/models/${model}:generateContent?key=${apiKey}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                contents: [
                    {
                        parts: [
                            {
                                text: 'Say "Hello, I am working!" in exactly 5 words.'
                            }
                        ]
                    }
                ],
                generationConfig: {
                    maxOutputTokens: 20,
                    temperature: 0
                }
            })
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error?.message || `HTTP ${response.status}`);
        }

        const data = await response.json();

        return {
            success: true,
            provider: 'google',
            model: model,
            response_preview: data.candidates[0].content.parts[0].text,
            usage: {
                prompt_tokens: data.usageMetadata?.promptTokenCount || 0,
                completion_tokens: data.usageMetadata?.candidatesTokenCount || 0,
                total_tokens: data.usageMetadata?.totalTokenCount || 0
            }
        };
    } catch (error) {
        return {
            success: false,
            error: error.message,
            detail: `Google Gemini 测试失败: ${error.message}`
        };
    }
}

// 测试 Azure OpenAI 提供者
async function testAzureOpenAIProvider(config) {
    try {
        let apiKey = config.azure_openai_api_key;
        let endpoint = config.azure_openai_endpoint;
        let deploymentName = config.azure_openai_deployment_name;
        let apiVersion = config.azure_openai_api_version || '2024-02-15-preview';

        // 如果前端没有输入，尝试从后端获取
        if (!apiKey || !endpoint || !deploymentName) {
            const configResponse = await fetch('/api/config/ai_providers');
            if (configResponse.ok) {
                const configResult = await configResponse.json();
                if (configResult.success) {
                    apiKey = apiKey || configResult.config.azure_openai_api_key;
                    endpoint = endpoint || configResult.config.azure_openai_endpoint;
                    deploymentName = deploymentName || configResult.config.azure_openai_deployment_name;
                }
            }
        }

        if (!apiKey || !endpoint || !deploymentName) {
            throw new Error('请配置 Azure OpenAI 的所有必需参数');
        }

        // 确保 endpoint 格式正确
        if (!endpoint.endsWith('/')) {
            endpoint += '/';
        }

        // 调用 Azure OpenAI API 进行测试
        const url = `${endpoint}openai/deployments/${deploymentName}/chat/completions?api-version=${apiVersion}`;
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'api-key': apiKey
            },
            body: JSON.stringify({
                messages: [
                    {
                        role: 'user',
                        content: 'Say "Hello, I am working!" in exactly 5 words.'
                    }
                ],
                max_tokens: 20,
                temperature: 0
            })
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error?.message || `HTTP ${response.status}`);
        }

        const data = await response.json();

        return {
            success: true,
            provider: 'azure_openai',
            model: deploymentName,
            response_preview: data.choices[0].message.content,
            usage: data.usage || {
                prompt_tokens: 0,
                completion_tokens: 0,
                total_tokens: 0
            }
        };
    } catch (error) {
        return {
            success: false,
            error: error.message,
            detail: `Azure OpenAI 测试失败: ${error.message}`
        };
    }
}

// 测试 Ollama 提供者
async function testOllamaProvider(config) {
    try {
        let baseUrl = (config.ollama_base_url || 'http://localhost:11434').trim();
        let model = config.ollama_model || 'llama2';

        // Basic validation: only allow http/https schemes
        try {
            const u = new URL(baseUrl);
            if (u.protocol !== 'http:' && u.protocol !== 'https:') {
                throw new Error('Invalid URL scheme');
            }
        } catch (e) {
            return { success: false, provider: 'ollama', error: '无效的 base URL' };
        }

        // Call backend proxy which validates and performs the request server-side
        const proxyResp = await fetch('/api/ai/providers/ollama/test', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ base_url: baseUrl, model: model })
        });

        if (!proxyResp.ok) {
            let errMsg = `HTTP ${proxyResp.status}`;
            try {
                const errJson = await proxyResp.json();
                errMsg = errJson.error || errJson.detail || errMsg;
            } catch (e) {}
            throw new Error(errMsg);
        }

        const proxyResult = await proxyResp.json();
        if (!proxyResult.success) {
            throw new Error(proxyResult.error || proxyResult.detail || '测试失败');
        }

        return {
            success: true,
            provider: 'ollama',
            model: model,
            response_preview: proxyResult.response_preview || '',
        };
    } catch (error) {
        // Ollama 可能未运行或无法连接
        if (error.message.includes('Failed to fetch') || error.message.includes('NetworkError')) {
            return {
                success: false,
                provider: 'ollama',
                error: 'Ollama 服务未运行或无法连接',
                detail: `请确保 Ollama 正在运行并可以通过 ${config.ollama_base_url || 'http://localhost:11434'} 访问`
            };
        }
        return {
            success: false,
            provider: 'ollama',
            error: error.message,
            detail: `Ollama 测试失败: ${error.message}`
        };
    }
}

async function testCurrentProvider() {
    // 显示进度条
    showButtonProgress('test-current-btn', 'test-current-progress', 'test-current-text');

    try {
        // 1) 优先从顶部下拉读取
        const selectEl = document.getElementById('current-provider-select');
        let currentProvider = (selectEl && selectEl.value) ? selectEl.value.trim() : '';

    // 2) 再尝试调用API（若已登录）
    if (!currentProvider) {
        try {
            const response = await fetch('/api/config/current-provider');
            if (response.ok) {
                const result = await response.json();
                if (result.success && result.current_provider) {
                    currentProvider = result.current_provider;
                }
            }
        } catch (error) {
            console.warn('获取当前提供者失败:', error);
        }
    }

    // 3) 最后回退到模板默认
    if (!currentProvider) {
        const fallback = (typeof defaultProviderTemplate === 'string' && defaultProviderTemplate) ? defaultProviderTemplate : '';
        if (fallback) currentProvider = fallback;
    }

    if (!currentProvider) {
        showNotification('请先在上方下拉框选择一个“当前提供者”', 'error');
        return;
    }

    // 获取当前选择的模型
    const modelSelect = document.getElementById('current_model_select');
    const selectedModel = modelSelect && modelSelect.value ? modelSelect.value : null;

    // 如果选择了模型，先保存配置再测试
    if (selectedModel) {
    window.__ai_log.info(`使用提供者 ${currentProvider} 和模型 ${selectedModel} 进行测试`);

        // 构建配置对象
        const config = {};
        if (currentProvider === 'azure_openai') {
            config['azure_openai_deployment_name'] = selectedModel;
        } else {
            config[currentProvider + '_model'] = selectedModel;
        }

        // 保存模型配置
        try {
            const saveResponse = await fetch('/api/config/all', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    config: config
                })
            });

            if (!saveResponse.ok) {
                throw new Error(`保存配置失败: HTTP ${saveResponse.status}`);
            }

            const saveResult = await saveResponse.json();
            if (!saveResult.success) {
                throw new Error(saveResult.message || '保存配置失败');
            }

            window.__ai_log.info('模型配置已保存');
        } catch (error) {
            console.warn('保存模型配置失败:', error);
            // 继续测试，即使保存失败
        }
    }

    // 测试提供者
    const testSuccess = await testProviderSilently(currentProvider);

    if (testSuccess) {
        const modelInfo = selectedModel ? ` (模型: ${selectedModel})` : '';
        showNotification(`${currentProvider} 测试成功！${modelInfo}`, 'success');

        // 更新状态显示
        updateProviderStatusDisplay(currentProvider, true);
    } else {
        const modelInfo = selectedModel ? ` (模型: ${selectedModel})` : '';
        showNotification(`${currentProvider} 测试失败${modelInfo}`, 'error');
    }

    } catch (error) {
        console.error('测试当前提供者失败:', error);
        showNotification('测试失败: ' + error.message, 'error');
    } finally {
        // 隐藏进度条
        hideButtonProgress('test-current-btn', 'test-current-progress', 'test-current-text');
    }
}

async function refreshProviders() {
    const progressConfig = {
        buttonId: 'refresh-providers-btn',
        progressId: 'refresh-providers-progress',
        textId: 'refresh-providers-text'
    };

    const result = await ErrorHandler.handleAsyncOperation(
        async () => {
            // 首先清除所有测试缓存
            clearTestCache();
            window.__ai_log.info('已清除所有测试缓存');

            // 测试所有已配置的提供者
            await testAllConfiguredProviders();

            // 重新初始化当前提供者下拉框
            await initCurrentProviderSelect();

            // 返回可用提供者数量
            return getAvailableProviders().length;
        },
        '重新测试提供者失败',
        progressConfig
    );

    if (result.success) {
        showNotification(`测试完成！可用提供者: ${result.data} 个`, 'success');
    }
}

// 测试所有已配置的提供者
async function testAllConfiguredProviders() {
    const configuredProviders = [];

    window.__ai_log.info('开始测试所有已配置的提供者...');

    // 首先检查哪些提供者已配置
    for (const provider of AVAILABLE_PROVIDERS) {
        const isConfigured = isProviderConfigured(provider);
    window.__ai_log.info(`检查提供者 ${provider}: ${isConfigured ? '已配置' : '未配置'}`);

        if (isConfigured) {
            configuredProviders.push(provider);
            window.__ai_log.info(`发现已配置的提供者: ${provider}`);
        } else {
            window.__ai_log.info(`跳过未配置的提供者: ${provider}`);
            // 未配置的提供者设置为不可用
            updateProviderStatusDisplay(provider, false);
            cacheTestResult(provider, false);
        }
    }

    if (configuredProviders.length === 0) {
    window.__ai_log.info('没有找到已配置的提供者');
        return;
    }

    // 并行化测试（有限并发），避免顺序阻塞页面交互
    const maxConcurrent = 3;
    let running = 0;
    let index = 0;

    const runNext = async () => {
        if (index >= configuredProviders.length) return;
        const provider = configuredProviders[index++];
        running++;
        try {
            await testProviderSilently(provider);
        } catch (error) {
            console.error(`测试 ${provider} 时出错:`, error);
        } finally {
            running--;
            // schedule next in next tick to yield to UI
            setTimeout(runNext, 0);
        }
    };

    // 启动初始并发任务
    for (let k = 0; k < Math.min(maxConcurrent, configuredProviders.length); k++) {
        runNext();
    }

    // 等待所有完成（轮询式）
    const waitForAll = () => new Promise(resolve => {
        const check = () => {
            if (running === 0 && index >= configuredProviders.length) return resolve();
            setTimeout(check, 150);
        };
        check();
    });

    await waitForAll();
    window.__ai_log.info('所有提供者测试完成');
}

// 检查提供者是否已配置（直接从页面表单读取）
function isProviderConfigured(providerName) {
    const card = document.querySelector(`[data-provider="${providerName}"]`);
    if (!card) {
    window.__ai_log.info(`${providerName}: 找不到配置卡片`);
        return false;
    }

    // 从表单获取配置
    const config = {};
    const inputs = card.querySelectorAll('input, select');
    inputs.forEach(input => {
        if (input.name && input.name !== 'default_provider') {
            const value = input.value.trim();
            if (value) {
                config[input.name] = value;
            }
        }
    });

    window.__ai_log.info(`${providerName} 配置:`, config);

    // 检查必要的配置字段
    let result = false;
    switch (providerName) {
        case 'openai':
            // OpenAI只需要API Key，Base URL有默认值
            result = !!config.openai_api_key;
            window.__ai_log.info(`${providerName}: API Key=${!!config.openai_api_key}, Base URL=${!!config.openai_base_url || '有默认值'}`);
            break;
        case 'anthropic':
            // Anthropic只需要API Key，Base URL有默认值
            result = !!config.anthropic_api_key;
            window.__ai_log.info(`${providerName}: API Key=${!!config.anthropic_api_key}`);
            break;
        case 'google':
            // Google只需要API Key，Base URL有默认值
            result = !!config.google_api_key;
            window.__ai_log.info(`${providerName}: API Key=${!!config.google_api_key}, Base URL=${!!config.google_base_url || '有默认值'}`);
            break;
        case 'azure_openai':
            result = !!(config.azure_openai_api_key && config.azure_openai_endpoint);
            window.__ai_log.info(`${providerName}: API Key=${!!config.azure_openai_api_key}, Endpoint=${!!config.azure_openai_endpoint}`);
            break;
        case 'ollama':
            // Ollama只需要Base URL，有默认值
            result = true; // Ollama总是可用，因为有默认的localhost地址
            window.__ai_log.info(`${providerName}: Base URL=${!!config.ollama_base_url || '有默认值'}`);
            break;
        default:
            window.__ai_log.info(`${providerName}: 不支持的提供者`);
            return false;
    }

    window.__ai_log.info(`${providerName} 配置检查结果: ${result}`);
    return result;
}

// 静默测试提供者（不显示弹窗）
async function testProviderSilently(providerName) {
    try {
        // 从配置获取提供者信息
        const card = document.querySelector(`[data-provider="${providerName}"]`);
        if (!card) {
            throw new Error('找不到提供者配置卡片');
        }

        const config = {};
        const inputs = card.querySelectorAll('input, select');
        inputs.forEach(input => {
            if (input.name && input.name !== 'default_provider') {
                const value = input.value.trim();
                if (value) {
                    config[input.name] = value;
                }
            }
        });

        // 根据不同的提供者进行测试
        let testResult;
        switch (providerName) {
            case 'openai':
                testResult = await testOpenAIProvider(config);
                break;
            case 'anthropic':
                testResult = await testAnthropicProvider(config);
                break;
            case 'google':
                testResult = await testGoogleProvider(config);
                break;
            case 'azure_openai':
                testResult = await testAzureOpenAIProvider(config);
                break;
            case 'ollama':
                testResult = await testOllamaProvider(config);
                break;
            default:
                throw new Error(`不支持的提供者: ${providerName}`);
        }

        // 更新状态显示和缓存
        if (testResult.success) {
            updateProviderStatusDisplay(providerName, true);
            cacheTestResult(providerName, true);
            window.__ai_log.info(`${providerName} 测试成功`);
        } else {
            updateProviderStatusDisplay(providerName, false);
            cacheTestResult(providerName, false);
            window.__ai_log.info(`${providerName} 测试失败:`, testResult.error || testResult.detail);
        }

        return testResult;
    } catch (error) {
        console.error(`${providerName} 测试出错:`, error);
        updateProviderStatusDisplay(providerName, false);
        cacheTestResult(providerName, false);
        return { success: false, error: error.message };
    }
}

// 配置管理功能
async function loadAllConfigs() {
    const result = await ApiUtils.fetchConfig(API_ENDPOINTS.config_all);
    if (result) {
        currentConfig = result.config;
        populateAllForms();
    } else {
        console.error('加载配置失败');
    }
}

function populateAllForms() {
    // 填充AI提供者配置
    populateProviderForms();

    // 填充生成参数
    populateGenerationParams();

    // 填充应用配置
    populateAppConfig();

    // 填充图片服务配置
    populateImageServiceConfig();
}

function populateProviderForms() {
    document.querySelectorAll('.provider-config-card').forEach(card => {
        const provider = card.dataset.provider;
        const inputs = card.querySelectorAll('input, select');

        inputs.forEach(input => {
            const configKey = input.name;
            if (currentConfig[configKey]) {
                if (input.type === 'checkbox') {
                    input.checked = currentConfig[configKey] === 'true';
                } else if (input.type === 'password') {
                    // 对于密码字段，如果有配置值且输入框为空，则显示配置值
                    if (!input.value && currentConfig[configKey]) {
                        input.value = currentConfig[configKey];
                    }
                    // 如果有配置值，更新placeholder为掩码显示
                    if (currentConfig[configKey]) {
                        input.placeholder = '••••••••';
                    }
                } else {
                    // 只有当输入框为空时才设置值，避免覆盖模板中已设置的值
                    if (!input.value && currentConfig[configKey]) {
                        input.value = currentConfig[configKey];
                    }
                }
            }
        });
    });
}

function populateGenerationParams() {
    const tab = document.getElementById('generation-params');
    if (!tab) return;

    const inputs = tab.querySelectorAll('input, select');
    inputs.forEach(input => {
        const configKey = input.name;
        if (currentConfig[configKey]) {
            if (input.type === 'checkbox') {
                input.checked = currentConfig[configKey] === 'true';
            } else if (input.type === 'password') {
                // 对于密码字段，如果有配置值且输入框为空，则显示配置值
                if (!input.value && currentConfig[configKey]) {
                    input.value = currentConfig[configKey];
                }
                // 如果有配置值，更新placeholder为掩码显示
                if (currentConfig[configKey]) {
                    input.placeholder = '••••••••';
                }
            } else {
                // 只有当输入框为空时才设置值，避免覆盖模板中已设置的值
                if (!input.value && currentConfig[configKey]) {
                    input.value = currentConfig[configKey];
                }
            }
        }
    });
}



function populateAppConfig() {
    const tab = document.getElementById('app-config');
    if (!tab) return;

    const inputs = tab.querySelectorAll('input, select');
    inputs.forEach(input => {
        const configKey = input.name;
        if (currentConfig[configKey]) {
            if (input.type === 'checkbox') {
                input.checked = currentConfig[configKey] === 'true';
            } else if (input.type === 'password') {
                // 对于密码字段，如果有配置值且输入框为空，则显示配置值
                if (!input.value && currentConfig[configKey]) {
                    input.value = currentConfig[configKey];
                }
                // 如果有配置值，更新placeholder为掩码显示
                if (currentConfig[configKey]) {
                    input.placeholder = '••••••••';
                }
            } else {
                // 只有当输入框为空时才设置值，避免覆盖模板中已设置的值
                if (!input.value && currentConfig[configKey]) {
                    input.value = currentConfig[configKey];
                }
            }
        }
    });
}

function populateImageServiceConfig() {
    const tab = document.getElementById('image-service');
    if (!tab) return;

    const inputs = tab.querySelectorAll('input, select');
    inputs.forEach(input => {
        const configKey = input.name;
        if (currentConfig[configKey] !== undefined) {
            if (input.type === 'checkbox') {
                input.checked = currentConfig[configKey] === 'true' || currentConfig[configKey] === true;
            } else if (input.type === 'password') {
                // 对于密码字段，如果有配置值且输入框为空，则显示配置值
                if (!input.value && currentConfig[configKey]) {
                    input.value = currentConfig[configKey];
                }
                // 如果有配置值，更新placeholder为掩码显示
                if (currentConfig[configKey]) {
                    input.placeholder = '••••••••';
                }
            } else {
                // 只有当输入框为空时才设置值，避免覆盖模板中已设置的值
                if (!input.value && currentConfig[configKey]) {
                    input.value = currentConfig[configKey];
                }
            }
        }
    });

    // 触发图片服务选项显示更新
    setTimeout(() => {
        toggleImageServiceOptions();
    }, 100);
}

// 设置默认提供者
async function setDefaultProvider(provider) {
    try {
        // 不显示loading，因为这是一个快速操作
        const response = await fetch('/api/config/default-provider', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ provider: provider })
        });

        if (response.ok) {
            const result = await response.json();
            if (result.success) {
                showNotification(`默认提供者已设置为 ${provider}`, 'success');

                // 更新页面显示的当前提供者
                updateCurrentProviderDisplay(provider);

                // 更新顶部状态显示
                updateTopStatusDisplay(provider);

                // 更新模型选择框
                loadCurrentProviderModels(provider);

                // 不需要刷新整个页面，只更新显示即可
            } else {
                showNotification('设置默认提供者失败: ' + (result.message || '未知错误'), 'error');
            }
// 应用顶部“当前提供者”下拉到系统默认提供者
async function applyCurrentProviderSelect() {
    const selectEl = document.getElementById('current-provider-select');
    if (!selectEl || !selectEl.value) {
        showNotification('请先在下拉框选择一个提供者', 'error');
        return;
    }
    await setDefaultProvider(selectEl.value);
}

        } else {
            showNotification('设置默认提供者失败', 'error');
        }
    } catch (error) {
        showNotification('设置默认提供者失败: ' + error.message, 'error');
    }
}

// 应用顶部“当前提供者”下拉到系统默认提供者
async function applyCurrentProviderSelect() {
    const selectEl = document.getElementById('current-provider-select');
    if (!selectEl || !selectEl.value) {
        showNotification('请先在下拉框选择一个提供者', 'error');
        return;
    }
    await setDefaultProvider(selectEl.value);
}

// 更新当前提供者显示
function updateCurrentProviderDisplay(provider) {
    // 更新当前提供者下拉框
    const currentProviderSelect = document.getElementById('current-provider-select');
    if (currentProviderSelect) {
        currentProviderSelect.value = provider;
    }

    // 同时更新所有单选框的选中状态
    document.querySelectorAll('input[name="default_provider"]').forEach(radio => {
        radio.checked = (radio.value === provider);
    });
}

// 更新顶部状态显示
function updateTopStatusDisplay(provider) {
    // 检查提供者是否有缓存的测试结果
    const cachedResult = getCachedTestResult(provider);

    let isAvailable = false;
    if (cachedResult) {
        // 如果有缓存结果，使用缓存结果
        isAvailable = cachedResult.success;
    } else {
        // 如果没有缓存结果，检查提供者卡片的当前状态
        const providerCard = document.querySelector(`[data-provider="${provider}"]`);
        if (providerCard) {
            const statusSpan = providerCard.querySelector('span[style*="background: var(--success-gradient)"]');
            isAvailable = statusSpan && statusSpan.innerHTML.includes('✅');
        }
    }

    // 更新状态文本
    const statusElement = document.getElementById('current-provider-status');
    if (statusElement) {
        if (isAvailable) {
            statusElement.innerHTML = '<span style="color: #27ae60;">✅ 正常运行</span>';
        } else {
            statusElement.innerHTML = '<span style="color: #f39c12;">⏳ 待测试</span>';
        }
    }
}

// 初始化顶部状态显示
async function initTopStatusDisplay() {
    // 从API获取当前默认提供者
    let currentProvider = null;

    try {
        const response = await fetch('/api/config/current-provider');
        if (response.ok) {
            const result = await response.json();
            if (result.success) {
                currentProvider = result.current_provider;
            }
        }
    } catch (error) {
        console.warn('获取当前提供者失败:', error);
        return;
    }

    if (!currentProvider) {
        return;
    }

    // 检查是否有缓存的测试结果
    const cachedResult = getCachedTestResult(currentProvider);
    if (cachedResult) {
        // 如果有缓存结果，使用缓存结果更新状态
        updateTopStatusDisplay(currentProvider);
    } else {
        // 如果没有缓存结果，显示待测试状态
        const statusElement = document.querySelector('#current-provider-status');
        if (statusElement) {
            statusElement.innerHTML = '<span style="color: #f39c12;">⏳ 待测试</span>';
        }
    }
}

// 带进度条的保存提供者配置
async function saveProviderConfigWithProgress(provider) {
    if (!ProviderUtils.isValidProvider(provider)) {
        showNotification(`无效的提供者: ${provider}`, 'error');
        return;
    }

    const progressConfig = {
        buttonId: `save-${provider}-btn`,
        progressId: `save-${provider}-progress`,
        textId: `save-${provider}-text`
    };

    const result = await ErrorHandler.handleAsyncOperation(
        () => saveProviderConfigSilently(provider),
        `保存 ${ProviderUtils.getDisplayName(provider)} 配置失败`,
        progressConfig
    );

    if (result.success) {
        const displayName = ProviderUtils.getDisplayName(provider);
        showNotification(`${displayName} 配置保存成功，已实时生效`, 'success');

        // 重新加载配置
        await loadAllConfigs();
        // 重新初始化提供者下拉框以更新可用性
        setTimeout(async () => {
            await initCurrentProviderSelect();
        }, 100);
    }
}

// 保存提供者配置（原函数，保持向后兼容）
async function saveProviderConfig(provider) {
    const card = document.querySelector(`[data-provider="${provider}"]`);
    if (!card) return;

    const config = {};
    const inputs = card.querySelectorAll('input, select');

    inputs.forEach(input => {
        if (input.name && input.value) {
            // 跳过 default_provider radio 按钮，因为它通过专门的 API 处理
            if (input.name === 'default_provider') {
                return;
            }
            config[input.name] = input.value;
        }
    });

    try {
        showLoading(`正在保存 ${provider} 配置...`);

        const response = await fetch('/api/config/ai_providers', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ config: config })
        });

        if (response.ok) {
            const result = await response.json();
            if (result.success) {
                showNotification(`${provider} 配置保存成功，已实时生效`, 'success');
                // 重新加载配置
                await loadAllConfigs();
                // 重新初始化提供者下拉框以更新可用性
                setTimeout(async () => {
                    await initCurrentProviderSelect();
                }, 100);
            } else {
                showNotification(`${provider} 配置保存失败: ${result.errors || '未知错误'}`, 'error');
            }
        } else {
            showNotification(`${provider} 配置保存失败`, 'error');
        }

        closeTestModal();
    } catch (error) {
        showNotification('保存配置失败: ' + error.message, 'error');
        closeTestModal();
    }
}

// 保存生成参数
async function saveGenerationParams() {
    const tab = document.getElementById('generation-params');
    if (!tab) return;

    const config = {};
    const inputs = tab.querySelectorAll('input, select');

    inputs.forEach(input => {
        if (input.name) {
            if (input.type === 'checkbox') {
                config[input.name] = input.checked;
            } else if (input.value) {
                config[input.name] = input.value;
            }
        }
    });

    try {
        const response = await fetch('/api/config/generation_params', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ config: config })
        });

        if (response.ok) {
            const result = await response.json();
            if (result.success) {
                showNotification('生成参数保存成功，已实时生效', 'success');
                // 重新加载配置
                loadAllConfigs();
            } else {
                showNotification('生成参数保存失败: ' + (result.errors || '未知错误'), 'error');
            }
        } else {
            showNotification('生成参数保存失败', 'error');
        }
    } catch (error) {
        showNotification('保存失败: ' + error.message, 'error');
    }
}



// 保存应用配置
async function saveAppConfig() {
    const tab = document.getElementById('app-config');
    if (!tab) return;

    const config = {};
    const inputs = tab.querySelectorAll('input, select');

    inputs.forEach(input => {
        if (input.name) {
            if (input.type === 'checkbox') {
                config[input.name] = input.checked;
            } else if (input.value) {
                config[input.name] = input.value;
            }
        }
    });

    try {
        const response = await fetch('/api/config/app_config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ config: config })
        });

        if (response.ok) {
            const result = await response.json();
            if (result.success) {
                showNotification('应用配置保存成功，已实时生效', 'success');
                // 重新加载配置
                loadAllConfigs();
            } else {
                showNotification('应用配置保存失败: ' + (result.errors || '未知错误'), 'error');
            }
        } else {
            showNotification('应用配置保存失败', 'error');
        }
    } catch (error) {
        showNotification('保存失败: ' + error.message, 'error');
    }
}

// 保存所有配置
async function saveAllConfigs() {
    showLoading('正在保存所有配置...');

    try {
        // 收集所有配置
        const allConfig = {};

        // 收集AI提供者配置
        document.querySelectorAll('.provider-config-card').forEach(card => {
            const inputs = card.querySelectorAll('input, select');
            inputs.forEach(input => {
                if (input.name && input.value) {
                    // 跳过 default_provider radio 按钮，因为它通过专门的 API 处理
                    if (input.name === 'default_provider') {
                        return;
                    }
                    allConfig[input.name] = input.value;
                }
            });
        });

        // 收集其他配置
        ['generation-params', 'app-config'].forEach(tabId => {
            const tab = document.getElementById(tabId);
            if (tab) {
                const inputs = tab.querySelectorAll('input, select');
                inputs.forEach(input => {
                    if (input.name) {
                        if (input.type === 'checkbox') {
                            allConfig[input.name] = input.checked;
                        } else if (input.value) {
                            allConfig[input.name] = input.value;
                        }
                    }
                });
            }
        });

        const response = await fetch('/api/config/all', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ config: allConfig })
        });

        if (response.ok) {
            const result = await response.json();
            if (result.success) {
                showNotification('所有配置保存成功', 'success');
            } else {
                showNotification('配置保存失败: ' + (result.errors || '未知错误'), 'error');
            }
            closeTestModal();
        } else {
            showNotification('配置保存失败', 'error');
            closeTestModal();
        }
    } catch (error) {
        showNotification('保存失败: ' + error.message, 'error');
        closeTestModal();
    }
}











// 通知功能
function showNotification(message, type = 'info') {
    // 创建通知元素
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 15px 20px;
        border-radius: 8px;
        color: white;
        font-weight: 600;
        z-index: 10000;
        max-width: 400px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        transform: translateX(100%);
        transition: transform 0.3s ease;
    `;

    // 设置背景颜色
    switch (type) {
        case 'success':
            notification.style.background = 'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)';
            break;
        case 'error':
            notification.style.background = 'linear-gradient(135deg, #fa709a 0%, #fee140 100%)';
            break;
        case 'warning':
            notification.style.background = 'linear-gradient(135deg, #fa709a 0%, #fee140 100%)';
            break;
        default:
            notification.style.background = 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)';
    }

    notification.textContent = message;
    document.body.appendChild(notification);

    // 显示动画
    setTimeout(() => {
        notification.style.transform = 'translateX(0)';
    }, 100);

    // 自动隐藏
    setTimeout(() => {
        notification.style.transform = 'translateX(100%)';
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 300);
    }, 3000);
}

function showLoading(message) {
    document.getElementById('testResults').innerHTML = `
        <div style="text-align: center; padding: 20px;">
            <div style="font-size: 2em; margin-bottom: 10px;">⏳</div>
            <p>${message}</p>
        </div>
    `;
    document.getElementById('testModal').style.display = 'block';
}

function hideLoading() {
    const testResults = document.getElementById('testResults');
    if (testResults) {
        testResults.innerHTML = '';
    }
}

function showTestResult(result, success) {
    const statusIcon = success ? '✅' : '❌';
    const statusColor = success ? '#27ae60' : '#e74c3c';

    let content = `
        <div style="text-align: center; margin-bottom: 20px;">
            <div style="font-size: 3em; margin-bottom: 10px;">${statusIcon}</div>
            <h4 style="color: ${statusColor};">${success ? '测试成功' : '测试失败'}</h4>
        </div>
    `;

    if (success) {
        content += `
            <div style="background: var(--glass-bg); border: 1px solid var(--glass-border); padding: 20px; border-radius: 8px;">
                <p style="color: var(--text-primary);"><strong>提供者:</strong> ${result.provider}</p>
                <p style="color: var(--text-primary);"><strong>模型:</strong> ${result.model}</p>
                <p style="color: var(--text-primary);"><strong>响应预览:</strong></p>
                <div style="background: var(--bg-secondary); border: 1px solid var(--glass-border); padding: 15px; border-radius: 5px; margin-top: 10px; font-family: monospace; font-size: 0.9em; color: var(--text-primary);">
                    ${result.response_preview}
                </div>
                <p style="margin-top: 15px; color: var(--text-primary);"><strong>使用统计:</strong></p>
                <ul style="margin-left: 20px; color: var(--text-primary);">
                    <li>提示词令牌: ${result.usage.prompt_tokens}</li>
                    <li>完成令牌: ${result.usage.completion_tokens}</li>
                    <li>总令牌: ${result.usage.total_tokens}</li>
                </ul>
            </div>
        `;
    } else {
        content += `
            <div style="background: rgba(231, 76, 60, 0.1); border: 1px solid rgba(231, 76, 60, 0.3); padding: 20px; border-radius: 8px; border-left: 4px solid #e74c3c;">
                <p style="color: var(--text-primary);"><strong>错误信息:</strong></p>
                <div style="background: var(--bg-secondary); border: 1px solid var(--glass-border); padding: 10px; border-radius: 5px; font-family: monospace; font-size: 0.9em; color: var(--text-primary);">
                    ${result.detail || result.error || '未知错误'}
                </div>
            </div>
        `;
    }

    document.getElementById('testResults').innerHTML = content;
    document.getElementById('testModal').style.display = 'block';

    // 如果测试成功，更新提供者状态显示并保存配置
    if (success && result.provider) {
        updateProviderStatusDisplay(result.provider, true);

        // 缓存测试结果
        cacheTestResult(result.provider, true);

        // 自动获取模型列表（如果支持）
        if (result.provider === 'openai' && result.models) {
            updateModelDropdown(result.provider, result.models);
        }

        // 自动保存配置以持久化状态
        setTimeout(() => {
            saveProviderConfigSilently(result.provider);
        }, 500);
    } else if (result.provider) {
        // 测试失败时更新状态显示
        updateProviderStatusDisplay(result.provider, false);

        // 测试失败也要缓存结果
        cacheTestResult(result.provider, false);
    }
}

function showAllTestResults(results) {
    let content = '<div style="margin-bottom: 20px;">';

    results.forEach(({provider, result, success}) => {
        const statusIcon = success ? '✅' : '❌';
        const statusColor = success ? '#27ae60' : '#e74c3c';

        content += `
            <div style="border: 1px solid var(--glass-border); background: var(--glass-bg); border-radius: 8px; padding: 15px; margin-bottom: 15px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                    <strong style="color: var(--text-primary);">${provider}</strong>
                    <span style="color: ${statusColor};">${statusIcon} ${success ? '成功' : '失败'}</span>
                </div>
                ${success ?
                    `<p style="color: var(--text-secondary); font-size: 0.9em;">模型: ${result.model} | 响应: ${result.response_preview.substring(0, 50)}...</p>` :
                    `<p style="color: #e74c3c; font-size: 0.9em;">错误: ${result.detail || result.error}</p>`
                }
            </div>
        `;

        // 更新提供者状态显示并保存配置
        if (success) {
            updateProviderStatusDisplay(provider, true);

            // 缓存测试结果
            cacheTestResult(provider, true);

            // 自动保存配置以持久化状态
            setTimeout(() => {
                saveProviderConfigSilently(provider);
            }, 500);
        } else {
            // 测试失败时更新状态显示
            updateProviderStatusDisplay(provider, false);

            // 测试失败也要缓存结果
            cacheTestResult(provider, false);
        }
    });

    content += '</div>';

    document.getElementById('testResults').innerHTML = content;
    document.getElementById('testModal').style.display = 'block';
}

function closeTestModal() {
    document.getElementById('testModal').style.display = 'none';
}

// 更新提供者状态显示
function updateProviderStatusDisplay(provider, isAvailable) {
    const providerCard = document.querySelector(`[data-provider="${provider}"]`);
    if (!providerCard) return;

    const statusSpan = providerCard.querySelector('span[style*="background: var(--success-gradient)"], span[style*="background: var(--secondary-gradient)"]');
    if (statusSpan) {
        if (isAvailable) {
            statusSpan.style.background = 'var(--success-gradient)';
            statusSpan.innerHTML = '✅ 可用';
        } else {
            statusSpan.style.background = 'var(--secondary-gradient)';
            statusSpan.innerHTML = '❌ 不可用';
        }
    }
}

// 静默保存提供者配置（不显示通知）
async function saveProviderConfigSilently(provider) {
    const card = document.querySelector(`[data-provider="${provider}"]`);
    if (!card) {
        throw new Error('找不到提供者配置卡片');
    }

    const config = {};
    const inputs = card.querySelectorAll('input, select');
    inputs.forEach(input => {
        if (input.name && input.name !== 'default_provider') {
            config[input.name] = input.value;
        }
    });

    const result = await ApiUtils.saveConfig(API_ENDPOINTS.config_ai_providers, config);
    if (!result) {
        throw new Error('保存配置失败');
    }

    window.__ai_log.info(`${provider} 配置已静默保存`);
    return result;
}

// 缓存测试结果到localStorage
function cacheTestResult(provider, success) {
    const cacheKey = `test_result_${provider}`;
    const result = {
        success: success,
        timestamp: Date.now(),
        expires: Date.now() + (60 * 60 * 1000) // 1小时过期
    };
    localStorage.setItem(cacheKey, JSON.stringify(result));
    providerTestCache.set(provider, result);
}

// 从localStorage加载缓存的测试结果
function loadCachedTestResults() {
    window.__ai_log.info('正在加载缓存的测试结果...');
    AVAILABLE_PROVIDERS.forEach(provider => {
        const cacheKey = `test_result_${provider}`;
        const cached = localStorage.getItem(cacheKey);
        if (cached) {
            try {
                const result = JSON.parse(cached);
                // 检查是否过期
                if (result.expires > Date.now()) {
                    providerTestCache.set(provider, result);
                    window.__ai_log.info(`恢复 ${provider} 的缓存状态:`, result.success ? '可用' : '不可用');
                    // 更新UI显示
                    updateProviderStatusDisplay(provider, result.success);
                } else {
                    window.__ai_log.info(`${provider} 的缓存已过期，清除`);
                    // 清除过期的缓存
                    localStorage.removeItem(cacheKey);
                }
            } catch (e) {
                console.error(`Failed to parse cached result for ${provider}:`, e);
                localStorage.removeItem(cacheKey);
            }
        } else {
            window.__ai_log.info(`${provider} 没有缓存的测试结果`);
        }
    });
}

// 获取缓存的测试结果
function getCachedTestResult(provider) {
    return providerTestCache.get(provider);
}

// 清除所有测试缓存
function clearTestCache() {
    const providers = ['openai', 'anthropic', 'google', 'azure_openai', 'ollama'];
    providers.forEach(provider => {
        const cacheKey = `test_result_${provider}`;
        localStorage.removeItem(cacheKey);
        providerTestCache.delete(provider);
        // 重置UI状态为未测试
        updateProviderStatusDisplay(provider, false);
    });

    // 重新初始化当前提供者选择
    initCurrentProviderSelect();

    window.__ai_log.info('所有测试缓存已清除');
}

// 重置所有提供者状态为未测试状态
function resetAllProviderStatus() {
    AVAILABLE_PROVIDERS.forEach(provider => {
        const cachedResult = getCachedTestResult(provider);
        if (!cachedResult) {
            // 如果没有缓存结果，设置为未测试状态
            updateProviderStatusDisplay(provider, false);
        }
    });
}

// 更新模型下拉列表
function updateModelDropdown(provider, models) {
    if (provider === 'openai' && models && models.length > 0) {
        const modelSelect = document.getElementById('openai_model_select');
        const modelInput = document.getElementById('openai_model_input');

        if (modelSelect && modelInput) {
            // 清空现有选项
            modelSelect.innerHTML = '';

            // 添加默认选项
            const defaultOption = document.createElement('option');
            defaultOption.value = '';
            defaultOption.textContent = '选择模型...';
            modelSelect.appendChild(defaultOption);

            // 添加模型选项
            models.forEach(model => {
                const option = document.createElement('option');
                option.value = model.id;
                option.textContent = model.id;
                modelSelect.appendChild(option);
            });

            // 显示下拉列表，隐藏输入框
            modelSelect.style.display = 'block';
            modelInput.style.display = 'none';

            // 如果当前输入框有值，在下拉列表中选中对应项
            const currentModel = modelInput.value;
            if (currentModel) {
                modelSelect.value = currentModel;
            }

            // 添加change事件监听器，同步值到输入框
            modelSelect.onchange = function() {
                modelInput.value = this.value;
                if (this.value) {
                    // 如果选择了模型，可以隐藏下拉列表，显示输入框
                    this.style.display = 'none';
                    modelInput.style.display = 'block';
                }
            };

            window.__ai_log.info(`已更新 ${provider} 的模型列表，共 ${models.length} 个模型`);
        }
    }
}

// Close modal when clicking outside
document.getElementById('testModal').addEventListener('click', function(e) {
    if (e.target === this) {
        closeTestModal();
    }
});

// 图片服务相关功能
async function checkImageServiceStatus() {
    try {
        const response = await fetch('/api/image/status');
        if (response.ok) {
            const result = await response.json();
            updateImageServiceStatus(result);
        } else {
            updateImageServiceStatus({
                status: 'error',
                available_providers: [],
                message: '无法连接到图片服务'
            });
        }
    } catch (error) {
        updateImageServiceStatus({
            status: 'error',
            available_providers: [],
            message: '检查图片服务状态失败: ' + error.message
        });
    }
}

function updateImageServiceStatus(status) {
    const statusElement = document.getElementById('image-service-status');
    const providersElement = document.getElementById('available-image-providers');

    if (statusElement) {
        if (status.status === 'ok' && status.available_providers.length > 0) {
            statusElement.textContent = '✅ 正常运行';
            statusElement.style.background = '#27ae60';
        } else {
            statusElement.textContent = '❌ 服务异常';
            statusElement.style.background = '#e74c3c';
        }
    }

    if (providersElement) {
        if (status.available_providers && status.available_providers.length > 0) {
            providersElement.textContent = status.available_providers.join(', ') + ` (${status.available_providers.length}个)`;
        } else {
            providersElement.textContent = '无可用提供者';
        }
    }
}

function showImageTestResult(result, success) {
    const statusIcon = success ? '✅' : '❌';
    const statusColor = success ? '#27ae60' : '#e74c3c';

    let content = `
        <div style="text-align: center; margin-bottom: 20px;">
            <div style="font-size: 3em; margin-bottom: 10px;">${statusIcon}</div>
            <h4 style="color: ${statusColor};">${success ? '图片服务测试成功' : '图片服务测试失败'}</h4>
        </div>
    `;

    if (success) {
        content += `
            <div style="background: var(--glass-bg); border: 1px solid var(--glass-border); padding: 20px; border-radius: 8px;">
                <p style="color: var(--text-primary);"><strong>测试结果:</strong></p>
                <ul style="margin-left: 20px; color: var(--text-primary);">
        `;

        if (result.providers) {
            Object.entries(result.providers).forEach(([provider, status]) => {
                const icon = status.available ? '✅' : '❌';
                content += `<li>${icon} ${provider}: ${status.message}</li>`;
            });
        }

        content += `
                </ul>
                <p style="margin-top: 15px; color: var(--text-primary);"><strong>缓存信息:</strong></p>
                <ul style="margin-left: 20px; color: var(--text-primary);">
                    <li>缓存目录: ${result.cache_info?.directory || 'temp/images_cache'}</li>
                    <li>缓存大小: ${result.cache_info?.size || '0 MB'}</li>
                    <li>文件数量: ${result.cache_info?.file_count || 0}</li>
                </ul>
            </div>
        `;
    } else {
        content += `
            <div style="background: rgba(231, 76, 60, 0.1); border: 1px solid rgba(231, 76, 60, 0.3); padding: 20px; border-radius: 8px; border-left: 4px solid #e74c3c;">
                <p style="color: var(--text-primary);"><strong>错误信息:</strong></p>
                <div style="background: var(--bg-secondary); border: 1px solid var(--glass-border); padding: 10px; border-radius: 5px; font-family: monospace; font-size: 0.9em; color: var(--text-primary);">
                    ${result.detail || result.error || '未知错误'}
                </div>
            </div>
        `;
    }

    document.getElementById('testResults').innerHTML = content;
    document.getElementById('testModal').style.display = 'block';
}


async function saveImageServiceConfig() {
    const tab = document.getElementById('image-service');
    if (!tab) return;

    const config = {};
    const inputs = tab.querySelectorAll('input, select');

    inputs.forEach(input => {
        if (input.name) {
            if (input.type === 'checkbox') {
                config[input.name] = input.checked;
            } else if (input.value) {
                config[input.name] = input.value;
            }
        }
    });

    try {
        const response = await fetch('/api/config/image_service', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ config: config })
        });

        if (response.ok) {
            const result = await response.json();
            if (result.success) {
                showNotification('图片服务配置保存成功，已实时生效', 'success');
                // 重新检查图片服务状态
                checkImageServiceStatus();
                // 重新加载配置
                loadAllConfigs();
            } else {
                // 正确处理错误信息
                let errorMessage = '未知错误';
                if (result.errors) {
                    if (typeof result.errors === 'string') {
                        errorMessage = result.errors;
                    } else if (typeof result.errors === 'object') {
                        // 如果errors是对象，将其转换为可读的字符串
                        errorMessage = JSON.stringify(result.errors, null, 2);
                    }
                } else if (result.message) {
                    errorMessage = result.message;
                }
                showNotification('图片服务配置保存失败: ' + errorMessage, 'error');
            }
        } else {
            // 尝试解析错误响应
            try {
                const errorResult = await response.json();
                let errorMessage = '请求失败';
                if (errorResult.detail) {
                    errorMessage = errorResult.detail;
                } else if (errorResult.message) {
                    errorMessage = errorResult.message;
                }
                showNotification('图片服务配置保存失败: ' + errorMessage, 'error');
            } catch (parseError) {
                showNotification('图片服务配置保存失败: HTTP ' + response.status, 'error');
            }
        }
    } catch (error) {
        showNotification('保存失败: ' + error.message, 'error');
    }
}

// 带进度条的保存图片服务配置
async function saveImageServiceConfigWithProgress() {
    const saveBtn = document.getElementById('save-image-service-btn');
    const progressElement = document.getElementById('save-image-service-progress');
    const textElement = document.getElementById('save-image-service-text');

    if (!saveBtn || !progressElement || !textElement) {
        console.error('找不到保存按钮或进度元素');
        return;
    }

    // 显示进度
    showButtonProgress('save-image-service-btn', 'save-image-service-progress', 'save-image-service-text');

    try {
        await saveImageServiceConfig();
    } catch (error) {
        console.error('保存图片服务配置失败:', error);
        showNotification('保存失败: ' + error.message, 'error');
    } finally {
        // 隐藏进度
        hideButtonProgress('save-image-service-btn', 'save-image-service-progress', 'save-image-service-text');
    }
}

// 图片服务选项控制函数
function toggleImageServiceOptions() {
    const enableCheckbox = document.querySelector('input[name="enable_image_service"]');
    const optionsDiv = document.getElementById('image-service-options');

    if (enableCheckbox && optionsDiv) {
        if (enableCheckbox.checked) {
            optionsDiv.style.display = 'block';
            // 触发一次配置显示更新
            toggleImageSourceConfig();
        } else {
            optionsDiv.style.display = 'none';
        }
    }
}

function toggleImageSourceConfig() {
    const localCheckbox = document.querySelector('input[name="enable_local_images"]');
    const networkCheckbox = document.querySelector('input[name="enable_network_search"]');
    const aiCheckbox = document.querySelector('input[name="enable_ai_generation"]');

    const localConfig = document.getElementById('local-images-config');
    const networkConfig = document.getElementById('network-search-config');
    const aiConfig = document.getElementById('ai-generation-config');

    if (!localConfig || !networkConfig || !aiConfig) return;

    // 根据复选框状态显示/隐藏对应配置
    if (localCheckbox && localCheckbox.checked) {
        localConfig.style.display = 'block';
    } else {
        localConfig.style.display = 'none';
    }

    if (networkCheckbox && networkCheckbox.checked) {
        networkConfig.style.display = 'block';
    } else {
        networkConfig.style.display = 'none';
    }

    if (aiCheckbox && aiCheckbox.checked) {
        aiConfig.style.display = 'block';
        // 当AI生成配置显示时，也检查提供商特定配置
        toggleProviderSpecificConfig();
    } else {
        aiConfig.style.display = 'none';
    }
}

function toggleProviderSpecificConfig() {
    const providerSelect = document.querySelector('select[name="default_ai_image_provider"]');
    const pollinationsConfig = document.getElementById('pollinations-specific-config');

    if (!providerSelect || !pollinationsConfig) return;

    const selectedProvider = providerSelect.value;

    // 显示/隐藏Pollinations特定配置
    if (selectedProvider === 'pollinations') {
        pollinationsConfig.style.display = 'block';
    } else {
        pollinationsConfig.style.display = 'none';
    }
}

// 通用函数：获取提供者模型列表
async function fetchProviderModels(provider) {
    try {
        // 获取提供者配置
        const config = getProviderConfig(provider);
        if (provider !== 'ollama' && !config.api_key) {
            throw new Error(`请先配置 ${provider} 的 API Key`);
        }

        const response = await fetch(`/api/ai/providers/${provider}/models`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(config)
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const result = await response.json();
        if (!result.success) {
            throw new Error(result.error || '获取模型列表失败');
        }

        return result.models || [];
    } catch (error) {
        console.error(`获取 ${provider} 模型列表失败:`, error);
        showNotification(`获取 ${provider} 模型列表失败: ${error.message}`, 'error');
        return [];
    }
}

// 获取提供者配置
function getProviderConfig(provider) {
    const config = {};

    switch (provider) {
        case 'anthropic':
            config.api_key = getInputValue('anthropic_api_key');
            config.base_url = getInputValue('anthropic_base_url') || 'https://api.anthropic.com';
            config.api_version = getInputValue('anthropic_api_version') || '2023-06-01';
            break;
        case 'google':
            config.api_key = getInputValue('google_api_key');
            config.base_url = getInputValue('google_base_url') || 'https://generativelanguage.googleapis.com';
            break;
        case 'azure_openai':
            config.api_key = getInputValue('azure_openai_api_key');
            config.endpoint = getInputValue('azure_openai_endpoint');
            config.base_url = config.endpoint; // alias
            config.api_version = getInputValue('azure_openai_api_version') || '2024-02-15-preview';
            break;
        case 'ollama':
            config.base_url = getInputValue('ollama_base_url') || 'http://localhost:11434';
            // Ollama doesn't need API key
            break;
        default:
            throw new Error(`未知的提供者: ${provider}`);
    }

    return config;
}

// 辅助函数：获取输入框值
function getInputValue(name) {
    const input = document.querySelector(`input[name="${name}"]`);
    return input ? input.value.trim() : '';
}

// 获取并显示模型列表（支持所有提供者）
async function fetchAndShowModels(provider = 'openai') {
    const selectElement = document.getElementById(`${provider}_model_select`);
    const inputElement = document.getElementById(`${provider}_model_input`);
    const fetchButton = document.getElementById(`${provider}_model_fetch_btn`);

    if (!selectElement || !inputElement || !fetchButton) {
        console.error(`找不到 ${provider} 的模型相关元素`);
        return;
    }

    try {
        // 设置加载状态
        fetchButton.classList.add('loading');
        fetchButton.disabled = true;
        fetchButton.textContent = '⏳';

        let models = [];

        if (provider === 'openai') {
            // OpenAI 模型获取逻辑
            const baseUrlInput = document.querySelector('input[name="openai_base_url"]');
            let baseUrl = baseUrlInput ? baseUrlInput.value.trim() : '';

            if (!baseUrl) {
                baseUrl = 'https://api.openai.com/v1';
            }

            if (!baseUrl.endsWith('/v1')) {
                if (baseUrl.endsWith('/')) {
                    baseUrl += 'v1';
                } else {
                    baseUrl += '/v1';
                }
            }

            const apiKeyInput = document.querySelector('input[name="openai_api_key"]');
            let apiKey = apiKeyInput ? apiKeyInput.value.trim() : '';

            if (!apiKey) {
                try {
                    const configResponse = await fetch('/api/config/ai_providers');
                    if (configResponse.ok) {
                        const configResult = await configResponse.json();
                        if (configResult.success && configResult.config.openai_api_key) {
                            apiKey = configResult.config.openai_api_key;
                        }
                    }
                } catch (error) {
                    console.error('获取后端配置失败:', error);
                }
            }

            if (!apiKey) {
                showNotification('请先配置 OpenAI API Key', 'warning');
                return;
            }

            models = await fetchOpenAIModels(baseUrl, apiKey);

        } else {
            // 其他提供者通过API获取模型列表
            models = await fetchProviderModels(provider);
        }

        if (models && models.length > 0) {
            // 检查当前是否已经在选择模式
            const isSelectMode = selectElement.style.display !== 'none';

            if (!isSelectMode) {
                // 切换到选择模式
                // 清空现有选项
                selectElement.innerHTML = '<option value="">选择模型...</option>';

                // 添加模型选项
                models.forEach(model => {
                    const option = document.createElement('option');
                    option.value = model.id;
                    option.textContent = model.id;
                    selectElement.appendChild(option);
                });

                // 保存当前输入框的值
                const currentValue = inputElement.value;

                // 切换显示模式
                inputElement.style.display = 'none';
                selectElement.style.display = 'block';

                // 设置选择框的值
                if (currentValue && selectElement.querySelector(`option[value="${currentValue}"]`)) {
                    selectElement.value = currentValue;
                } else {
                    selectElement.value = ''; // 显示"选择模型..."
                }

                // 监听选择变化
                selectElement.onchange = function() {
                    if (this.value) {
                        inputElement.value = this.value;
                        inputElement.placeholder = this.value; // 更新placeholder为选中的模型
                    } else {
                        inputElement.value = '';
                        inputElement.placeholder = '选择模型...';
                    }
                };

                showNotification(`成功获取到 ${models.length} 个模型，请从下拉框选择`, 'success');
            } else {
                // 已经在选择模式，切换回输入模式
                selectElement.style.display = 'none';
                inputElement.style.display = 'block';

                // 恢复原始placeholder
                const defaultPlaceholders = {
                    'openai': 'gpt-4o',
                    'anthropic': 'claude-3-5-sonnet-20241022',
                    'google': 'gemini-1.5-flash',
                    'azure_openai': 'your-deployment-name',
                    'ollama': 'llama2, mistral, codellama...'
                };

                if (!inputElement.value) {
                    inputElement.placeholder = defaultPlaceholders[provider] || '输入模型名称...';
                }

                showNotification('已切换到手动输入模式', 'info');
            }
        } else {
            const providerNames = {
                'openai': 'OpenAI',
                'anthropic': 'Anthropic',
                'google': 'Google',
                'azure_openai': 'Azure OpenAI',
                'ollama': 'Ollama'
            };
            const providerName = providerNames[provider] || provider;
            showNotification(`未能获取到 ${providerName} 模型列表，请检查配置`, 'warning');
        }

    } catch (error) {
        console.error('获取模型列表失败:', error);

        let errorMessage = `获取模型列表失败: ${error.message}`;
        let suggestion = '';

        // 根据错误类型提供建议
        if (error.message.includes('NO_KEYS_AVAILABLE')) {
            suggestion = '\n\n💡 解决建议：\n• 检查API Key是否正确\n• 确认API Key有足够配额\n• 验证API Key是否已激活\n• 尝试点击🔍按钮验证API Key';
        } else if (error.message.includes('503')) {
            suggestion = '\n\n💡 解决建议：\n• API服务可能暂时不可用\n• 检查网络连接\n• 稍后重试';
        } else if (error.message.includes('401')) {
            suggestion = '\n\n💡 解决建议：\n• API Key可能无效或过期\n• 检查API Key格式是否正确\n• 确认Base URL设置正确';
        } else if (error.message.includes('429')) {
            suggestion = '\n\n💡 解决建议：\n• API调用频率过高\n• 稍等片刻后重试\n• 检查API配额限制';
        }

        showNotification(errorMessage + suggestion, 'error');
    } finally {
        // 恢复按钮状态
        fetchButton.classList.remove('loading');
        fetchButton.disabled = false;
        fetchButton.textContent = '📋';
    }
}

// 从OpenAI API获取模型列表（仅通过后端代理）
async function fetchOpenAIModels(baseUrl, apiKey) {
    try {
        // 只通过后端代理请求，避免CORS问题
        const response = await fetch('/api/ai/providers/openai/models', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                base_url: baseUrl,
                api_key: apiKey
            })
        });

        if (!response.ok) {
            // 尝试解析错误响应
            let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
            try {
                const errorData = await response.json();
                if (errorData.error) {
                    errorMessage = errorData.error;
                } else if (errorData.detail) {
                    errorMessage = errorData.detail;
                } else if (errorData.message) {
                    errorMessage = errorData.message;
                }
            } catch (parseError) {
                // 如果无法解析错误响应，使用默认错误信息
            }
            throw new Error(errorMessage);
        }

        const data = await response.json();

        // 首先检查是否是错误响应
        if (data.success === false) {
            throw new Error(data.error || '获取模型列表失败');
        }

        // 处理不同的响应格式
        let models = null;

        // 检查各种可能的响应格式
        if (data.success === true && data.models && Array.isArray(data.models)) {
            // 后端返回的格式: {"success": true, "models": [...]}
            models = data.models;
        } else if (data.models && Array.isArray(data.models)) {
            models = data.models;
        } else if (data.data && Array.isArray(data.data)) {
            // 兼容 OpenAI 原始格式
            models = data.data;
        } else if (Array.isArray(data)) {
            // 直接返回数组的情况
            models = data;
        }

        if (models) {
            // 过滤并排序模型列表，优先显示常用的聊天模型
            const sortedModels = models
                .filter(model => model.id || model.name) // 确保有ID或name
                .map(model => {
                    // 标准化模型对象
                    return {
                        id: model.id || model.name,
                        name: model.name || model.id
                    };
                })
                .sort((a, b) => {
                    // 优先级排序：gpt-4 > gpt-3.5 > gemini > 其他
                    const getPriority = (id) => {
                        if (id.includes('gpt-4')) return 4;
                        if (id.includes('gpt-3.5')) return 3;
                        if (id.includes('gemini')) return 2;
                        return 1;
                    };

                    const priorityA = getPriority(a.id);
                    const priorityB = getPriority(b.id);

                    if (priorityA !== priorityB) {
                        return priorityB - priorityA; // 降序
                    }

                    return a.id.localeCompare(b.id); // 字母序
                });

            return sortedModels;
        } else {
            throw new Error('后端代理返回的数据格式不正确，未找到模型数据');
        }

    } catch (error) {
        console.error('通过后端代理获取模型列表失败:', error);
        throw error;
    }
}

// 验证API Key
async function validateApiKey() {
    const apiKeyInput = document.querySelector('input[name="openai_api_key"]');
    const baseUrlInput = document.querySelector('input[name="openai_base_url"]');
    const validateButton = document.getElementById('openai_validate_btn');

    if (!apiKeyInput) {
        showNotification('找不到API Key输入框', 'error');
        return;
    }

    const apiKey = apiKeyInput.value.trim();
    const baseUrl = baseUrlInput ? baseUrlInput.value.trim() : '';

    if (!apiKey) {
        showNotification('请先输入API Key', 'warning');
        return;
    }

    // 更新按钮状态
    validateButton.textContent = '🔄';
    validateButton.disabled = true;

    try {
        // 使用一个简单的API调用来验证Key
        const response = await fetch('/api/ai/providers/openai/validate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                api_key: apiKey,
                base_url: baseUrl || 'https://api.openai.com/v1'
            })
        });

        const result = await response.json();
    window.__ai_log.info('验证API响应:', { status: response.status, result });

        if (response.ok && result.success) {
            showNotification(`✅ API Key 验证成功！可访问 ${result.model_count || 0} 个模型`, 'success');
            window.__ai_log.info('API Key验证详情:', result);
        } else {
            const errorMsg = result.error || result.message || `HTTP ${response.status}: 验证失败`;
            let detailedMessage = `❌ API Key 验证失败: ${errorMsg}`;

            // 根据错误类型提供具体的解决建议
            if (errorMsg.includes('NO_KEYS_AVAILABLE')) {
                detailedMessage += `

🔧 解决方案：
1. 登录 OpenAI 控制台：https://platform.openai.com/
2. 检查账户余额和配额
3. 确认 API Key 状态为 "Active"
4. 如果余额不足，请充值账户
5. 尝试创建新的 API Key

📋 其他选项：
• 尝试使用 Anthropic Claude 或 Google Gemini
• 配置 Ollama 本地模型（无需 API Key）`;
            } else if (errorMsg.includes('401')) {
                detailedMessage += `

🔧 解决方案：
1. 检查 API Key 格式是否正确（应以 sk- 开头）
2. 确认 API Key 未过期
3. 重新复制粘贴 API Key，避免多余空格`;
            } else if (errorMsg.includes('429')) {
                detailedMessage += `

🔧 解决方案：
1. 等待几分钟后重试
2. 检查 API 调用频率限制
3. 升级账户以获得更高的速率限制`;
            }

            showNotification(detailedMessage, 'error');
            console.error('API Key验证失败:', result);
        }
    } catch (error) {
        showNotification(`❌ 验证过程出错: ${error.message}`, 'error');
        console.error('API Key验证错误:', error);
    } finally {
        // 恢复按钮状态
        validateButton.textContent = '🔍';
        validateButton.disabled = false;
    }
}

// 初始化OpenAI模型输入框状态
function initOpenAIModelInput() {
    const inputElement = document.getElementById('openai_model_input');
    if (inputElement && !inputElement.value.trim()) {
        // 恢复原始placeholder，不强制显示"选择模型..."
        const originalPlaceholder = inputElement.getAttribute('placeholder');
        if (originalPlaceholder && originalPlaceholder !== '选择模型...') {
            inputElement.placeholder = originalPlaceholder;
        }
    }

    // 移除自动获取模型的行为，让用户可以正常手动输入
    // 用户需要点击📋按钮来获取模型列表
}

// 页面加载时初始化图片服务选项显示
document.addEventListener('DOMContentLoaded', function() {
    // 延迟执行以确保DOM完全加载
    setTimeout(() => {
        toggleImageServiceOptions();
        initOpenAIModelInput();
        initCurrentModelSelect();
    }, 100);
});

// 初始化当前模型选择框
async function initCurrentModelSelect() {
    // 获取当前提供者
    let currentProvider = null;

    // 首先尝试从API获取
    try {
        const response = await fetch('/api/config/current-provider');
        if (response.ok) {
            const result = await response.json();
            if (result.success && result.current_provider) {
                currentProvider = result.current_provider;
                window.__ai_log.info('从API获取当前提供者:', currentProvider);
            }
        }
    } catch (error) {
        console.warn('API获取当前提供者失败:', error);
    }

    // 如果API获取失败，尝试从可用提供者中推断
    if (!currentProvider) {
    window.__ai_log.info('API未返回提供者，尝试从可用提供者推断...');

        // 获取可用的提供者列表
        const availableProviders = getAvailableProviders();
    window.__ai_log.info('可用提供者列表:', availableProviders);

        if (availableProviders.length > 0) {
            // 使用第一个可用的提供者作为默认值
            currentProvider = availableProviders[0];
            window.__ai_log.info('使用第一个可用提供者作为当前提供者:', currentProvider);
        }
    }

    if (!currentProvider) {
        console.warn('当前提供者未设置');
        return;
    }

    window.__ai_log.info('初始化模型选择框，当前提供者:', currentProvider);

    // 延迟加载以确保DOM完全准备好
    setTimeout(() => {
        loadCurrentProviderModels(currentProvider);
    }, 200);
}

// 加载当前提供者的模型列表
async function loadCurrentProviderModels(provider) {
    const modelSelect = document.getElementById('current_model_select');
    if (!modelSelect) {
        console.error('找不到模型选择框元素');
        return;
    }

    window.__ai_log.info('加载提供者模型:', provider);

    try {
        // 清空现有选项
        modelSelect.innerHTML = '<option value="">选择模型...</option>';

        if (provider === 'openai') {
            // 尝试获取OpenAI模型列表
            const baseUrlInput = document.querySelector('input[name="openai_base_url"]');
            const apiKeyInput = document.querySelector('input[name="openai_api_key"]');

            let baseUrl = baseUrlInput ? baseUrlInput.value.trim() : '';
            let apiKey = apiKeyInput ? apiKeyInput.value.trim() : '';

            if (!baseUrl) baseUrl = 'https://api.openai.com/v1';
            if (!baseUrl.endsWith('/v1')) {
                baseUrl = baseUrl.endsWith('/') ? baseUrl + 'v1' : baseUrl + '/v1';
            }

            // 如果没有API Key，尝试从后端获取
            if (!apiKey) {
                try {
                    const configResponse = await fetch('/api/config/ai_providers');
                    if (configResponse.ok) {
                        const configResult = await configResponse.json();
                        if (configResult.success && configResult.config.openai_api_key) {
                            apiKey = configResult.config.openai_api_key;
                        }
                    }
                } catch (error) {
                    console.error('获取后端配置失败:', error);
                }
            }

            if (apiKey) {
                const models = await fetchOpenAIModels(baseUrl, apiKey);
                if (models && models.length > 0) {
                    models.forEach(model => {
                        const option = document.createElement('option');
                        option.value = model.id;
                        option.textContent = model.id;
                        modelSelect.appendChild(option);
                    });

                    // 从API实时获取当前选中的模型
                    try {
                        const configResponse = await fetch('/api/config/ai_providers');
                        if (configResponse.ok) {
                            const configResult = await configResponse.json();
                            window.__ai_log.info('OpenAI API配置响应:', configResult);
                            if (configResult.success && configResult.config) {
                                const currentModel = configResult.config.openai_model;
                                window.__ai_log.info('从API获取到OpenAI当前模型:', currentModel);
                                window.__ai_log.info('可用模型选项:', Array.from(modelSelect.options).map(opt => opt.value));
                                if (currentModel) {
                                    modelSelect.value = currentModel;
                                    window.__ai_log.info('设置后的模型选择框值:', modelSelect.value);
                                } else {
                                    window.__ai_log.info('API中没有OpenAI模型配置');
                                }
                            } else {
                                window.__ai_log.info('API响应格式异常:', configResult);
                            }
                        } else {
                            console.error('获取配置API失败，状态码:', configResponse.status);
                        }
                    } catch (error) {
                        console.error('获取OpenAI当前模型失败:', error);
                    }
                }
            }
        } else {
            // 其他提供者通过API获取模型
            const models = await fetchProviderModels(provider);
            if (models && models.length > 0) {
                models.forEach(model => {
                    const option = document.createElement('option');
                    option.value = model.id;
                    option.textContent = model.id;
                    modelSelect.appendChild(option);
                });
            }

            // 从API实时获取当前选中的模型
            try {
                const configResponse = await fetch('/api/config/ai_providers');
                if (configResponse.ok) {
                    const configResult = await configResponse.json();
                    if (configResult.success && configResult.config) {
                        let currentModel = '';

                        if (provider === 'anthropic') {
                            currentModel = configResult.config['anthropic_model'] || '';
                        } else if (provider === 'google') {
                            currentModel = configResult.config['google_model'] || '';
                        } else if (provider === 'ollama') {
                            currentModel = configResult.config['ollama_model'] || '';
                        } else if (provider === 'azure_openai') {
                            currentModel = configResult.config['azure_openai_deployment_name'] || '';
                        }

                        window.__ai_log.info(`从API获取到 ${provider} 的当前模型:`, currentModel);

                        if (currentModel) {
                            modelSelect.value = currentModel;
                        }
                    }
                }
            } catch (error) {
                console.error(`获取 ${provider} 当前模型失败:`, error);
            }
        }
    } catch (error) {
        console.error('加载模型列表失败:', error);
    }
}

// 保存并测试当前选择的模型
async function saveAndTestCurrentModel() {
    const modelSelect = document.getElementById('current_model_select');

    if (!modelSelect || !modelSelect.value) {
        showNotification('请先选择一个模型', 'warning');
        return;
    }

    // 显示进度条
    showButtonProgress('save_model_btn', 'save-model-progress', 'save-model-text');

    try {
        // 获取当前提供者
        let currentProvider = null;

        // 首先尝试从API获取
        try {
            const response = await fetch('/api/config/current-provider');
            if (response.ok) {
                const result = await response.json();
                if (result.success && result.current_provider) {
                    currentProvider = result.current_provider;
                    window.__ai_log.info('从API获取到当前提供者:', currentProvider);
                }
            }
        } catch (error) {
            console.warn('API获取当前提供者失败:', error);
        }

        // 如果API获取失败，尝试从可用提供者中推断
        if (!currentProvider) {
            window.__ai_log.info('API未返回提供者，尝试从可用提供者推断...');

            // 获取可用的提供者列表
            const availableProviders = getAvailableProviders();
            window.__ai_log.info('可用提供者列表:', availableProviders);

            if (availableProviders.length > 0) {
                // 使用第一个可用的提供者作为默认值
                currentProvider = availableProviders[0];
                window.__ai_log.info('使用第一个可用提供者作为当前提供者:', currentProvider);
            }
        }

        if (!currentProvider) {
            showNotification('没有可用的提供者，请先配置并测试至少一个AI提供者', 'error');
            return;
        }

        const selectedModel = modelSelect.value;

        // 构建配置对象
        const config = {};

        // 根据提供者类型设置正确的配置键
        if (currentProvider === 'azure_openai') {
            config['azure_openai_deployment_name'] = selectedModel;
        } else {
            config[currentProvider + '_model'] = selectedModel;
        }

    window.__ai_log.info('保存模型配置:', config);

        // 保存配置 - 使用正确的API端点
        const saveResponse = await fetch('/api/config/all', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                config: config
            })
        });

        if (!saveResponse.ok) {
            const errorText = await saveResponse.text();
            throw new Error(`HTTP ${saveResponse.status}: ${errorText}`);
        }

        const saveResult = await saveResponse.json();
        if (!saveResult.success) {
            throw new Error(saveResult.message || '保存失败');
        }

    window.__ai_log.info('模型配置保存成功');

        // 保存成功后，测试该提供者和模型
        const testSuccess = await testProviderSilently(currentProvider);

        if (testSuccess) {
            showNotification(`模型 ${selectedModel} 保存并测试成功！`, 'success');

            // 更新状态显示
            updateProviderStatusDisplay(currentProvider, true);

            // 刷新当前提供者下拉框
            await initCurrentProviderSelect();
        } else {
            showNotification(`模型 ${selectedModel} 已保存，但测试失败。请检查模型名称是否正确。`, 'warning');
        }

    } catch (error) {
        console.error('保存并测试模型失败:', error);
        showNotification('保存并测试失败: ' + error.message, 'error');
    } finally {
        // 隐藏进度条
        hideButtonProgress('save_model_btn', 'save-model-progress', 'save-model-text');
    }
}

// 保存当前选择的模型（原始函数，保留作为备用）
async function saveCurrentModel() {
    const modelSelect = document.getElementById('current_model_select');
    const saveBtn = document.getElementById('save_model_btn');

    if (!modelSelect || !modelSelect.value) {
        showNotification('请先选择一个模型', 'warning');
        return;
    }

    try {
        saveBtn.disabled = true;
        saveBtn.textContent = '保存中...';

        // 获取当前提供者
        let currentProvider = null;

        // 首先尝试从API获取
        try {
            const response = await fetch('/api/config/current-provider');
            if (response.ok) {
                const result = await response.json();
                if (result.success && result.current_provider) {
                    currentProvider = result.current_provider;
                    window.__ai_log.info('从API获取到当前提供者:', currentProvider);
                }
            }
        } catch (error) {
            console.warn('API获取当前提供者失败:', error);
        }

        // 如果API获取失败，尝试从可用提供者中推断
        if (!currentProvider) {
            window.__ai_log.info('API未返回提供者，尝试从可用提供者推断...');

            // 获取可用的提供者列表
            const availableProviders = getAvailableProviders();
            window.__ai_log.info('可用提供者列表:', availableProviders);

            if (availableProviders.length > 0) {
                // 使用第一个可用的提供者作为默认值
                currentProvider = availableProviders[0];
                window.__ai_log.info('使用第一个可用提供者作为当前提供者:', currentProvider);
            }
        }

        if (!currentProvider) {
            showNotification('没有可用的提供者，请先配置并测试至少一个AI提供者', 'error');
            return;
        }

        const selectedModel = modelSelect.value;

        // 构建配置对象
        const config = {};

        // 根据提供者类型设置正确的配置键
        if (currentProvider === 'azure_openai') {
            config['azure_openai_deployment_name'] = selectedModel;
        } else {
            config[currentProvider + '_model'] = selectedModel;
        }

        // 保存配置
        const response = await fetch('/api/config/update', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(config)
        });

        if (response.ok) {
            const result = await response.json();
            if (result.success) {
                showNotification(`已将 ${currentProvider} 的默认模型设置为: ${selectedModel}`, 'success');

                // 更新对应提供者配置卡片中的模型输入框
                const providerCard = document.querySelector(`[data-provider="${currentProvider}"]`);
                if (providerCard) {
                    let modelInputName = currentProvider + '_model';
                    if (currentProvider === 'azure_openai') {
                        modelInputName = 'azure_openai_deployment_name';
                    }

                    const modelInput = providerCard.querySelector(`input[name="${modelInputName}"]`);
                    if (modelInput) {
                        modelInput.value = selectedModel;
                    }
                }
            } else {
                throw new Error(result.error || '保存失败');
            }
        } else {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
    } catch (error) {
        console.error('保存模型配置失败:', error);
        showNotification('保存失败: ' + error.message, 'error');
    } finally {
        saveBtn.disabled = false;
        saveBtn.textContent = '保存';
    }
}

// 质量预设映射
const QUALITY_PRESETS = {
    conservative: { temperature: 0.2, top_p: 0.8, max_tokens: 1500 },
    balanced:     { temperature: 0.7, top_p: 1.0, max_tokens: 2000 },
    creative:     { temperature: 1.1, top_p: 1.0, max_tokens: 2400 },
};

function onPageCountModeChange(mode){
    const fixedGroup = document.getElementById('fixedPagesGroup');
    const rangeGroup = document.getElementById('rangePagesGroup');
    if(mode === 'fixed'){
        fixedGroup.style.display = '';
        rangeGroup.style.display = 'none';
    }else if(mode === 'custom_range'){
        fixedGroup.style.display = 'none';
        rangeGroup.style.display = '';
    }else{
        fixedGroup.style.display = 'none';
        rangeGroup.style.display = 'none';
    }
}

// 预设选择时自动带出参数但不强制覆盖用户手动输入
(function bindQualityPreset(){
    document.addEventListener('change', function(e){
        if(e.target && e.target.name === 'generation_quality_preset'){
            const p = QUALITY_PRESETS[e.target.value];
            if(!p) return;
            const temp = document.querySelector('#generation-params input[name="temperature"]');
            const topP = document.querySelector('#generation-params input[name="top_p"]');
            const maxT = document.querySelector('#generation-params input[name="max_tokens"]');
            if(temp && !temp.dataset.userEdited){ temp.value = p.temperature; temp.dispatchEvent(new Event('input')); }
            if(topP && !topP.dataset.userEdited){ topP.value = p.top_p; topP.dispatchEvent(new Event('input')); }
            if(maxT && !maxT.dataset.userEdited){ maxT.value = p.max_tokens; maxT.dispatchEvent(new Event('input')); }
        }
    });

    ['temperature','top_p','max_tokens'].forEach(name =>{
        const el = document.querySelector(`#generation-params input[name="${name}"]`);
        if(el){ el.addEventListener('input', ()=>{ el.dataset.userEdited = '1'; }); }
    });
})();

// Apryse许可证检测功能
async function checkApryseLicense() {
    const btn = document.getElementById('checkLicenseBtn');
    const status = document.getElementById('licenseStatus');
    const input = document.getElementById('apryse_license_key');

    // 检查是否输入了许可证
    if (!input.value.trim()) {
        showLicenseStatus('请先输入Apryse许可证密钥', 'error');
        return;
    }

    // 显示检测中状态
    btn.disabled = true;
    btn.textContent = '检测中...';
    showLicenseStatus('正在验证许可证...', 'info');

    try {
        // 先保存当前配置以确保许可证被更新
        const licenseKey = input.value.trim();

        // 创建FormData对象并添加许可证密钥
        const formData = new FormData();
        formData.append('apryse_license_key', licenseKey);

        // 保存配置
        const saveResponse = await fetch('/api/config/all', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                config: { apryse_license_key: licenseKey }
            })
        });

        if (!saveResponse.ok) {
            throw new Error('保存配置失败');
        }

        // 检测许可证
        const response = await fetch('/api/apryse/license/check');
        const result = await response.json();

        if (result.valid) {
            showLicenseStatus(`✅ ${result.message}`, 'success');
        } else {
            showLicenseStatus(`❌ ${result.error}`, 'error');
        }

    } catch (error) {
        console.error('许可证检测失败:', error);
        showLicenseStatus(`❌ 检测失败: ${error.message}`, 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = '检测许可证';
    }
}

function showLicenseStatus(message, type) {
    const status = document.getElementById('licenseStatus');
    status.style.display = 'block';
    status.textContent = message;

    // 清除之前的样式
    status.className = '';

    // 根据类型设置样式
    switch (type) {
        case 'success':
            status.style.background = '#d4edda';
            status.style.color = '#155724';
            status.style.border = '1px solid #c3e6cb';
            break;
        case 'error':
            status.style.background = '#f8d7da';
            status.style.color = '#721c24';
            status.style.border = '1px solid #f5c6cb';
            break;
        case 'info':
            status.style.background = '#d1ecf1';
            status.style.color = '#0c5460';
            status.style.border = '1px solid #bee5eb';
            break;
        default:
            status.style.background = '#f8f9fa';
            status.style.color = '#6c757d';
            status.style.border = '1px solid #dee2e6';
    }
}

// 在加载配置后，根据 page_count_mode 控制显示
(function patchPopulate(){
    const orig = populateGenerationParams;
    window.populateGenerationParams = function(){
        orig.apply(this, arguments);
        const tab = document.getElementById('generation-params');
        if(!tab) return;
        const modeEl = tab.querySelector('select[name="page_count_mode"]');
        if(modeEl){ onPageCountModeChange(modeEl.value); }
    }
})();

// 数据备份相关功能
// 刷新部署模式信息
async function refreshDeploymentMode() {
    try {
        const response = await fetch('/api/deployment/mode');
        if (response.ok) {
            const result = await response.json();
            // API直接返回数据，不需要检查success字段
            updateDeploymentModeDisplay(result);
        } else {
            const errorData = await response.json().catch(() => ({}));
            const errorMessage = errorData.detail || '获取部署模式失败';
            showNotification(errorMessage, 'error');
        }
    } catch (error) {
        console.error('刷新部署模式失败:', error);
        showNotification('刷新部署模式失败: ' + error.message, 'error');
    }
}

// 更新部署模式显示
function updateDeploymentModeDisplay(result) {
    const modeElement = document.getElementById('current-deployment-mode');
    const detailsElement = document.getElementById('deployment-mode-details');

    if (modeElement) {
        let modeText = result.current_mode || '未知';
        let bgColor = '#95a5a6'; // 默认灰色

        // 根据模式设置不同的颜色
        switch (result.current_mode) {
            case 'local_only':
                bgColor = '#e74c3c'; // 红色
                modeText = 'LOCAL_ONLY';
                break;
            case 'local_external':
                bgColor = '#f39c12'; // 橙色
                modeText = 'LOCAL_EXTERNAL';
                break;
            case 'local_r2':
                bgColor = '#27ae60'; // 绿色
                modeText = 'LOCAL_R2';
                break;
            case 'local_external_r2':
                bgColor = '#8e44ad'; // 紫色
                modeText = 'LOCAL_EXTERNAL_R2';
                break;
        }

        modeElement.textContent = modeText;
        modeElement.style.background = bgColor;
    }

    if (detailsElement) {
        let details = '';
        details += `<strong>当前模式:</strong> ${result.current_mode || '未知'}<br>`;
        details += `<strong>检测模式:</strong> ${result.detected_mode || '未知'}<br>`;
        if (result.switch_in_progress) {
            details += `<strong>状态:</strong> <span style="color: #f39c12;">模式切换中...</span><br>`;
        } else {
            details += `<strong>状态:</strong> <span style="color: #27ae60;">正常</span><br>`;
        }
        if (result.last_check) {
            // API返回的是ISO格式字符串，直接使用new Date()解析
            const lastCheckDate = new Date(result.last_check);
            details += `<strong>最后检查:</strong> ${lastCheckDate.toLocaleString()}<br>`;
        }
        detailsElement.innerHTML = details || '暂无详细信息';
    }
}

// 创建数据库备份
async function createDatabaseBackup() {
    try {
        showNotification('正在创建数据库备份...', 'info');

        const response = await fetch('/api/backup/database', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        });

        if (response.ok) {
            const result = await response.json();
            if (result.success) {
                showNotification('数据库备份创建成功！', 'success');
                // 刷新备份历史
                refreshBackupHistory();
                // 更新最后备份时间
                updateLastBackupInfo(result.backup_info);
            } else {
                showNotification('备份创建失败: ' + (result.error || '未知错误'), 'error');
            }
        } else {
            showNotification('备份创建失败', 'error');
        }
    } catch (error) {
        console.error('创建数据库备份失败:', error);
        showNotification('创建备份失败: ' + error.message, 'error');
    }
}

// 下载最新备份
async function downloadLatestBackup() {
    try {
        const response = await fetch('/api/backup/download/latest');
        if (response.ok) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = url;
            a.download = `flowslide_backup_${new Date().toISOString().split('T')[0]}.sql`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
            showNotification('备份文件下载成功！', 'success');
        } else {
            showNotification('下载备份失败', 'error');
        }
    } catch (error) {
        console.error('下载备份失败:', error);
        showNotification('下载备份失败: ' + error.message, 'error');
    }
}

// 同步到R2
async function syncToR2() {
    try {
        showNotification('正在同步到R2云存储...', 'info');

        const response = await fetch('/api/backup/sync/r2', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        });

        if (response.ok) {
            const result = await response.json();
            if (result.success) {
                showNotification('同步到R2成功！', 'success');
                updateR2SyncStatus(result.sync_info);
            } else {
                showNotification('同步失败: ' + (result.error || '未知错误'), 'error');
            }
        } else {
            showNotification('同步到R2失败', 'error');
        }
    } catch (error) {
        console.error('同步到R2失败:', error);
        showNotification('同步失败: ' + error.message, 'error');
    }
}

// 从R2恢复
async function restoreFromR2() {
    if (!confirm('确定要从R2云存储恢复数据吗？这将覆盖当前数据！')) {
        return;
    }

    try {
        showNotification('正在从R2恢复数据...', 'info');

        const response = await fetch('/api/backup/restore/r2', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        });

        if (response.ok) {
            const result = await response.json();
            if (result.success) {
                showNotification('数据恢复成功！请刷新页面查看最新数据。', 'success');
                updateR2SyncStatus(result.restore_info);
            } else {
                showNotification('恢复失败: ' + (result.error || '未知错误'), 'error');
            }
        } else {
            showNotification('从R2恢复失败', 'error');
        }
    } catch (error) {
        console.error('从R2恢复失败:', error);
        showNotification('恢复失败: ' + error.message, 'error');
    }
}

// 测试数据库连接
async function testDatabaseConnection() {
    const statusElement = document.getElementById('db-connection-status');
    if (statusElement) {
        statusElement.textContent = '测试中...';
        statusElement.style.background = '#f39c12'; // 橙色
    }

    try {
        const response = await fetch('/api/system/db-test');
        if (response.ok) {
            const result = await response.json();
            if (result.success) {
                if (statusElement) {
                    statusElement.textContent = '✅ 正常';
                    statusElement.style.background = '#27ae60'; // 绿色
                }
                showNotification('数据库连接正常！', 'success');
            } else {
                if (statusElement) {
                    statusElement.textContent = '❌ 异常';
                    statusElement.style.background = '#e74c3c'; // 红色
                }
                showNotification('数据库连接异常: ' + (result.error || '未知错误'), 'error');
            }
        } else {
            if (statusElement) {
                statusElement.textContent = '❌ 失败';
                statusElement.style.background = '#e74c3c'; // 红色
            }
            showNotification('数据库连接测试失败', 'error');
        }
    } catch (error) {
        console.error('测试数据库连接失败:', error);
        if (statusElement) {
            statusElement.textContent = '❌ 错误';
            statusElement.style.background = '#e74c3c'; // 红色
        }
        showNotification('测试失败: ' + error.message, 'error');
    }
}

// 刷新备份历史
async function refreshBackupHistory() {
    try {
        const response = await fetch('/api/backup/history');
        if (response.ok) {
            const result = await response.json();
            if (result.success) {
                updateBackupHistory(result.backups || []);
            } else {
                console.error('获取备份历史失败:', result.error);
            }
        }
    } catch (error) {
        console.error('刷新备份历史失败:', error);
    }
}

// 更新备份历史显示
function updateBackupHistory(backups) {
    const historyElement = document.getElementById('backup-history');
    if (!historyElement) return;

    if (backups.length === 0) {
        historyElement.innerHTML = '<div style="text-align: center; color: #6c757d; padding: 20px;">暂无备份记录</div>';
        return;
    }

    let html = '';
    backups.slice(0, 10).forEach(backup => { // 只显示最近10个
        const date = new Date(backup.created_at).toLocaleString();
        const size = backup.size ? formatFileSize(backup.size) : '未知';
        html += `
            <div style="padding: 8px 0; border-bottom: 1px solid var(--glass-border);">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-weight: 500;">${date}</span>
                    <span style="font-size: 0.8em; color: #6c757d;">${size}</span>
                </div>
                <div style="font-size: 0.8em; color: #6c757d; margin-top: 2px;">
                    ${backup.filename || '未知文件名'}
                </div>
            </div>
        `;
    });

    historyElement.innerHTML = html;
}

// 更新最后备份信息
function updateLastBackupInfo(backupInfo) {
    const timeElement = document.getElementById('last-db-backup');
    const sizeElement = document.getElementById('db-backup-size');

    if (timeElement && backupInfo.created_at) {
        timeElement.textContent = new Date(backupInfo.created_at).toLocaleString();
    }

    if (sizeElement && backupInfo.size) {
        sizeElement.textContent = formatFileSize(backupInfo.size);
    }
}

// 更新R2同步状态
function updateR2SyncStatus(syncInfo) {
    const statusElement = document.getElementById('r2-sync-status');
    const timeElement = document.getElementById('last-r2-sync');

    if (statusElement) {
        if (syncInfo && syncInfo.success) {
            statusElement.textContent = '✅ 已同步';
            statusElement.style.background = '#27ae60'; // 绿色
        } else {
            statusElement.textContent = '❌ 同步失败';
            statusElement.style.background = '#e74c3c'; // 红色
        }
    }

    if (timeElement && syncInfo && syncInfo.timestamp) {
        timeElement.textContent = new Date(syncInfo.timestamp).toLocaleString();
    }
}

// 切换自动备份
function toggleAutoBackup() {
    const checkbox = document.querySelector('input[name="auto_backup_enabled"]');
    const isEnabled = checkbox.checked;

    showNotification(isEnabled ? '自动备份已启用' : '自动备份已禁用', 'info');
}

// 清理旧备份
async function cleanupOldBackups() {
    if (!confirm('确定要清理旧备份文件吗？此操作不可恢复！')) {
        return;
    }

    try {
        showNotification('正在清理旧备份...', 'info');

        const response = await fetch('/api/backup/cleanup', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        });

        if (response.ok) {
            const result = await response.json();
            if (result.success) {
                showNotification(`清理完成！删除了 ${result.deleted_count || 0} 个旧备份文件`, 'success');
                refreshBackupHistory();
            } else {
                showNotification('清理失败: ' + (result.error || '未知错误'), 'error');
            }
        } else {
            showNotification('清理旧备份失败', 'error');
        }
    } catch (error) {
        console.error('清理旧备份失败:', error);
        showNotification('清理失败: ' + error.message, 'error');
    }
}

// 保存备份配置
async function saveBackupConfig() {
    try {
        const config = {};

        // 收集自动备份设置
        const autoBackupEnabled = document.querySelector('input[name="auto_backup_enabled"]');
        if (autoBackupEnabled) {
            config.auto_backup_enabled = autoBackupEnabled.checked;
        }

        // 收集备份间隔
        const backupInterval = document.querySelector('select[name="backup_interval"]');
        if (backupInterval) {
            config.backup_interval = backupInterval.value;
        }

        // 收集最大备份数量
        const maxBackups = document.querySelector('input[name="max_backups"]');
        if (maxBackups) {
            config.max_backups = parseInt(maxBackups.value) || 10;
        }

        const response = await fetch('/api/backup/config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(config)
        });

        if (response.ok) {
            const result = await response.json();
            if (result.success) {
                showNotification('备份配置保存成功！', 'success');
            } else {
                showNotification('保存失败: ' + (result.error || '未知错误'), 'error');
            }
        } else {
            showNotification('备份配置保存失败', 'error');
        }
    } catch (error) {
        console.error('保存备份配置失败:', error);
        showNotification('保存失败: ' + error.message, 'error');
    }
}

// 格式化文件大小
function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// 初始化数据备份页面
async function initDataBackupPage() {
    try {
        // 刷新部署模式信息
        await refreshDeploymentMode();

        // 加载备份配置
        await loadBackupConfig();

        // 刷新备份历史
        await refreshBackupHistory();

        // 加载系统资源信息
        await loadSystemResources();

        // 检查R2同步状态
        await checkR2Status();

    } catch (error) {
        console.error('初始化数据备份页面失败:', error);
    }
}

// 加载备份配置
async function loadBackupConfig() {
    try {
        const response = await fetch('/api/backup/config');
        if (response.ok) {
            const result = await response.json();
            if (result.success) {
                const config = result.config;

                // 更新表单值
                const autoBackupEnabled = document.getElementById('autoBackupEnabled');
                const backupInterval = document.getElementById('backupInterval');
                const maxBackups = document.getElementById('maxBackups');
                const retentionDays = document.getElementById('retentionDays');

                if (autoBackupEnabled) autoBackupEnabled.checked = config.auto_backup_enabled;
                if (backupInterval) backupInterval.value = config.backup_interval;
                if (maxBackups) maxBackups.value = config.max_backups;
                if (retentionDays) retentionDays.value = config.retention_days;

                console.log('备份配置已加载:', config);
            }
        } else {
            console.error('加载备份配置失败:', response.status);
        }
    } catch (error) {
        console.error('加载备份配置出错:', error);
    }
}

// 加载系统资源信息
async function loadSystemResources() {
    try {
        const response = await fetch('/api/system/resources');
        if (response.ok) {
            const result = await response.json();
            if (result.success) {
                updateSystemResources(result.resources);
            }
        }
    } catch (error) {
        console.error('加载系统资源信息失败:', error);
    }
}

// 更新系统资源显示
function updateSystemResources(resources) {
    const memoryElement = document.getElementById('memory-usage');
    const diskElement = document.getElementById('disk-usage');
    const uptimeElement = document.getElementById('uptime');

    if (memoryElement && resources.memory) {
        memoryElement.textContent = `${resources.memory.used} / ${resources.memory.total}`;
    }

    if (diskElement && resources.disk) {
        diskElement.textContent = `${resources.disk.used} / ${resources.disk.total}`;
    }

    if (uptimeElement && resources.uptime) {
        uptimeElement.textContent = formatUptime(resources.uptime);
    }
}

// 检查R2状态
async function checkR2Status() {
    try {
        const response = await fetch('/api/system/r2-status');
        if (response.ok) {
            const result = await response.json();
            if (result.success) {
                updateR2SyncStatus(result.r2_status);
            }
        }
    } catch (error) {
        console.error('检查R2状态失败:', error);
    }
}

// 格式化运行时间
function formatUptime(seconds) {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);

    if (days > 0) {
        return `${days}天 ${hours}小时 ${minutes}分钟`;
    } else if (hours > 0) {
        return `${hours}小时 ${minutes}分钟`;
    } else {
        return `${minutes}分钟`;
    }
}

// 页面加载时初始化数据备份功能
document.addEventListener('DOMContentLoaded', function() {
    // 检查当前是否在数据备份标签页，如果是则初始化
    const dataBackupTab = document.getElementById('data-backup');
    if (dataBackupTab && !dataBackupTab.classList.contains('active')) {
        // 标签页未激活，不初始化
        return;
    }

    // 延迟初始化，确保DOM完全加载
    setTimeout(() => {
        initDataBackupPage();
    }, 500);
});

// 监听标签页切换事件
document.addEventListener('click', function(e) {
    if (e.target.closest('[data-tab="data-backup"]')) {
        // 切换到数据备份标签页时初始化
        setTimeout(() => {
        initDataBackupPage();
    }, 100);
    }
});

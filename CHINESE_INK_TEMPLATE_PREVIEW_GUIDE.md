# 中国泼墨风模板预览实现指南

## 问题描述
在 `/template-selection` 页面的小框预览中，中国泼墨风模板的内容无法正确显示。

## 解决方案

### 1. 模板数据获取
```javascript
// 获取中国泼墨风模板（ID=1）的详细信息
async function loadTemplatePreview(templateId) {
    const response = await fetch('/api/global-master-templates/' + templateId);
    const template = await response.json();
    // template.html_template 包含完整的HTML内容
}
```

### 2. 模板变量替换
在 `loadTemplatePreview` 函数中，需要替换以下变量：

```javascript
const replacements = [
    ['title', template.template_name || '中国泼墨风'],
    ['page_title', template.template_name || '中国泼墨风'],
    ['main_title', template.template_name || '中国泼墨风'],
    ['main_heading', template.template_name || '中国泼墨风'],
    ['heading', template.template_name || '中国泼墨风'],
    ['subtitle', '子标题'],
    ['content', '这是模板预览内容'],
    ['body', '这是模板预览内容'],
    ['author', 'FlowSlide'],
    ['company_name', 'Your Company'],
    ['username', 'User'],
    ['date', new Date().toLocaleDateString()],
    ['footer', 'FlowSlide 预览'],
    ['page', '1'],
    ['page_number', '1'],
    ['slide_number', '1'],
    ['current_slide', '1'],
    ['current_page_number', '1'],
    ['total_slides', '1'],
    ['total_pages', '1'],
    ['total_page_count', '1'],
    ['theme_color', '#4f46e5'],
    ['background_color', '#ffffff'],
    ['logo_url', '']
];
```

### 3. iframe内容设置
```javascript
// 替换模板变量
let previewHtml = template.html_template || '';
replacements.forEach(([key, value]) => {
    const re = new RegExp(`\\{\\{\\s*${key}\\s*\\}\\}`,'g');
    previewHtml = previewHtml.replace(re, String(value));
});

// 添加预览专用CSS
const previewInjectCSS = `<style>
    /* 确保根元素正确显示 */
    html, body {
        width: 100% !important;
        height: 100% !important;
        margin: 0 !important;
        padding: 0 !important;
        overflow: hidden !important;
    }

    /* 确保slide容器可见 */
    .slide, .ppt-slide, #root, .page, .slide-content {
        display: block !important;
        opacity: 1 !important;
        visibility: visible !important;
    }
</style>`;

// 注入CSS
if (/<head[^>]*>/i.test(previewHtml)) {
    previewHtml = previewHtml.replace(/<head[^>]*>/i, function(m) {
        return m + previewInjectCSS;
    });
}

// 创建blob URL并设置到iframe
const blob = new Blob([previewHtml], { type: 'text/html' });
const url = URL.createObjectURL(blob);
iframe.src = url;

// iframe加载完成后应用缩放
iframe.onload = function() {
    applyCoverScaleForIframe(templateId, iframe);
    // 延迟释放blob URL
    setTimeout(() => URL.revokeObjectURL(url), 10000);
};
```

### 4. iframe缩放函数
```javascript
function applyCoverScaleForIframe(templateId, iframe) {
    const container = document.getElementById('preview-' + templateId);
    if (!container || !iframe) return;

    const rect = container.getBoundingClientRect();

    // 使用模板的自然尺寸 (16:9 比例)
    const naturalW = 1280;
    const naturalH = 720;

    // 计算cover缩放比例
    const coverScale = Math.max(rect.width / naturalW, rect.height / naturalH);
    const safeScale = Math.max(0.05, Math.min(20, coverScale));

    // 设置iframe尺寸和缩放
    iframe.style.width = `${naturalW}px`;
    iframe.style.height = `${naturalH}px`;
    iframe.style.transform = `scale(${safeScale})`;
    iframe.style.transformOrigin = 'top left';

    // 居中对齐
    const scaledWidth = naturalW * safeScale;
    const scaledHeight = naturalH * safeScale;
    const offsetX = (rect.width - scaledWidth) / 2;
    const offsetY = (rect.height - scaledHeight) / 2;

    iframe.style.position = 'absolute';
    iframe.style.left = `${offsetX}px`;
    iframe.style.top = `${offsetY}px`;
}
```

### 5. CSS样式要求
确保 `.template-preview-iframe` 的CSS样式正确：

```css
.template-preview-iframe {
    width: 1280px;
    height: 720px;
    border: none;
    position: absolute;
    left: 50%;
    top: 50%;
    transform: translate(-50%, -50%);
    opacity: 0;
    transition: transform 180ms ease-out, opacity 180ms ease-out;
    transform-origin: center center;
    border-radius: 4px;
}
```

## 关键要点

1. **尺寸一致性**：模板原始尺寸(1280x720)必须与iframe尺寸保持一致
2. **变量替换**：所有模板变量必须被正确替换，包括 `{{ page_title }}`、`{{ main_heading }}` 等
3. **CSS注入**：确保模板样式正确注入到iframe中
4. **缩放计算**：使用cover缩放算法确保内容适应预览框
5. **资源管理**：正确管理blob URL的创建和释放

## 测试验证

创建的 `test_chinese_ink_template.html` 文件展示了正确的实现方式，可以作为参考。

按照以上步骤实现后，中国泼墨风模板的小框预览应该能够正确显示其独特的泼墨风格，包括：
- 书法字体标题
- 墨色背景纹理
- 红色装饰元素
- 传统布局结构

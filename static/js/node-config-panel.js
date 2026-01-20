/**
 * 工作流节点配置面板组件
 * 提供完整的节点配置界面，支持Schema驱动的动态表单生成
 */

class NodeConfigPanel {
    constructor(container, options = {}) {
        this.container = container;
        this.options = {
            showModuleAssociation: true,
            showVariablePicker: true,
            ...options
        };
        this.currentConfig = {};
        this.currentNodeType = null;
        
        this.init();
    }
    
    init() {
        this.render();
        this.bindEvents();
    }
    
    render() {
        this.container.innerHTML = `
            <div class="node-config-panel">
                <div class="config-header">
                    <h3>节点配置</h3>
                    <button class="close-btn" onclick="this.close()">&times;</button>
                </div>
                
                <div class="config-tabs">
                    <button class="tab-btn active" data-tab="basic">基本配置</button>
                    <button class="tab-btn" data-tab="function">功能配置</button>
                    <button class="tab-btn" data-tab="module" style="${this.options.showModuleAssociation ? '' : 'display:none'}">模块关联</button>
                    <button class="tab-btn" data-tab="advanced">高级设置</button>
                </div>
                
                <div class="config-content">
                    <div class="tab-content active" id="tab-basic">
                        <div class="form-group">
                            <label>节点名称 <span class="required">*</span></label>
                            <input type="text" id="node-name" class="form-input" placeholder="输入节点名称">
                        </div>
                        <div class="form-group">
                            <label>节点类型</label>
                            <select id="node-type" class="form-input" disabled>
                                <option value="">请选择节点类型</option>
                                <option value="workflow_trigger">工作流触发</option>
                                <option value="chat_history">对话历史</option>
                                <option value="data_input">数据输入</option>
                                <option value="data_output">数据输出</option>
                                <option value="document_extractor">文档提取</option>
                                <option value="delay">延迟</option>
                                <option value="ai_generation">AI生成</option>
                                <option value="ai_classification">AI分类</option>
                                <option value="ai_extraction">AI提取</option>
                                <option value="intent_recognition">意图识别</option>
                                <option value="sentiment_analysis">情感分析</option>
                                <option value="condition">条件分支</option>
                                <option value="loop">循环处理</option>
                                <option value="iterator">迭代器</option>
                                <option value="parallel">并行处理</option>
                                <option value="http_request">HTTP请求</option>
                                <option value="webhook">Webhook</option>
                                <option value="database_query">数据库查询</option>
                                <option value="message_queue">消息队列</option>
                                <option value="variable_aggregation">变量聚合</option>
                                <option value="parameter_aggregation">参数聚合</option>
                                <option value="variable_assignment">变量赋值</option>
                                <option value="data_transform">数据转换</option>
                                <option value="data_filter">数据过滤</option>
                                <option value="data_aggregation">数据聚合</option>
                                <option value="data_formatting">数据格式化</option>
                                <option value="text_processing">文本处理</option>
                                <option value="template_render">模板渲染</option>
                                <option value="image_processing">图片处理</option>
                                <option value="audio_processing">音频处理</option>
                                <option value="qa_interaction">QA交互</option>
                                <option value="code_execution">代码执行</option>
                                <option value="file_operation">文件操作</option>
                                <option value="notification">通知发送</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label>节点描述</label>
                            <textarea id="node-description" class="form-input" rows="3" placeholder="可选：描述节点的用途"></textarea>
                        </div>
                    </div>
                    
                    <div class="tab-content" id="tab-function">
                        <div id="function-config" class="function-config">
                            <p class="config-hint">请先选择节点类型以加载配置项</p>
                        </div>
                    </div>
                    
                    <div class="tab-content" id="tab-module">
                        <div class="module-association">
                            <h4>关联现有模块</h4>
                            <p class="config-hint">选择要关联的项目模块，自动加载可用模型和服务</p>
                            
                            <div class="form-group">
                                <label>选择模块</label>
                                <select id="module-select" class="form-input">
                                    <option value="">请选择模块</option>
                                    <option value="customer">客户管理</option>
                                    <option value="contract">合同管理</option>
                                    <option value="finance">财务管理</option>
                                    <option value="project">项目管理</option>
                                    <option value="approval">审批流程</option>
                                    <option value="message">消息通知</option>
                                    <option value="user">用户管理</option>
                                    <option value="common">公共模块</option>
                                </select>
                            </div>
                            
                            <div id="module-models" class="module-section" style="display:none">
                                <h5>可用数据模型</h5>
                                <div id="models-list" class="model-list"></div>
                            </div>
                            
                            <div id="module-services" class="module-section" style="display:none">
                                <h5>可用服务</h5>
                                <div id="services-list" class="service-list"></div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="tab-content" id="tab-advanced">
                        <div class="form-group">
                            <label>错误处理</label>
                            <select id="error-handling" class="form-input">
                                <option value="retry">重试</option>
                                <option value="fallback">降级</option>
                                <option value="error">报错</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label>执行超时(秒)</label>
                            <input type="number" id="timeout" class="form-input" value="30" min="1" max="300">
                        </div>
                        <div class="form-group">
                            <label>
                                <input type="checkbox" id="enable-logging"> 启用日志记录
                            </label>
                        </div>
                        <div class="form-group">
                            <label>自定义CSS类</label>
                            <input type="text" id="custom-css" class="form-input" placeholder="可选：自定义样式类名">
                        </div>
                    </div>
                </div>
                
                <div class="config-footer">
                    <button class="btn btn-secondary" onclick="this.reset()">重置</button>
                    <button class="btn btn-primary" onclick="this.save()">保存配置</button>
                </div>
            </div>
        `;
        
        this.addStyles();
    }
    
    addStyles() {
        if (document.getElementById('node-config-styles')) return;
        
        const styles = `
            .node-config-panel {
                width: 400px;
                background: #fff;
                border-radius: 8px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.15);
                overflow: hidden;
                font-size: 14px;
            }
            
            .config-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 16px 20px;
                border-bottom: 1px solid #e8e8e8;
                background: #fafafa;
            }
            
            .config-header h3 {
                margin: 0;
                font-size: 16px;
                color: #262626;
            }
            
            .close-btn {
                background: none;
                border: none;
                font-size: 24px;
                cursor: pointer;
                color: #8c8c8c;
                padding: 0;
                line-height: 1;
            }
            
            .close-btn:hover {
                color: #262626;
            }
            
            .config-tabs {
                display: flex;
                border-bottom: 1px solid #e8e8e8;
                background: #f5f5f5;
            }
            
            .tab-btn {
                flex: 1;
                padding: 12px 16px;
                border: none;
                background: none;
                cursor: pointer;
                font-size: 13px;
                color: #666;
                border-bottom: 2px solid transparent;
                transition: all 0.2s;
            }
            
            .tab-btn:hover {
                color: #1890ff;
            }
            
            .tab-btn.active {
                color: #1890ff;
                border-bottom-color: #1890ff;
                background: #fff;
            }
            
            .config-content {
                padding: 20px;
                max-height: 400px;
                overflow-y: auto;
            }
            
            .tab-content {
                display: none;
            }
            
            .tab-content.active {
                display: block;
            }
            
            .form-group {
                margin-bottom: 16px;
            }
            
            .form-group label {
                display: block;
                margin-bottom: 6px;
                font-size: 13px;
                color: #595959;
                font-weight: 500;
            }
            
            .required {
                color: #ff4d4f;
            }
            
            .form-input {
                width: 100%;
                padding: 8px 12px;
                border: 1px solid #d9d9d9;
                border-radius: 4px;
                font-size: 14px;
                transition: border-color 0.2s;
            }
            
            .form-input:focus {
                border-color: #1890ff;
                outline: none;
                box-shadow: 0 0 0 2px rgba(24,144,255,0.1);
            }
            
            .form-input:disabled {
                background: #f5f5f5;
                cursor: not-allowed;
            }
            
            textarea.form-input {
                resize: vertical;
                min-height: 80px;
            }
            
            .config-hint {
                color: #8c8c8c;
                font-size: 12px;
                margin: 8px 0;
            }
            
            .function-config .config-field {
                margin-bottom: 20px;
                padding: 16px;
                background: #fafafa;
                border-radius: 6px;
                border: 1px solid #f0f0f0;
            }
            
            .config-field label {
                display: flex;
                align-items: center;
                gap: 8px;
                margin-bottom: 8px;
            }
            
            .field-tooltip {
                color: #8c8c8c;
                cursor: help;
                font-size: 14px;
            }
            
            .field-description {
                font-size: 12px;
                color: #8c8c8c;
                margin-top: 4px;
            }
            
            .nested-config {
                margin-top: 12px;
                padding: 12px;
                background: #fff;
                border-radius: 4px;
                border: 1px dashed #d9d9d9;
            }
            
            .module-association h4 {
                margin: 0 0 8px 0;
                font-size: 14px;
            }
            
            .module-section {
                margin-top: 16px;
                padding: 12px;
                background: #fafafa;
                border-radius: 6px;
            }
            
            .module-section h5 {
                margin: 0 0 12px 0;
                font-size: 13px;
                color: #595959;
            }
            
            .model-item, .service-item {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 8px 12px;
                background: #fff;
                border: 1px solid #e8e8e8;
                border-radius: 4px;
                margin-bottom: 8px;
                cursor: pointer;
                transition: all 0.2s;
            }
            
            .model-item:hover, .service-item:hover {
                border-color: #1890ff;
                background: #e6f7ff;
            }
            
            .model-item.selected, .service-item.selected {
                border-color: #1890ff;
                background: #e6f7ff;
            }
            
            .config-footer {
                display: flex;
                justify-content: flex-end;
                gap: 12px;
                padding: 16px 20px;
                border-top: 1px solid #e8e8e8;
                background: #fafafa;
            }
            
            .btn {
                padding: 8px 20px;
                border-radius: 4px;
                font-size: 14px;
                cursor: pointer;
                transition: all 0.2s;
            }
            
            .btn-secondary {
                background: #fff;
                border: 1px solid #d9d9d9;
                color: #595959;
            }
            
            .btn-secondary:hover {
                border-color: #1890ff;
                color: #1890ff;
            }
            
            .btn-primary {
                background: #1890ff;
                border: 1px solid #1890ff;
                color: #fff;
            }
            
            .btn-primary:hover {
                background: #40a9ff;
                border-color: #40a9ff;
            }
            
            .variable-picker {
                display: inline-flex;
                align-items: center;
                gap: 4px;
                padding: 2px 8px;
                background: #e6f7ff;
                border: 1px solid #91d5ff;
                border-radius: 4px;
                font-size: 12px;
                color: #1890ff;
                cursor: pointer;
            }
            
            .condition-row {
                display: flex;
                gap: 8px;
                align-items: center;
                margin-bottom: 8px;
            }
            
            .condition-row select, .condition-row input {
                flex: 1;
            }
            
            .add-condition-btn {
                color: #1890ff;
                background: none;
                border: none;
                cursor: pointer;
                font-size: 13px;
            }
        `;
        
        const styleSheet = document.createElement('style');
        styleSheet.id = 'node-config-styles';
        styleSheet.textContent = styles;
        document.head.appendChild(styleSheet);
    }
    
    bindEvents() {
        // Tab switching
        this.container.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', (e) => this.switchTab(e.target.dataset.tab));
        });
        
        // Module selection
        const moduleSelect = this.container.querySelector('#module-select');
        if (moduleSelect) {
            moduleSelect.addEventListener('change', (e) => this.loadModuleInfo(e.target.value));
        }
    }
    
    switchTab(tabId) {
        this.container.querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.tab === tabId);
        });
        this.container.querySelectorAll('.tab-content').forEach(content => {
            content.classList.toggle('active', content.id === `tab-${tabId}`);
        });
    }
    
    setNodeType(nodeType) {
        this.currentNodeType = nodeType;
        this.container.querySelector('#node-type').value = nodeType;
        this.renderFunctionConfig(nodeType);
    }
    
    renderFunctionConfig(nodeType) {
        const container = this.container.querySelector('#function-config');
        
        // Fetch schema from server
        fetch(`/api/workflow/nodes/${nodeType}/schema/`)
            .then(response => response.json())
            .then(schema => {
                this.renderSchemaFields(schema, container);
            })
            .catch(() => {
                container.innerHTML = '<p class="config-hint">无法加载配置项</p>';
            });
    }
    
    renderSchemaFields(schema, container, prefix = '') {
        if (!schema || Object.keys(schema).length === 0) {
            container.innerHTML = '<p class="config-hint">此节点类型无需额外配置</p>';
            return;
        }
        
        let html = '';
        
        for (const [fieldName, fieldSchema] of Object.entries(schema)) {
            const fullName = prefix ? `${prefix}.${fieldName}` : fieldName;
            const fieldId = `config-${fullName.replace(/\./g, '-')}`;
            
            if (fieldSchema.type === 'object' && fieldSchema.properties) {
                html += `
                    <div class="config-field" id="field-${fieldId}">
                        <label>${fieldSchema.label || fieldName}</label>
                        <div class="nested-config" id="nested-${fieldId}"></div>
                    </div>
                `;
                
                // Render nested fields after a small delay
                setTimeout(() => {
                    const nestedContainer = document.getElementById(`nested-${fieldId}`);
                    if (nestedContainer) {
                        this.renderSchemaFields(fieldSchema.properties, nestedContainer, fullName);
                    }
                }, 0);
            } else {
                html += this.renderField(fieldId, fieldName, fieldSchema, fullName);
            }
        }
        
        container.innerHTML = html;
        
        // Add event listeners for dynamically created fields
        this.bindFieldEvents(container);
    }
    
    renderField(fieldId, fieldName, fieldSchema, fullName) {
        let inputHtml = '';
        const tooltip = fieldSchema.description ? `<span class="field-tooltip" title="${fieldSchema.description}">?</span>` : '';
        const desc = fieldSchema.description ? `<div class="field-description">${fieldSchema.description}</div>` : '';
        const defaultValue = fieldSchema.default !== undefined ? `data-default="${fieldSchema.default}"` : '';
        
        switch (fieldSchema.type) {
            case 'select':
                const options = fieldSchema.options.map(opt => 
                    `<option value="${opt.value}">${opt.label}</option>`
                ).join('');
                inputHtml = `<select id="${fieldId}" name="${fullName}" class="form-input" ${defaultValue}>${options}</select>`;
                break;
                
            case 'number':
                const minAttr = fieldSchema.min_value !== undefined ? `min="${fieldSchema.min_value}"` : '';
                const maxAttr = fieldSchema.max_value !== undefined ? `max="${fieldSchema.max_value}"` : '';
                inputHtml = `<input type="number" id="${fieldId}" name="${fullName}" class="form-input" ${minAttr} ${maxAttr} ${defaultValue}>`;
                break;
                
            case 'boolean':
                inputHtml = `<input type="checkbox" id="${fieldId}" name="${fullName}" ${defaultValue}>`;
                break;
                
            case 'array':
                inputHtml = `
                    <div id="${fieldId}-container">
                        <button type="button" class="add-condition-btn" data-field="${fullName}">+ 添加项</button>
                    </div>
                `;
                break;
                
            case 'text':
                const rows = fieldSchema.rows || 4;
                inputHtml = `<textarea id="${fieldId}" name="${fullName}" class="form-input" rows="${rows}" ${defaultValue}></textarea>`;
                break;
                
            default:
                inputHtml = `<input type="text" id="${fieldId}" name="${fullName}" class="form-input" placeholder="${fieldSchema.placeholder || ''}" ${defaultValue}>`;
        }
        
        if (this.options.showVariablePicker && ['text'].includes(fieldSchema.type)) {
            inputHtml += `<span class="variable-picker" onclick="showVariablePicker('${fieldId}')">插入变量</span>`;
        }
        
        return `
            <div class="config-field" id="field-${fieldId}">
                <label for="${fieldId}">${fieldSchema.label || fieldName} ${tooltip}</label>
                ${inputHtml}
                ${desc}
            </div>
        `;
    }
    
    bindFieldEvents(container) {
        // Add array item buttons
        container.querySelectorAll('.add-condition-btn').forEach(btn => {
            btn.addEventListener('click', (e) => this.addArrayItem(e.target));
        });
        
        // Add select change handlers for dependent fields
        container.querySelectorAll('select[data-depends-on]').forEach(select => {
            select.addEventListener('change', (e) => this.handleDependencyChange(e.target));
        });
    }
    
    addArrayItem(button) {
        const fieldName = button.dataset.field;
        const container = document.getElementById(`${button.closest('.config-field').id}-container`);
        
        const itemHtml = `
            <div class="condition-row">
                <input type="text" name="${fieldName}[]" class="form-input" placeholder="输入值">
                <button type="button" class="add-condition-btn" onclick="this.parentElement.remove()">删除</button>
            </div>
        `;
        
        container.insertAdjacentHTML('beforeend', itemHtml);
    }
    
    handleDependencyChange(select) {
        const dependsOn = JSON.parse(select.dataset.dependsOn || '{}');
        const selectedValue = select.value;
        
        // Show/hide dependent fields
        for (const [field, values] of Object.entries(dependsOn)) {
            const fieldElement = document.getElementById(`field-config-${field.replace(/\./g, '-')}`);
            if (fieldElement) {
                const shouldShow = values.includes(selectedValue);
                fieldElement.style.display = shouldShow ? 'block' : 'none';
            }
        }
    }
    
    loadModuleInfo(moduleName) {
        if (!moduleName) {
            this.container.querySelector('#module-models').style.display = 'none';
            this.container.querySelector('#module-services').style.display = 'none';
            return;
        }
        
        fetch(`/api/modules/${moduleName}/`)
            .then(response => response.json())
            .then(data => {
                // Render models
                const modelsList = this.container.querySelector('#models-list');
                if (data.models && data.models.length > 0) {
                    modelsList.innerHTML = data.models.map(model => `
                        <div class="model-item" data-model="${model.name}" onclick="selectModel(this, '${model.name}')">
                            <span>${model.verbose_name || model.name}</span>
                            <span class="model-fields">${model.fields.length}个字段</span>
                        </div>
                    `).join('');
                    this.container.querySelector('#module-models').style.display = 'block';
                } else {
                    this.container.querySelector('#module-models').style.display = 'none';
                }
                
                // Render services
                const servicesList = this.container.querySelector('#services-list');
                if (data.services && data.services.length > 0) {
                    servicesList.innerHTML = data.services.map(service => `
                        <div class="service-item" data-service="${service.name}" onclick="selectService(this, '${service.name}')">
                            <span>${service.name}</span>
                            <span class="service-badge">服务</span>
                        </div>
                    `).join('');
                    this.container.querySelector('#module-services').style.display = 'block';
                } else {
                    this.container.querySelector('#module-services').style.display = 'none';
                }
            })
            .catch(err => {
                console.error('Failed to load module info:', err);
            });
    }
    
    loadConfig(config) {
        this.currentConfig = config || {};
        
        // Basic info
        if (config.name) {
            this.container.querySelector('#node-name').value = config.name;
        }
        if (config.node_type) {
            this.setNodeType(config.node_type);
        }
        if (config.description) {
            this.container.querySelector('#node-description').value = config.description;
        }
        
        // Function config
        if (config.config) {
            for (const [key, value] of Object.entries(config.config)) {
                const field = this.container.querySelector(`[name="${key}"]`);
                if (field) {
                    if (field.type === 'checkbox') {
                        field.checked = value;
                    } else {
                        field.value = value;
                    }
                }
            }
        }
        
        // Advanced config
        if (config.error_handling) {
            this.container.querySelector('#error-handling').value = config.error_handling;
        }
        if (config.timeout) {
            this.container.querySelector('#timeout').value = config.timeout;
        }
        if (config.enable_logging) {
            this.container.querySelector('#enable-logging').checked = true;
        }
        if (config.custom_css) {
            this.container.querySelector('#custom-css').value = config.custom_css;
        }
    }
    
    getConfig() {
        const config = {
            name: this.container.querySelector('#node-name').value.trim(),
            node_type: this.container.querySelector('#node-type').value,
            description: this.container.querySelector('#node-description').value.trim(),
            error_handling: this.container.querySelector('#error-handling').value,
            timeout: parseInt(this.container.querySelector('#timeout').value) || 30,
            enable_logging: this.container.querySelector('#enable-logging').checked,
            custom_css: this.container.querySelector('#custom-css').value.trim(),
            config: {}
        };
        
        // Collect function config
        this.container.querySelectorAll('[name]').forEach(field => {
            const name = field.name;
            if (name && !['node-name', 'node-type', 'node-description', 'error-handling', 'timeout', 'custom-css'].includes(name)) {
                let value = field.value;
                if (field.type === 'checkbox') {
                    value = field.checked;
                } else if (field.type === 'number') {
                    value = parseFloat(value);
                }
                
                // Handle nested names (e.g., "api.url")
                this.setNestedValue(config.config, name, value);
            }
        });
        
        return config;
    }
    
    setNestedValue(obj, path, value) {
        const keys = path.split('.');
        let current = obj;
        
        for (let i = 0; i < keys.length - 1; i++) {
            const key = keys[i];
            if (!(key in current)) {
                current[key] = {};
            }
            current = current[key];
        }
        
        current[keys[keys.length - 1]] = value;
    }
    
    reset() {
        this.loadConfig({});
    }
    
    save() {
        const config = this.getConfig();
        
        // Validation
        if (!config.name) {
            alert('请输入节点名称');
            return;
        }
        if (!config.node_type) {
            alert('请选择节点类型');
            return;
        }
        
        // Emit save event
        if (typeof this.options.onSave === 'function') {
            this.options.onSave(config);
        }
        
        this.close();
    }
    
    close() {
        if (typeof this.options.onClose === 'function') {
            this.options.onClose();
        }
        this.container.remove();
    }
}

// Global function for variable picker
function showVariablePicker(targetId) {
    const variables = window.availableVariables || ['input_data', 'output_data', 'result'];
    const menu = document.createElement('div');
    menu.className = 'variable-picker-menu';
    menu.innerHTML = `
        <div class="picker-header">选择变量</div>
        <div class="picker-list">
            ${variables.map(v => `<div class="picker-item" onclick="insertVariable('${targetId}', '${v}')">${v}</div>`).join('')}
        </div>
    `;
    
    document.body.appendChild(menu);
    
    const rect = document.getElementById(targetId).getBoundingClientRect();
    menu.style.left = rect.left + 'px';
    menu.style.top = (rect.bottom + 4) + 'px';
    
    document.addEventListener('click', function handler(e) {
        if (!menu.contains(e.target)) {
            menu.remove();
            document.removeEventListener('click', handler);
        }
    });
}

function insertVariable(targetId, variable) {
    const field = document.getElementById(targetId);
    field.value += '${' + variable + '}';
    field.dispatchEvent(new Event('input'));
}

// Global function for model selection
function selectModel(element, modelName) {
    element.classList.toggle('selected');
    const selectedModels = Array.from(document.querySelectorAll('.model-item.selected'))
        .map(el => el.dataset.model);
    
    window.selectedModuleModels = selectedModels;
}

function selectService(element, serviceName) {
    element.classList.toggle('selected');
    const selectedServices = Array.from(document.querySelectorAll('.service-item.selected'))
        .map(el => el.dataset.service);
    
    window.selectedModuleServices = selectedServices;
}

// Export for use
window.NodeConfigPanel = NodeConfigPanel;

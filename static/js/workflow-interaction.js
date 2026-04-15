/**
 * 工作流交互管理模块
 * 处理工作流执行过程中的用户交互
 */

class WorkflowInteractionManager {
    constructor(options = {}) {
        this.baseUrl = options.baseUrl || '/ai/workflow';
        this.csrfToken = options.csrfToken || '';
        this.currentInteraction = null;
        this.pendingInteractions = [];
        this.notificationSource = null;
        this.isPolling = false;
        
        this.init();
    }
    
    init() {
        this.loadPendingInteractions();
        this.startNotificationListener();
    }
    
    async loadPendingInteractions() {
        try {
            const response = await fetch(`${this.baseUrl}/interaction/pending/`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            const data = await response.json();
            if (data.success) {
                this.pendingInteractions = data.data;
                this.updatePendingCount();
            }
        } catch (error) {
            console.error('加载待处理交互失败:', error);
        }
    }
    
    startNotificationListener() {
        if (this.notificationSource) {
            this.notificationSource.close();
        }
        
        try {
            this.notificationSource = new EventSource(`${this.baseUrl}/interaction/notifications/`);
            
            this.notificationSource.onmessage = (event) => {
                const data = JSON.parse(event.data);
                if (data.type === 'new_interaction') {
                    this.loadPendingInteractions();
                    this.showNotification('新的交互请求', '您有新的待处理交互');
                }
            };
            
            this.notificationSource.onerror = () => {
                console.log('SSE连接断开，切换到轮询模式');
                this.isPolling = true;
                this.startPolling();
            };
        } catch (error) {
            console.log('SSE不可用，启用轮询模式');
            this.isPolling = true;
            this.startPolling();
        }
    }
    
    startPolling() {
        if (this.pollingInterval) {
            clearInterval(this.pollingInterval);
        }
        
        this.pollingInterval = setInterval(() => {
            if (this.isPolling) {
                this.loadPendingInteractions();
            }
        }, 10000);
    }
    
    updatePendingCount() {
        const badge = document.getElementById('pending-interaction-count');
        if (badge) {
            badge.textContent = this.pendingInteractions.length;
            badge.style.display = this.pendingInteractions.length > 0 ? 'inline' : 'none';
        }
    }
    
    showNotification(title, body) {
        if (Notification.permission === 'granted') {
            new Notification(title, { body });
        } else if (Notification.permission !== 'denied') {
            Notification.requestPermission();
        }
    }
    
    async getInteraction(interactionId) {
        try {
            const response = await fetch(`${this.baseUrl}/interaction/${interactionId}/`, {
                method: 'GET',
                headers: { 'Content-Type': 'application/json' }
            });
            
            const data = await response.json();
            return data.success ? data.data : null;
        } catch (error) {
            console.error('获取交互详情失败:', error);
            return null;
        }
    }
    
    async getInteractionSchema(interactionId) {
        try {
            const response = await fetch(`${this.baseUrl}/interaction/${interactionId}/schema/`, {
                method: 'GET',
                headers: { 'Content-Type': 'application/json' }
            });
            
            const data = await response.json();
            return data.success ? data.data : null;
        } catch (error) {
            console.error('获取交互Schema失败:', error);
            return null;
        }
    }
    
    async completeInteraction(interactionId, inputData, result = null, comment = '') {
        try {
            const response = await fetch(`${this.baseUrl}/interaction/${interactionId}/complete/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrfToken
                },
                body: JSON.stringify({
                    input_data: inputData,
                    result: result,
                    comment: comment
                })
            });
            
            const data = await response.json();
            if (data.success) {
                this.loadPendingInteractions();
                return { success: true, data: data.data };
            } else {
                return { success: false, error: data.error };
            }
        } catch (error) {
            console.error('完成交互失败:', error);
            return { success: false, error: error.message };
        }
    }
    
    async cancelInteraction(interactionId, reason = '') {
        try {
            const response = await fetch(`${this.baseUrl}/interaction/${interactionId}/cancel/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrfToken
                },
                body: JSON.stringify({ reason })
            });
            
            const data = await response.json();
            if (data.success) {
                this.loadPendingInteractions();
                return { success: true };
            } else {
                return { success: false, error: data.error };
            }
        } catch (error) {
            console.error('取消交互失败:', error);
            return { success: false, error: error.message };
        }
    }
    
    showInteractionDialog(interaction) {
        const dialogId = `interaction-dialog-${interaction.id}`;
        
        if (document.getElementById(dialogId)) {
            return;
        }
        
        const dialog = document.createElement('div');
        dialog.id = dialogId;
        dialog.className = 'workflow-interaction-dialog';
        dialog.innerHTML = this.generateInteractionDialogHTML(interaction);
        
        document.body.appendChild(dialog);
        
        this.bindInteractionDialogEvents(dialog, interaction);
        
        layui.layer.open({
            type: 1,
            title: interaction.title,
            area: ['80%', '100%'],
            content: dialog,
            maxmin: true,
            resize: true
        });
    }
    
    generateInteractionDialogHTML(interaction) {
        const schema = interaction.input_schema || {};
        const fields = schema.properties || {};
        const required = schema.required || [];
        
        let formHTML = '';
        
        for (const [fieldName, fieldConfig] of Object.entries(fields)) {
            const isRequired = required.includes(fieldName);
            const label = fieldConfig.label || fieldName;
            const placeholder = fieldConfig.placeholder || '';
            const defaultValue = fieldConfig.default || '';
            const options = fieldConfig.options || [];
            
            let inputHTML = '';
            
            switch (fieldConfig.type) {
                case 'string':
                    if (options.length > 0) {
                        inputHTML = this.generateSelectHTML(fieldName, options, defaultValue);
                    } else {
                        inputHTML = `<input type="text" name="${fieldName}" class="layui-input" 
                            placeholder="${placeholder}" value="${defaultValue}" ${isRequired ? 'required' : ''}>`;
                    }
                    break;
                    
                case 'textarea':
                    inputHTML = `<textarea name="${fieldName}" class="layui-textarea" 
                        placeholder="${placeholder}" ${isRequired ? 'required' : ''}>${defaultValue}</textarea>`;
                    break;
                    
                case 'number':
                    inputHTML = `<input type="number" name="${fieldName}" class="layui-input" 
                        placeholder="${placeholder}" value="${defaultValue}" 
                        min="${fieldConfig.minimum || ''}" max="${fieldConfig.maximum || ''}"
                        ${isRequired ? 'required' : ''}>`;
                    break;
                    
                case 'boolean':
                    inputHTML = `
                        <input type="radio" name="${fieldName}" value="true" title="是" ${defaultValue === true ? 'checked' : ''}>
                        <input type="radio" name="${fieldName}" value="false" title="否" ${defaultValue === false ? 'checked' : ''}>
                    `;
                    break;
                    
                case 'select':
                    inputHTML = this.generateSelectHTML(fieldName, options, defaultValue);
                    break;
                    
                case 'array':
                    inputHTML = this.generateCheckboxGroupHTML(fieldName, options, defaultValue);
                    break;
                    
                default:
                    inputHTML = `<input type="text" name="${fieldName}" class="layui-input" 
                        placeholder="${placeholder}" value="${defaultValue}">`;
            }
            
            formHTML += `
                <div class="layui-form-item">
                    <label class="layui-form-label">${label}${isRequired ? '<span class="required">*</span>' : ''}</label>
                    <div class="layui-input-block">${inputHTML}</div>
                </div>
            `;
        }
        
        return `
            <div class="interaction-form">
                ${interaction.description ? `<div class="interaction-description">${interaction.description}</div>` : ''}
                <form class="layui-form" lay-filter="interaction-form">
                    ${formHTML}
                    <div class="layui-form-item">
                        <label class="layui-form-label">备注</label>
                        <div class="layui-input-block">
                            <textarea name="comment" class="layui-textarea" placeholder="请输入备注（可选）"></textarea>
                        </div>
                    </div>
                </form>
            </div>
        `;
    }
    
    generateSelectHTML(fieldName, options, defaultValue) {
        const optionsHTML = options.map(opt => {
            const value = opt.value || opt;
            const label = opt.label || opt;
            const selected = String(value) === String(defaultValue) ? 'selected' : '';
            return `<option value="${value}" ${selected}>${label}</option>`;
        }).join('');
        
        return `
            <select name="${fieldName}" lay-search>
                ${optionsHTML}
            </select>
        `;
    }
    
    generateCheckboxGroupHTML(fieldName, options, defaultValue) {
        const defaultValues = Array.isArray(defaultValue) ? defaultValue : [];
        
        const checkboxesHTML = options.map(opt => {
            const value = opt.value || opt;
            const label = opt.label || opt;
            const checked = defaultValues.includes(value) ? 'checked' : '';
            return `
                <input type="checkbox" name="${fieldName}" value="${value}" title="${label}" ${checked}>
            `;
        }).join('');
        
        return checkboxesHTML;
    }
    
    bindInteractionDialogEvents(dialog, interaction) {
        const form = dialog.querySelector('form');
        
        layui.form.render();
        
        const submitBtn = dialog.querySelector('.submit-btn');
        const cancelBtn = dialog.querySelector('.cancel-btn');
        
        if (submitBtn) {
            submitBtn.addEventListener('click', async () => {
                const formData = new FormData(form);
                const inputData = {};
                
                for (const [key, value] of formData.entries()) {
                    if (inputData[key]) {
                        if (!Array.isArray(inputData[key])) {
                            inputData[key] = [inputData[key]];
                        }
                        inputData[key].push(value);
                    } else {
                        inputData[key] = value;
                    }
                }
                
                const comment = formData.get('comment') || '';
                
                const result = await this.completeInteraction(
                    interaction.id,
                    inputData,
                    null,
                    comment
                );
                
                if (result.success) {
                    layui.layer.closeAll();
                    layui.layer.msg('操作成功', { icon: 1 });
                    this.loadPendingInteractions();
                } else {
                    layui.layer.msg(result.error || '操作失败', { icon: 2 });
                }
            });
        }
        
        if (cancelBtn) {
            cancelBtn.addEventListener('click', async () => {
                layui.layer.confirm('确定要取消此操作吗？', {
                    title: '确认取消'
                }, async (index) => {
                    layui.layer.close(index);
                    const result = await this.cancelInteraction(interaction.id, '用户取消');
                    if (result.success) {
                        layui.layer.closeAll();
                        layui.layer.msg('已取消', { icon: 1 });
                    } else {
                        layui.layer.msg(result.error || '取消失败', { icon: 2 });
                    }
                });
            });
        }
    }
    
    showPendingInteractionsPanel() {
        const panelId = 'pending-interactions-panel';
        
        if (document.getElementById(panelId)) {
            return;
        }
        
        const panel = document.createElement('div');
        panel.id = panelId;
        panel.className = 'pending-interactions-panel';
        panel.innerHTML = this.generatePendingPanelHTML();
        
        document.body.appendChild(panel);
        
        this.bindPendingPanelEvents(panel);
        
        layui.layer.open({
            type: 1,
            title: '待处理交互',
            area: ['80%', '100%'],
            content: panel,
            shade: 0.3,
            maxmin: true
        });
    }
    
    generatePendingPanelHTML() {
        if (this.pendingInteractions.length === 0) {
            return `
                <div class="empty-state">
                    <i class="layui-icon layui-icon-ok-circle" style="font-size: 48px; color: #52c41a;"></i>
                    <p>暂无待处理的交互</p>
                </div>
            `;
        }
        
        const itemsHTML = this.pendingInteractions.map(interaction => {
            const typeLabels = {
                'approval': '审批',
                'input': '输入',
                'confirmation': '确认',
                'selection': '选择',
                'review': '审核',
                'feedback': '反馈'
            };
            
            const typeLabel = typeLabels[interaction.type] || '交互';
            const priorityClass = interaction.priority === 'urgent' ? 'priority-urgent' : 
                                 interaction.priority === 'high' ? 'priority-high' : '';
            
            return `
                <div class="interaction-item ${priorityClass}" data-id="${interaction.id}">
                    <div class="interaction-header">
                        <span class="interaction-type">${typeLabel}</span>
                        <span class="interaction-time">${this.formatTime(interaction.created_at)}</span>
                    </div>
                    <div class="interaction-title">${interaction.title}</div>
                    <div class="interaction-actions">
                        <button class="layui-btn layui-btn-sm handle-btn">处理</button>
                    </div>
                </div>
            `;
        }).join('');
        
        return `
            <div class="pending-interactions-list">
                ${itemsHTML}
            </div>
        `;
    }
    
    bindPendingPanelEvents(panel) {
        const items = panel.querySelectorAll('.interaction-item');
        
        items.forEach(item => {
            const handleBtn = item.querySelector('.handle-btn');
            
            if (handleBtn) {
                handleBtn.addEventListener('click', async () => {
                    const interactionId = item.dataset.id;
                    const interaction = this.pendingInteractions.find(i => i.id === interactionId);
                    
                    if (interaction) {
                        this.showInteractionDialog(interaction);
                    }
                });
            }
            
            item.addEventListener('click', async () => {
                const interactionId = item.dataset.id;
                const interaction = this.pendingInteractions.find(i => i.id === interactionId);
                
                if (interaction) {
                    this.showInteractionDialog(interaction);
                }
            });
        });
    }
    
    formatTime(timeStr) {
        const time = new Date(timeStr);
        const now = new Date();
        const diff = (now - time) / 1000;
        
        if (diff < 60) return '刚刚';
        if (diff < 3600) return `${Math.floor(diff / 60)}分钟前`;
        if (diff < 86400) return `${Math.floor(diff / 3600)}小时前`;
        return time.toLocaleDateString();
    }
    
    async getExecutionInteractions(executionId) {
        try {
            const response = await fetch(`${this.baseUrl}/execution/${executionId}/interactions/`, {
                method: 'GET',
                headers: { 'Content-Type': 'application/json' }
            });
            
            const data = await response.json();
            return data.success ? data.data : [];
        } catch (error) {
            console.error('获取执行交互列表失败:', error);
            return [];
        }
    }
    
    destroy() {
        if (this.notificationSource) {
            this.notificationSource.close();
        }
        if (this.pollingInterval) {
            clearInterval(this.pollingInterval);
        }
        this.isPolling = false;
    }
}


class WorkflowInteractionFormBuilder {
    constructor(container, options = {}) {
        this.container = container;
        this.options = options;
        this.formData = {};
    }
    
    build(schema) {
        this.container.innerHTML = '';
        this.formData = {};
        
        if (!schema || !schema.properties) {
            return;
        }
        
        const fields = schema.properties;
        const required = schema.required || [];
        
        for (const [fieldName, fieldConfig] of Object.entries(fields)) {
            const fieldElement = this.createField(fieldName, fieldConfig, required.includes(fieldName));
            this.container.appendChild(fieldElement);
        }
        
        layui.form.render();
    }
    
    createField(fieldName, fieldConfig, isRequired) {
        const wrapper = document.createElement('div');
        wrapper.className = 'layui-form-item';
        
        const label = document.createElement('label');
        label.className = 'layui-form-label';
        label.innerHTML = `${fieldConfig.label || fieldName}${isRequired ? '<span class="required">*</span>' : ''}`;
        
        const inputWrapper = document.createElement('div');
        inputWrapper.className = 'layui-input-block';
        
        const inputElement = this.createInput(fieldName, fieldConfig);
        inputWrapper.appendChild(inputElement);
        
        wrapper.appendChild(label);
        wrapper.appendChild(inputWrapper);
        
        return wrapper;
    }
    
    createInput(fieldName, fieldConfig) {
        const type = fieldConfig.type;
        const placeholder = fieldConfig.placeholder || '';
        const defaultValue = fieldConfig.default || '';
        const options = fieldConfig.options || [];
        
        switch (type) {
            case 'string':
                if (options.length > 0) {
                    return this.createSelect(fieldName, options, defaultValue);
                }
                return this.createTextInput(fieldName, placeholder, defaultValue);
                
            case 'textarea':
                return this.createTextarea(fieldName, placeholder, defaultValue);
                
            case 'number':
                return this.createNumberInput(fieldName, placeholder, defaultValue, fieldConfig);
                
            case 'boolean':
                return this.createRadioGroup(fieldName, defaultValue);
                
            case 'select':
                return this.createSelect(fieldName, options, defaultValue);
                
            case 'array':
                return this.createCheckboxGroup(fieldName, options, defaultValue);
                
            default:
                return this.createTextInput(fieldName, placeholder, defaultValue);
        }
    }
    
    createTextInput(name, placeholder, value) {
        const input = document.createElement('input');
        input.type = 'text';
        input.name = name;
        input.className = 'layui-input';
        input.placeholder = placeholder;
        input.value = value;
        return input;
    }
    
    createTextarea(name, placeholder, value) {
        const textarea = document.createElement('textarea');
        textarea.name = name;
        textarea.className = 'layui-textarea';
        textarea.placeholder = placeholder;
        textarea.value = value;
        return textarea;
    }
    
    createNumberInput(name, placeholder, value, config) {
        const input = document.createElement('input');
        input.type = 'number';
        input.name = name;
        input.className = 'layui-input';
        input.placeholder = placeholder;
        input.value = value;
        if (config.minimum !== undefined) input.min = config.minimum;
        if (config.maximum !== undefined) input.max = config.maximum;
        return input;
    }
    
    createRadioGroup(name, defaultValue) {
        const container = document.createElement('div');
        
        const trueOption = document.createElement('input');
        trueOption.type = 'radio';
        trueOption.name = name;
        trueOption.value = 'true';
        trueOption.title = '是';
        if (String(defaultValue) === 'true') trueOption.checked = true;
        
        const falseOption = document.createElement('input');
        falseOption.type = 'radio';
        falseOption.name = name;
        falseOption.value = 'false';
        falseOption.title = '否';
        if (String(defaultValue) === 'false') falseOption.checked = true;
        
        container.appendChild(trueOption);
        container.appendChild(falseOption);
        
        return container;
    }
    
    createSelect(name, options, defaultValue) {
        const select = document.createElement('select');
        select.name = name;
        select.setAttribute('lay-search', '');
        
        const defaultOption = document.createElement('option');
        defaultOption.value = '';
        defaultOption.textContent = '请选择';
        select.appendChild(defaultOption);
        
        options.forEach(opt => {
            const option = document.createElement('option');
            option.value = opt.value || opt;
            option.textContent = opt.label || opt;
            if (String(opt.value || opt) === String(defaultValue)) {
                option.selected = true;
            }
            select.appendChild(option);
        });
        
        return select;
    }
    
    createCheckboxGroup(name, options, defaultValue) {
        const container = document.createElement('div');
        const defaultValues = Array.isArray(defaultValue) ? defaultValue : [];
        
        options.forEach(opt => {
            const value = opt.value || opt;
            const label = opt.label || opt;
            
            const wrapper = document.createElement('div');
            
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.name = name;
            checkbox.value = value;
            checkbox.title = label;
            if (defaultValues.includes(value)) checkbox.checked = true;
            
            wrapper.appendChild(checkbox);
            container.appendChild(wrapper);
        });
        
        return container;
    }
    
    getData() {
        const form = this.container.closest('form');
        if (!form) return {};
        
        const formData = new FormData(form);
        const data = {};
        
        for (const [key, value] of formData.entries()) {
            if (data[key]) {
                if (!Array.isArray(data[key])) {
                    data[key] = [data[key]];
                }
                data[key].push(value);
            } else {
                data[key] = value;
            }
        }
        
        return data;
    }
}


window.WorkflowInteractionManager = WorkflowInteractionManager;
window.WorkflowInteractionFormBuilder = WorkflowInteractionFormBuilder;

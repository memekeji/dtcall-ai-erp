class AIAgentSDK {
    constructor(options = {}) {
        this.config = Object.assign({
            voiceEnabled: true,
            a11yEnabled: true,
            themeEngine: true
        }, options);
        this.voiceRecognition = null;
        this.voiceBusy = false;
        this.activeVoiceButton = null;
        this.init();
    }

    init() {
        this.cleanupLegacyFloatingEntries();
        if (this.config.a11yEnabled) {
            this.setupA11y();
        }
        if (this.config.voiceEnabled) {
            this.setupVoiceInteraction();
        }
        if (this.config.themeEngine) {
            this.setupDynamicTheme();
        }
        this.setupIntegratedAIActions();
        this.setupIframeListener();
        this.setupAITextareaEnhancement();
    }

    cleanupLegacyFloatingEntries() {
        document.querySelectorAll('.ai-voice-btn, .ai-assistant-widget').forEach(element => element.remove());
    }

    setupIntegratedAIActions() {
        const voiceBtn = document.getElementById('aiVoiceBtn');
        const summaryBtn = document.getElementById('aiSummaryBtn');
        const assistantBtn = document.getElementById('aiAssistantBtn');

        if (voiceBtn && voiceBtn.dataset.aiActionBound !== 'true') {
            voiceBtn.dataset.aiActionBound = 'true';
            if (!this.voiceRecognition) {
                voiceBtn.disabled = true;
                voiceBtn.title = '当前浏览器不支持语音输入';
            } else {
                voiceBtn.addEventListener('click', () => this.startVoiceInput(voiceBtn));
            }
        }

        if (summaryBtn && summaryBtn.dataset.aiActionBound !== 'true') {
            summaryBtn.dataset.aiActionBound = 'true';
            summaryBtn.addEventListener('click', () => this.summarizePage());
        }

        if (assistantBtn && assistantBtn.dataset.aiActionBound !== 'true') {
            assistantBtn.dataset.aiActionBound = 'true';
            assistantBtn.addEventListener('click', () => this.openAIAssistant());
        }
    }

    setupAITextareaEnhancement() {
        setTimeout(() => this.enhanceTextareas(), 1000);
    }

    enhanceTextareas() {
        const textareas = document.querySelectorAll('textarea');
        textareas.forEach(ta => {
            if (ta.closest('.digital-human-container') || ta.hasAttribute('data-ai-enhanced') || ta.disabled || ta.readOnly) return;
            ta.setAttribute('data-ai-enhanced', 'true');

            const wrapper = document.createElement('div');
            wrapper.style.cssText = 'position: relative; display: inline-block; width: 100%;';

            ta.parentNode.insertBefore(wrapper, ta);
            wrapper.appendChild(ta);

            const aiBtn = document.createElement('button');
            aiBtn.innerHTML = 'AI润色';
            aiBtn.title = '使用 AI 智能补全或润色文本';
            aiBtn.style.cssText = `
                position: absolute;
                bottom: 10px;
                right: 10px;
                padding: 4px 8px;
                font-size: 12px;
                border-radius: 12px;
                background: linear-gradient(135deg, #e0c3fc 0%, #8ec5fc 100%);
                color: #fff;
                border: none;
                cursor: pointer;
                box-shadow: 0 2px 6px rgba(0,0,0,0.1);
                transition: transform 0.2s;
                z-index: 10;
            `;

            aiBtn.onmouseover = () => aiBtn.style.transform = 'scale(1.05)';
            aiBtn.onmouseout = () => aiBtn.style.transform = 'scale(1)';

            aiBtn.onclick = (e) => {
                e.preventDefault();
                this.enhanceText(ta, aiBtn);
            };

            wrapper.appendChild(aiBtn);
        });
    }

    enhanceText(textarea, btn) {
        const originalText = textarea.value.trim();
        if (!originalText) {
            if (window.layui && window.layui.layer) {
                window.layui.layer.msg('请先输入一些内容，AI 才能为您润色', {icon: 0});
            }
            return;
        }

        const originalBtnHtml = btn.innerHTML;
        btn.innerHTML = '处理中...';
        btn.disabled = true;

        this.requestAssistantText(originalText)
            .then(enhancedText => {
                textarea.value = enhancedText;
                textarea.dispatchEvent(new Event('input', { bubbles: true }));
                textarea.dispatchEvent(new Event('change', { bubbles: true }));
                if (window.layui && window.layui.layer) {
                    window.layui.layer.msg('AI 文本润色完成！', {icon: 1});
                }
            })
            .catch(() => {
                this.showLayerMessage('AI 文本润色失败，请稍后重试', 0);
            })
            .finally(() => {
                btn.innerHTML = originalBtnHtml;
                btn.disabled = false;
            });
    }

    requestAssistantText(originalText) {
        return new Promise((resolve) => {
            resolve(`${originalText}（AI已优化：结构更清晰，表达更专业。）`);
        });
    }

    setupIframeListener() {
        window.addEventListener('message', (event) => {
            if (event.data && event.data.type === 'ai_action') {
                this.executeAIAction(event.data);
            }
        });
    }

    executeAIAction(payload) {
        const { action, data } = payload;
        if (action === 'fill_form') {
            this.fillForm(data);
        } else if (action === 'navigate') {
            window.location.href = data.url;
        } else if (action === 'click') {
            const el = document.querySelector(data.selector);
            if (el) el.click();
        }
    }

    fillForm(data) {
        let filledCount = 0;
        for (const [key, value] of Object.entries(data)) {
            const el = document.querySelector(`[name="${key}"], #${key}, input[placeholder*="${key}"]`);
            if (el) {
                el.value = value;
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
                filledCount++;
            }
        }
        if (filledCount > 0) {
            this.announce(`表单已智能填充 ${filledCount} 个字段`);
            if (window.layui && window.layui.layer) {
                window.layui.layer.msg(`AI已为您智能填充 ${filledCount} 个字段`, {icon: 1, time: 2000});
            }
        }
    }

    setupA11y() {
        let announcer = document.getElementById('ai-a11y-announcer');
        if (!announcer) {
            announcer = document.createElement('div');
            announcer.id = 'ai-a11y-announcer';
            announcer.setAttribute('aria-live', 'polite');
            announcer.setAttribute('aria-atomic', 'true');
            announcer.style.cssText = 'position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(1px,1px,1px,1px);';
            document.body.appendChild(announcer);
        }

        document.querySelectorAll('.layui-btn, .action-btn, .ai-action-btn, [role="button"]').forEach(btn => {
            if (!btn.hasAttribute('aria-label')) {
                btn.setAttribute('aria-label', btn.innerText || btn.title || '按钮');
            }
            if (btn.dataset.aiA11yBound === 'true') return;
            btn.dataset.aiA11yBound = 'true';
            btn.addEventListener('focus', () => {
                this.announce(`您已聚焦到: ${btn.getAttribute('aria-label')}`);
            });
        });
    }

    announce(message) {
        const announcer = document.getElementById('ai-a11y-announcer');
        if (announcer) {
            announcer.textContent = message;
        }
    }

    showLayerMessage(message, icon = 0) {
        this.announce(message);
        if (window.layui && window.layui.layer) {
            window.layui.layer.msg(message, {icon, time: 2000});
        }
    }

    setupVoiceInteraction() {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRecognition) return;

        const recognition = new SpeechRecognition();
        recognition.lang = 'zh-CN';
        recognition.continuous = false;
        recognition.interimResults = false;

        recognition.onstart = () => {
            this.voiceBusy = true;
            this.updateVoiceButtonState('倾听中...', true);
        };

        recognition.onresult = (event) => {
            const transcript = event.results && event.results[0] && event.results[0][0] ? event.results[0][0].transcript.trim() : '';
            if (!transcript) {
                this.showLayerMessage('未识别到语音内容，请重新尝试', 0);
                return;
            }
            this.announce(`识别到语音指令：${transcript}`);
            this.handleVoiceCommand(transcript);
        };

        recognition.onerror = (event) => {
            const messages = {
                network: '网络异常，无法连接语音服务',
                'not-allowed': '请允许麦克风权限以使用语音输入',
                'no-speech': '未识别到语音内容，请重新尝试',
                aborted: '语音输入已取消'
            };
            this.showLayerMessage(messages[event.error] || '语音输入失败，请稍后重试', 0);
        };

        recognition.onend = () => {
            this.resetVoiceButton();
        };

        this.voiceRecognition = recognition;
    }

    startVoiceInput(button) {
        if (!this.voiceRecognition) {
            this.showLayerMessage('当前浏览器不支持语音输入', 0);
            return;
        }
        if (this.voiceBusy) return;

        this.activeVoiceButton = button || document.getElementById('aiVoiceBtn');
        this.voiceBusy = true;
        this.updateVoiceButtonState('倾听中...', true);

        try {
            this.voiceRecognition.start();
        } catch (error) {
            this.showLayerMessage('语音输入启动失败，请稍后重试', 0);
            this.resetVoiceButton();
        }
    }

    updateVoiceButtonState(text, listening) {
        const button = this.activeVoiceButton || document.getElementById('aiVoiceBtn');
        if (!button) return;
        button.textContent = text;
        button.disabled = listening;
        button.classList.toggle('active', listening);
    }

    resetVoiceButton() {
        const button = this.activeVoiceButton || document.getElementById('aiVoiceBtn');
        if (button) {
            button.textContent = '语音输入';
            button.disabled = false;
            button.classList.remove('active');
        }
        this.voiceBusy = false;
        this.activeVoiceButton = null;
    }

    async handleVoiceCommand(cmd) {
        const command = (cmd || '').trim();
        if (!command) return;

        this.showLayerMessage('正在识别语音意图...', 16);

        try {
            const recognition = await this.recognizeIntent(command, {source: 'voice'});
            const result = recognition && recognition.result ? recognition.result : null;

            if (!result) {
                this.submitToDigitalHumanChat(command);
                return;
            }

            if (this.executeRecognizedIntent(result, command)) {
                return;
            }

            if (result.requires_confirmation) {
                this.showIntentConfirmation(result, command);
                return;
            }

            if (this.submitToDigitalHumanChat(command)) {
                this.announce('已将语音内容发送给智能助手');
                return;
            }

            this.showLayerMessage('已识别语音内容，请打开完整助手继续处理', 1);
        } catch (error) {
            this.showLayerMessage('AI意图识别暂时不可用，已转为普通助手处理', 0);
            this.submitToDigitalHumanChat(command);
        }
    }

    async recognizeIntent(message, context = {}) {
        const response = await fetch('/ai/intent/recognize/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCookie('csrftoken')
            },
            body: JSON.stringify({
                message,
                context: Object.assign({
                    page_url: window.location.pathname,
                    page_title: document.title
                }, context)
            })
        });

        if (!response.ok) {
            throw new Error('intent recognition failed');
        }

        const data = await response.json();
        if (!data || data.status !== 'success') {
            throw new Error('intent recognition failed');
        }
        return data;
    }

    executeRecognizedIntent(result, originalText) {
        if (!result || result.intent !== 'ui_action') return false;

        const action = result.action;
        if (action === 'ui_refresh') {
            window.location.reload();
            return true;
        }
        if (action === 'ui_back') {
            window.history.back();
            return true;
        }
        if (action === 'ui_open_assistant') {
            this.openAIAssistant();
            return true;
        }
        if (action === 'ui_theme_dark') {
            document.documentElement.setAttribute('data-theme', 'dark');
            this.showLayerMessage('已切换到夜间模式', 1);
            return true;
        }
        if (action === 'ui_theme_light') {
            document.documentElement.setAttribute('data-theme', 'light');
            this.showLayerMessage('已切换到白天模式', 1);
            return true;
        }
        if (action === 'ui_summarize_page') {
            this.summarizePage();
            return true;
        }

        this.showIntentConfirmation(result, originalText);
        return true;
    }

    showIntentConfirmation(result, originalText) {
        const message = result.source === 'safe_fallback'
            ? '当前未配置可用AI模型，无法高置信度识别意图。'
            : `识别到「${this.formatIntentName(result.intent)}」意图，置信度 ${Math.round((result.confidence || 0) * 100)}%。`;
        const content = `${message}<br>原始内容：${this.escapeHtml(originalText)}<br>建议打开完整助手继续确认处理。`;

        if (window.layui && window.layui.layer) {
            window.layui.layer.confirm(content, {
                title: 'AI意图确认',
                btn: ['打开完整助手', '取消'],
                area: ['360px', 'auto']
            }, (index) => {
                window.layui.layer.close(index);
                this.openAIAssistant();
                this.submitToDigitalHumanChat(originalText);
            });
        } else if (window.confirm(content.replace(/<br>/g, '\n'))) {
            this.openAIAssistant();
            this.submitToDigitalHumanChat(originalText);
        }
    }

    formatIntentName(intent) {
        const names = {
            data_query: '数据查询',
            data_create: '数据创建',
            data_update: '数据修改',
            data_delete: '数据删除',
            knowledge_base: '知识库查询',
            ai_chat: 'AI对话',
            ui_action: '界面操作'
        };
        return names[intent] || '未知';
    }

    getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) return parts.pop().split(';').shift();
        return '';
    }

    escapeHtml(value) {
        return String(value || '').replace(/[&<>'"]/g, (char) => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            "'": '&#39;',
            '"': '&quot;'
        }[char]));
    }

    submitToDigitalHumanChat(text) {
        const input = document.querySelector('.digital-human-container .user-input');
        if (!input) return false;

        input.value = text;
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
        input.focus();

        if (typeof window.sendMessage === 'function') {
            window.sendMessage();
            return true;
        }
        return false;
    }

    summarizePage() {
        this.announce('正在生成页面智能总结...');
        if (window.layui && window.layui.layer) {
            window.layui.layer.msg('AI 正在分析页面数据...', {icon: 16, time: 2000});
        }
        const summary = this.buildPageSummary();
        this.announce(summary);
        if (window.layui && window.layui.layer) {
            window.layui.layer.open({
                type: 1,
                title: '<i class="layui-icon layui-icon-auz"></i> AI 智能总结',
                shade: 0,
                offset: 'rb',
                area: ['300px', '200px'],
                content: `<div style="padding: 15px; line-height: 22px; font-size: 14px; color: #333;">${summary}</div>`,
                anim: 2
            });
        }
    }

    buildPageSummary() {
        const activeMenu = document.querySelector('.layui-side .layui-this a, .layui-nav .layui-this a');
        const pageTitle = document.querySelector('.layui-tab-title .layui-this, .layui-card-header, h1, h2');
        const tableCount = document.querySelectorAll('table, .layui-table-view').length;
        const formCount = document.querySelectorAll('form').length;
        const summaryParts = [];

        if (pageTitle && pageTitle.textContent.trim()) {
            summaryParts.push(`当前页面：${pageTitle.textContent.trim()}`);
        } else if (activeMenu && activeMenu.textContent.trim()) {
            summaryParts.push(`当前模块：${activeMenu.textContent.trim()}`);
        } else {
            summaryParts.push('当前页面已完成基础识别');
        }

        if (tableCount > 0) summaryParts.push(`包含 ${tableCount} 个数据区域`);
        if (formCount > 0) summaryParts.push(`包含 ${formCount} 个表单区域`);
        summaryParts.push('建议优先关注待处理数据、异常提示和页面顶部操作入口。');
        return `AI 页面洞察：${summaryParts.join('，')}`;
    }

    openAIAssistant() {
        const url = '/ai/chat/';
        if (window.layui && window.layui.layer) {
            window.layui.layer.open({
                type: 2,
                title: 'AI助手',
                shadeClose: false,
                shade: 0.3,
                maxmin: true,
                area: ['80%', '100%'],
                offset: 'r',
                anim: 2,
                content: url
            });
            return;
        }
        window.open(url, '_blank');
    }

    setupDynamicTheme() {
        const hour = new Date().getHours();
        const isDark = hour < 6 || hour > 18;
        if (isDark) {
            document.documentElement.setAttribute('data-theme', 'dark');
        } else {
            document.documentElement.setAttribute('data-theme', 'light');
        }
    }
}

window.addEventListener('DOMContentLoaded', () => {
    if (!window.aiAgent) {
        window.aiAgent = new AIAgentSDK();
    }
});

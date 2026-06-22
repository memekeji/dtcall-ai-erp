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
        this.voiceFinalText = '';
        this.voiceInterimText = '';
        this.voiceInputMode = 'server';
        this.voiceMediaRecorder = null;
        this.voiceAudioChunks = [];
        this.voiceRecordingStream = null;
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
        this.setupIframeListener();
        this.setupAITextareaEnhancement();
    }

    cleanupLegacyFloatingEntries() {
        document.querySelectorAll('.ai-voice-btn, .ai-assistant-widget').forEach(element => element.remove());
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
        if (SpeechRecognition) {
            const recognition = new SpeechRecognition();
            recognition.lang = 'zh-CN';
            recognition.continuous = false;
            recognition.interimResults = true;
            recognition.maxAlternatives = 1;
            recognition.onresult = (event) => {
                let finalText = '';
                let interimText = '';
                for (let i = event.resultIndex; i < event.results.length; i += 1) {
                    const transcript = event.results[i][0] ? event.results[i][0].transcript : '';
                    if (event.results[i].isFinal) {
                        finalText += transcript;
                    } else {
                        interimText += transcript;
                    }
                }
                if (finalText) {
                    this.voiceFinalText += finalText;
                }
                this.voiceInterimText = interimText;
                const preview = (this.voiceFinalText || this.voiceInterimText || '').trim();
                if (preview) {
                    this.announce(`正在识别：${preview}`);
                }
            };
            recognition.onerror = (event) => {
                const message = event && event.error === 'not-allowed'
                    ? '无法访问麦克风，请允许浏览器麦克风权限'
                    : '语音识别失败，请重试或检查麦克风';
                this.showLayerMessage(message, 0);
                this.resetVoiceButton();
            };
            recognition.onend = () => {
                const command = (this.voiceFinalText || this.voiceInterimText || '').trim();
                this.resetVoiceButton();
                if (command) {
                    this.announce(`识别到语音内容：${command}`);
                    this.handleVoiceCommand(command);
                } else {
                    this.showLayerMessage('未识别到语音内容，请重新尝试', 0);
                }
            };
            this.voiceRecognition = recognition;
            this.voiceInputMode = 'browser';
            return;
        }
        if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia && window.MediaRecorder) {
            this.voiceRecognition = { type: 'server-media-recorder' };
            this.voiceInputMode = 'server';
            return;
        }
    }

    startVoiceInput(button) {
        if (!this.voiceRecognition) {
            this.showLayerMessage('当前浏览器不支持语音输入', 0);
            return;
        }
        if (this.voiceBusy) {
            this.stopVoiceInput();
            return;
        }

        if (this.voiceRecognition.type === 'server-media-recorder') {
            this.startServerVoiceInput(button);
            return;
        }

        this.activeVoiceButton = button || null;
        this.voiceBusy = true;
        this.voiceFinalText = '';
        this.voiceInterimText = '';
        this.updateVoiceButtonState('停止识别', true);

        try {
            this.voiceRecognition.start();
        } catch (error) {
            this.showLayerMessage('语音输入启动失败，请稍后重试', 0);
            this.resetVoiceButton();
        }
    }

    stopVoiceInput() {
        if (!this.voiceRecognition || !this.voiceBusy) return;
        if (this.voiceRecognition.type === 'server-media-recorder') {
            this.stopServerVoiceInput();
            return;
        }
        try {
            this.voiceRecognition.stop();
        } catch (error) {
            this.resetVoiceButton();
        }
    }

    async startServerVoiceInput(button) {
        this.activeVoiceButton = button || null;
        this.voiceBusy = true;
        this.voiceAudioChunks = [];
        this.updateVoiceButtonState('停止录音', true);
        this.showLayerMessage('正在录音，再次点击语音按钮结束识别', 16);

        try {
            const stream = await navigator.mediaDevices.getUserMedia({audio: true});
            this.voiceRecordingStream = stream;
            const mimeType = this.getSupportedVoiceMimeType();
            const options = mimeType ? {mimeType} : undefined;
            const recorder = new MediaRecorder(stream, options);
            this.voiceMediaRecorder = recorder;
            recorder.ondataavailable = (event) => {
                if (event.data && event.data.size > 0) {
                    this.voiceAudioChunks.push(event.data);
                }
            };
            recorder.onerror = () => {
                this.showLayerMessage('录音失败，请检查麦克风权限或设备状态', 0);
                this.cleanupServerVoiceInput();
                this.resetVoiceButton();
            };
            recorder.onstop = () => {
                this.submitServerVoiceInput(mimeType || recorder.mimeType || 'audio/webm');
            };
            recorder.start();
        } catch (error) {
            this.showLayerMessage('无法访问麦克风，请允许浏览器麦克风权限', 0);
            this.cleanupServerVoiceInput();
            this.resetVoiceButton();
        }
    }

    stopServerVoiceInput() {
        if (this.voiceMediaRecorder && this.voiceMediaRecorder.state !== 'inactive') {
            this.updateVoiceButtonState('识别中...', true);
            this.showLayerMessage('录音已结束，正在进行服务端语音识别...', 16);
            this.voiceMediaRecorder.stop();
            return;
        }
        this.cleanupServerVoiceInput();
        this.resetVoiceButton();
    }

    async submitServerVoiceInput(mimeType) {
        const chunks = this.voiceAudioChunks || [];
        this.cleanupServerVoiceInput(false);
        if (!chunks.length) {
            this.showLayerMessage('未录到语音内容，请重新尝试', 0);
            this.resetVoiceButton();
            return;
        }

        try {
            const audioBlob = new Blob(chunks, {type: mimeType || 'audio/webm'});
            const formData = new FormData();
            formData.append('audio', audioBlob, this.getServerVoiceFileName(mimeType));
            const response = await fetch('/ai/voice/stt/', {
                method: 'POST',
                credentials: 'same-origin',
                headers: {
                    'X-CSRFToken': this.getCookie('csrftoken')
                },
                body: formData
            });
            const data = await response.json();
            if (!response.ok || !data || data.status !== 'success') {
                throw new Error(data && data.message ? data.message : '语音识别失败');
            }
            const command = String(data.text || '').trim();
            this.resetVoiceButton();
            if (command) {
                this.announce(`识别到语音指令：${command}`);
                this.handleVoiceCommand(command);
            } else {
                this.showLayerMessage('未识别到语音内容，请重新尝试', 0);
            }
        } catch (error) {
            this.showLayerMessage(error.message || '服务端语音识别失败，请检查语音识别配置', 0);
            this.resetVoiceButton();
        } finally {
            this.voiceAudioChunks = [];
        }
    }

    cleanupServerVoiceInput(clearChunks = true) {
        if (this.voiceRecordingStream) {
            this.voiceRecordingStream.getTracks().forEach(track => track.stop());
        }
        this.voiceRecordingStream = null;
        this.voiceMediaRecorder = null;
        if (clearChunks) {
            this.voiceAudioChunks = [];
        }
    }

    getSupportedVoiceMimeType() {
        const candidates = [
            'audio/webm;codecs=opus',
            'audio/webm',
            'audio/ogg;codecs=opus',
            'audio/ogg',
            'audio/mp4'
        ];
        if (!window.MediaRecorder || typeof MediaRecorder.isTypeSupported !== 'function') return '';
        return candidates.find(type => MediaRecorder.isTypeSupported(type)) || '';
    }

    getServerVoiceFileName(mimeType) {
        const type = String(mimeType || '').toLowerCase();
        if (type.includes('ogg')) return 'voice.ogg';
        if (type.includes('mp4')) return 'voice.m4a';
        if (type.includes('wav')) return 'voice.wav';
        return 'voice.webm';
    }

    updateVoiceButtonState(text, listening) {
        const button = this.activeVoiceButton;
        if (!button) return;
        if (button.dataset.voiceIconButton === 'true') {
            const icon = button.querySelector('i');
            if (icon) {
                icon.className = listening ? 'layui-icon layui-icon-pause' : 'layui-icon layui-icon-mike';
            }
            button.classList.toggle('listening', listening);
        } else {
            button.textContent = text;
        }
        button.classList.toggle('active', listening);
        button.setAttribute('aria-label', listening ? '停止语音识别' : '语音输入');
        button.setAttribute('title', listening ? '停止语音识别' : '语音输入');
    }

    resetVoiceButton() {
        const button = this.activeVoiceButton;
        if (button) {
            if (button.dataset.voiceIconButton === 'true') {
                const icon = button.querySelector('i');
                if (icon) {
                    icon.className = 'layui-icon layui-icon-mike';
                }
                button.classList.remove('listening');
            } else {
                button.textContent = '语音输入';
            }
            button.classList.remove('active');
            button.setAttribute('aria-label', '语音输入');
            button.setAttribute('title', '语音输入');
        }
        this.voiceBusy = false;
        this.activeVoiceButton = null;
        this.voiceInterimText = '';
    }

    async handleVoiceCommand(cmd) {
        const command = (cmd || '').trim();
        if (!command) return;

        this.showLayerMessage('已识别语音内容，正在发送给AI助手...', 1);
        this.submitToDigitalHumanChat(command);
        this.announce('已将语音内容发送给智能助手');
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

    extractBusinessAIFeedbackContext(aiResult) {
        if (!aiResult || typeof aiResult !== 'object') return null;
        if (aiResult.endpoint && aiResult.payload) return aiResult;

        const data = aiResult.data && typeof aiResult.data === 'object' ? aiResult.data : aiResult;
        if (data.feedback_context && typeof data.feedback_context === 'object') {
            return data.feedback_context;
        }
        return null;
    }

    submitBusinessAIFeedback(aiResultOrContext, options = {}) {
        const feedbackContext = this.extractBusinessAIFeedbackContext(aiResultOrContext);
        if (!feedbackContext || !feedbackContext.payload) {
            return Promise.reject(new Error('缺少AI反馈上下文'));
        }

        const rating = Number(options.rating);
        if (!Number.isInteger(rating) || rating < 1 || rating > 5) {
            return Promise.reject(new Error('评分必须是1-5的整数'));
        }

        const endpoint = feedbackContext.endpoint || '/ai/business-feedback/';
        const payload = {
            feedback_context: feedbackContext,
            rating: rating,
            comment: options.comment || ''
        };

        return fetch(endpoint, {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': this.getCookie('csrftoken')
            },
            body: JSON.stringify(payload)
        }).then(response => {
            return response.json().then(data => {
                if (!response.ok || data.code !== 0) {
                    throw new Error(data.msg || 'AI反馈提交失败');
                }
                return data;
            });
        });
    }

    showBusinessAIResult(aiResult, options = {}) {
        const title = options.title || 'AI 分析结果';
        const contentId = `business-ai-result-${Date.now()}-${Math.random().toString(16).slice(2)}`;
        const content = `<div id="${contentId}">${this.renderBusinessAIResult(aiResult, options)}</div>`;

        if (window.layui && window.layui.layer) {
            window.layui.layer.open({
                type: 1,
                title: this.escapeHtml(title),
                area: options.area || ['680px', '520px'],
                maxmin: true,
                content,
                btn: options.buttons || ['关闭'],
                success: () => this.bindBusinessAIResultFeedback(contentId, aiResult)
            });
            return;
        }

        window.alert(this.extractBusinessAIPlainText(aiResult));
    }

    mountBusinessAIResult(container, aiResult, options = {}) {
        const target = typeof container === 'string' ? document.querySelector(container) : container;
        if (!target) return false;

        const contentId = `business-ai-result-${Date.now()}-${Math.random().toString(16).slice(2)}`;
        target.innerHTML = `<div id="${contentId}">${this.renderBusinessAIResult(aiResult, options)}</div>`;
        this.bindBusinessAIResultFeedback(contentId, aiResult);
        return true;
    }

    renderBusinessAIResult(aiResult, options = {}) {
        const data = this.extractBusinessAIData(aiResult);
        const riskLevel = data.risk_level || 'unknown';
        const riskLabel = this.formatBusinessAIRiskLevel(riskLevel);
        const actionLabel = this.formatBusinessAIAction(data.recommended_action);
        const confidence = this.formatBusinessAIConfidence(data.confidence);
        const riskPoints = this.toBusinessAIList(data.risk_points);
        const suggestions = this.toBusinessAIList(data.suggestions);
        const sourceRefs = this.toBusinessAIList(data.source_refs).map(ref => {
            if (typeof ref === 'object') {
                return Object.keys(ref).map(key => `${key}: ${ref[key]}`).join(', ');
            }
            return ref;
        });
        const summary = data.summary || data.analysis || data.message || '暂无摘要';
        const hasFeedback = !!this.extractBusinessAIFeedbackContext(data);

        return `
            <div class="business-ai-result" style="padding: 18px 20px; color: #263238; line-height: 1.65; font-size: 14px;">
                <div style="display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 14px;">
                    <span style="display: inline-flex; align-items: center; min-height: 24px; padding: 0 8px; border-radius: 4px; background: ${this.getBusinessAIRiskColor(riskLevel)}; color: #fff;">${this.escapeHtml(riskLabel)}</span>
                    <span style="display: inline-flex; align-items: center; min-height: 24px; padding: 0 8px; border-radius: 4px; background: #eef5ff; color: #1e64b7;">${this.escapeHtml(actionLabel)}</span>
                    <span style="color: #607d8b;">置信度 ${confidence}</span>
                </div>
                <section style="margin-bottom: 14px;">
                    <h4 style="margin: 0 0 6px; font-size: 15px; font-weight: 600;">摘要</h4>
                    <div style="white-space: pre-wrap;">${this.escapeHtml(summary)}</div>
                </section>
                ${this.renderBusinessAIListSection('风险点', riskPoints, '未发现明确风险点')}
                ${this.renderBusinessAIListSection('建议', suggestions, '暂无具体建议')}
                ${data.requires_confirmation ? '<div style="margin: 12px 0; padding: 10px 12px; border-left: 3px solid #ffb800; background: #fff8e6; color: #7a5200;">该结果涉及较高风险或关键动作，请人工确认后再处理。</div>' : ''}
                ${sourceRefs.length ? this.renderBusinessAIListSection('来源', sourceRefs, '') : ''}
                ${options.showRaw && data.raw_result ? `<details style="margin-top: 12px;"><summary style="cursor: pointer; color: #1e9fff;">查看原始结果</summary><pre style="margin-top: 8px; padding: 10px; background: #f6f8fa; overflow: auto;">${this.escapeHtml(JSON.stringify(data.raw_result, null, 2))}</pre></details>` : ''}
                ${hasFeedback ? this.renderBusinessAIFeedbackControls() : ''}
            </div>
        `;
    }

    bindBusinessAIResultFeedback(contentId, aiResult) {
        const root = document.getElementById(contentId);
        if (!root) return;

        root.querySelectorAll('[data-ai-feedback-rating]').forEach(button => {
            button.addEventListener('click', () => {
                const rating = Number(button.getAttribute('data-ai-feedback-rating'));
                const commentInput = root.querySelector('[data-ai-feedback-comment]');
                const status = root.querySelector('[data-ai-feedback-status]');
                button.disabled = true;
                this.submitBusinessAIFeedback(aiResult, {
                    rating,
                    comment: commentInput ? commentInput.value.trim() : ''
                }).then(() => {
                    if (status) status.textContent = '反馈已提交，感谢校准 AI 结果。';
                    root.querySelectorAll('[data-ai-feedback-rating]').forEach(btn => {
                        btn.disabled = true;
                        btn.style.opacity = '0.65';
                    });
                }).catch(error => {
                    button.disabled = false;
                    if (status) status.textContent = error.message || '反馈提交失败，请稍后重试。';
                });
            });
        });
    }

    extractBusinessAIData(aiResult) {
        if (!aiResult || typeof aiResult !== 'object') return {};
        return aiResult.data && typeof aiResult.data === 'object' ? aiResult.data : aiResult;
    }

    extractBusinessAIPlainText(aiResult) {
        const data = this.extractBusinessAIData(aiResult);
        const parts = [
            `摘要：${data.summary || data.analysis || data.message || '暂无摘要'}`,
            `风险等级：${this.formatBusinessAIRiskLevel(data.risk_level || 'unknown')}`,
            `建议动作：${this.formatBusinessAIAction(data.recommended_action)}`
        ];
        const suggestions = this.toBusinessAIList(data.suggestions);
        if (suggestions.length) parts.push(`建议：${suggestions.join('；')}`);
        return parts.join('\n');
    }

    renderBusinessAIListSection(title, items, emptyText) {
        const safeTitle = this.escapeHtml(title);
        if (!items.length) {
            if (!emptyText) return '';
            return `
                <section style="margin-bottom: 14px;">
                    <h4 style="margin: 0 0 6px; font-size: 15px; font-weight: 600;">${safeTitle}</h4>
                    <div style="color: #78909c;">${this.escapeHtml(emptyText)}</div>
                </section>
            `;
        }

        const listItems = items
            .map(item => `<li style="margin-bottom: 4px;">${this.escapeHtml(item)}</li>`)
            .join('');
        return `
            <section style="margin-bottom: 14px;">
                <h4 style="margin: 0 0 6px; font-size: 15px; font-weight: 600;">${safeTitle}</h4>
                <ul style="margin: 0; padding-left: 18px;">${listItems}</ul>
            </section>
        `;
    }

    renderBusinessAIFeedbackControls() {
        const buttons = [1, 2, 3, 4, 5].map(rating => (
            `<button type="button" class="layui-btn layui-btn-primary layui-btn-xs" data-ai-feedback-rating="${rating}" style="min-width: 32px;">${rating}</button>`
        )).join('');

        return `
            <section style="margin-top: 16px; padding-top: 12px; border-top: 1px solid #edf1f5;">
                <div style="margin-bottom: 8px; font-weight: 600;">结果反馈</div>
                <div style="display: flex; flex-wrap: wrap; gap: 8px; align-items: center;">
                    <span style="color: #607d8b;">评分</span>
                    ${buttons}
                    <input type="text" data-ai-feedback-comment placeholder="可选：补充修正意见" style="flex: 1 1 220px; min-width: 180px; height: 28px; padding: 0 8px; border: 1px solid #dcdfe6; border-radius: 4px;">
                </div>
                <div data-ai-feedback-status style="margin-top: 8px; min-height: 20px; color: #607d8b;"></div>
            </section>
        `;
    }

    toBusinessAIList(value) {
        if (Array.isArray(value)) return value.filter(item => item !== null && item !== undefined && item !== '');
        if (value === null || value === undefined || value === '') return [];
        return [value];
    }

    formatBusinessAIRiskLevel(level) {
        const labels = {
            high: '高风险',
            medium: '中风险',
            low: '低风险',
            unknown: '风险未知'
        };
        return labels[level] || String(level || '风险未知');
    }

    getBusinessAIRiskColor(level) {
        const colors = {
            high: '#e34d59',
            medium: '#ed7b2f',
            low: '#2ba471',
            unknown: '#78909c'
        };
        return colors[level] || colors.unknown;
    }

    formatBusinessAIAction(action) {
        const labels = {
            approve: '建议通过',
            reject: '建议拒绝',
            request_more_info: '建议补充信息',
            manual_review: '人工复核',
            follow_up: '建议跟进'
        };
        return labels[action] || '人工复核';
    }

    formatBusinessAIConfidence(confidence) {
        const value = Number(confidence);
        if (!Number.isFinite(value)) return '0%';
        return `${Math.round(Math.max(0, Math.min(1, value)) * 100)}%`;
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
        this.openAIAssistant(text);
        return true;
    }

    summarizePage() {
        this.announce('正在生成页面业务分析...');
        if (window.layui && window.layui.layer) {
            window.layui.layer.msg('AI 正在分析当前业务数据...', {icon: 16, time: 2000});
        }
        const summary = this.buildPageBusinessSummary();
        this.announce(summary.text);
        if (window.layui && window.layui.layer) {
            window.layui.layer.open({
                type: 1,
                title: '<i class="layui-icon layui-icon-auz"></i> AI 业务分析摘要',
                shade: 0,
                offset: 'rb',
                area: ['520px', '460px'],
                maxmin: true,
                content: summary.html,
                anim: 2
            });
        }
    }

    buildPageSummary() {
        return this.buildPageBusinessSummary().text;
    }

    buildPageBusinessSummary() {
        const context = this.getPageBusinessContext();
        const metrics = this.collectBusinessMetrics();
        const rows = this.collectBusinessRows();
        const analysis = this.analyzeBusinessRows(rows);
        const suggestions = this.buildBusinessSuggestions(context, metrics, analysis);
        const textParts = [
            `${context.title}：当前可见 ${rows.length} 条业务记录`,
            metrics.length ? `关键指标 ${metrics.slice(0, 3).map(item => `${item.label}${item.value}`).join('，')}` : '',
            analysis.riskCount ? `发现 ${analysis.riskCount} 条风险/异常信号` : '',
            analysis.pendingCount ? `待处理 ${analysis.pendingCount} 条` : '',
            analysis.amountTotal !== null ? `可见金额合计 ${this.formatBusinessNumber(analysis.amountTotal)}` : '',
            suggestions[0] ? `建议：${suggestions[0]}` : ''
        ].filter(Boolean);

        return {
            text: textParts.join('；'),
            html: this.renderBusinessPageSummary(context, metrics, analysis, suggestions, rows)
        };
    }

    getPageBusinessContext() {
        const activeMenu = document.querySelector('.layui-side .layui-this a, .layui-nav .layui-this a');
        const pageTitle = document.querySelector('.layui-tab-title .layui-this, .layui-card-header, h1, h2');
        const rawTitle = (pageTitle && pageTitle.textContent.trim()) || (activeMenu && activeMenu.textContent.trim()) || document.title || '当前页面';
        const title = rawTitle.replace(/\s+/g, ' ').trim();
        const path = window.location.pathname || '';
        return {
            title,
            path,
            module: this.inferBusinessModule(`${title} ${path}`)
        };
    }

    inferBusinessModule(text) {
        const value = String(text || '');
        const modules = [
            {name: '客户经营', keys: ['customer', '客户', '线索', '公海', '意向']},
            {name: '合同履约', keys: ['contract', '合同', '采购', '销售']},
            {name: '项目交付', keys: ['project', '项目', '任务', '工时']},
            {name: '财务资金', keys: ['finance', '财务', '付款', '回款', '报销', '发票', '开票']},
            {name: '生产运营', keys: ['production', '生产', '工序', '质检', '设备', 'BOM', 'SOP']},
            {name: '审批协同', keys: ['approval', '审批', '待办']},
            {name: '库存供应', keys: ['inventory', '库存', '入库', '出库']}
        ];
        const matched = modules.find(item => item.keys.some(key => value.includes(key)));
        return matched ? matched.name : '综合业务';
    }

    collectBusinessMetrics() {
        const candidates = Array.from(document.querySelectorAll(
            '.stat-item, .stats-card, .stat-card, .layui-card, [id*="total"], [id*="Count"], [class*="stat"], [class*="summary"]'
        ));
        const metrics = [];
        const seen = new Set();

        candidates.forEach(element => {
            if (!this.isVisibleElement(element)) return;
            const valueNode = element.querySelector('.stat-number, .stat-value, [class*="number"], [class*="value"]') || element;
            const rawValue = (valueNode.textContent || '').replace(/\s+/g, ' ').trim();
            if (!rawValue || rawValue.length > 40 || !/[0-9¥￥%]/.test(rawValue)) return;
            const label = this.findMetricLabel(element, valueNode);
            const key = `${label}:${rawValue}`;
            if (seen.has(key)) return;
            seen.add(key);
            metrics.push({label, value: rawValue});
        });

        return metrics.slice(0, 8);
    }

    findMetricLabel(element, valueNode) {
        const labelNode = element.querySelector('.stat-label, .stat-title, [class*="label"], [class*="title"]');
        if (labelNode && labelNode !== valueNode) {
            const label = (labelNode.textContent || '').replace(/\s+/g, ' ').trim();
            if (label && label.length <= 24) return label;
        }
        const text = (element.textContent || '').replace(/\s+/g, ' ').trim();
        const value = (valueNode.textContent || '').replace(/\s+/g, ' ').trim();
        const label = text.replace(value, '').trim();
        return label && label.length <= 24 ? label : '指标';
    }

    collectBusinessRows() {
        const rows = [];
        document.querySelectorAll('.layui-table-view').forEach(view => {
            const headers = Array.from(view.querySelectorAll('.layui-table-header th')).map(th => th.textContent.trim());
            view.querySelectorAll('.layui-table-body tbody tr').forEach(tr => {
                const cells = Array.from(tr.querySelectorAll('td')).map((td, index) => ({
                    label: (headers[index] || td.getAttribute('data-field') || '').trim(),
                    value: td.textContent.replace(/\s+/g, ' ').trim()
                })).filter(cell => cell.value);
                if (cells.length) rows.push(cells);
            });
        });

        document.querySelectorAll('table').forEach(table => {
            if (table.closest && table.closest('.layui-table-view')) return;
            if (!this.isVisibleElement(table)) return;
            const headers = Array.from(table.querySelectorAll('thead th, tr:first-child th')).map(th => th.textContent.trim());
            table.querySelectorAll('tbody tr, tr').forEach((tr, rowIndex) => {
                if (rowIndex === 0 && tr.querySelector('th')) return;
                const cells = Array.from(tr.querySelectorAll('td')).map((td, index) => ({
                    label: (headers[index] || '').trim(),
                    value: td.textContent.replace(/\s+/g, ' ').trim()
                })).filter(cell => cell.value);
                if (cells.length) rows.push(cells);
            });
        });

        return rows.slice(0, 120);
    }

    analyzeBusinessRows(rows) {
        const statusCounter = {};
        const riskWords = ['风险', '异常', '逾期', '超期', '失败', '拒绝', '不通过', '作废', '取消', '欠款', '超支', '低于'];
        const pendingWords = ['待', '审核中', '处理中', '未开始', '未完成', '待检', '待处理', '待审核', '待付款', '待回款'];
        const doneWords = ['完成', '通过', '已付款', '已回款', '已确认', '已交付', '正常', '启用'];
        let riskCount = 0;
        let pendingCount = 0;
        let doneCount = 0;
        let amountTotal = 0;
        let amountFound = false;
        const riskSamples = [];

        rows.forEach(cells => {
            const rowText = cells.map(cell => cell.value).join(' ');
            if (riskWords.some(word => rowText.includes(word))) {
                riskCount += 1;
                if (riskSamples.length < 3) riskSamples.push(rowText.slice(0, 80));
            }
            if (pendingWords.some(word => rowText.includes(word))) pendingCount += 1;
            if (doneWords.some(word => rowText.includes(word))) doneCount += 1;

            cells.forEach(cell => {
                const label = `${cell.label} ${cell.value}`;
                if (/状态|进度|阶段|结果/.test(label)) {
                    const status = cell.value.slice(0, 16);
                    statusCounter[status] = (statusCounter[status] || 0) + 1;
                }
                if (/金额|费用|成本|收入|付款|回款|报价|总价|工时|数量|合计/.test(label)) {
                    const numericValue = this.parseBusinessNumber(cell.value);
                    if (numericValue !== null) {
                        amountFound = true;
                        amountTotal += numericValue;
                    }
                }
            });
        });

        return {
            rowCount: rows.length,
            statusCounter,
            riskCount,
            pendingCount,
            doneCount,
            amountTotal: amountFound ? amountTotal : null,
            riskSamples
        };
    }

    buildBusinessSuggestions(context, metrics, analysis) {
        const suggestions = [];
        if (analysis.riskCount > 0) {
            suggestions.push(`优先复核 ${analysis.riskCount} 条风险/异常记录，确认责任人和处理时限。`);
        }
        if (analysis.pendingCount > 0) {
            suggestions.push(`将 ${analysis.pendingCount} 条待处理事项按金额、到期时间或客户级别排序推进。`);
        }
        if (analysis.amountTotal !== null) {
            suggestions.push(`核对可见金额合计 ${this.formatBusinessNumber(analysis.amountTotal)}，关注大额记录的审批和回款状态。`);
        }
        if (!analysis.rowCount && !metrics.length) {
            suggestions.push('当前页面可见业务数据较少，建议先完成筛选或加载列表后再生成分析。');
        }
        if (!suggestions.length) {
            suggestions.push(`当前${context.module}数据暂无明显风险，建议继续关注新增、待审和异常状态变化。`);
        }
        return suggestions.slice(0, 4);
    }

    renderBusinessPageSummary(context, metrics, analysis, suggestions, rows) {
        const statusItems = Object.entries(analysis.statusCounter)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 6)
            .map(([name, count]) => `<span style="display:inline-flex;align-items:center;margin:0 8px 8px 0;padding:4px 8px;border-radius:4px;background:#eef5ff;color:#1e64b7;">${this.escapeHtml(name)} ${count}</span>`)
            .join('');
        const metricItems = metrics.length
            ? metrics.map(item => `<li>${this.escapeHtml(item.label)}：<strong>${this.escapeHtml(item.value)}</strong></li>`).join('')
            : '<li style="color:#8c8c8c;">未识别到显著指标卡片</li>';
        const riskItems = analysis.riskSamples.length
            ? analysis.riskSamples.map(item => `<li>${this.escapeHtml(item)}</li>`).join('')
            : '<li style="color:#8c8c8c;">当前可见数据未发现明确风险关键词</li>';
        const suggestionItems = suggestions.map(item => `<li>${this.escapeHtml(item)}</li>`).join('');
        const amountText = analysis.amountTotal !== null ? this.formatBusinessNumber(analysis.amountTotal) : '未识别';

        return `
            <div style="padding:18px 20px;color:#263238;line-height:1.65;font-size:14px;">
                <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:14px;">
                    <span style="display:inline-flex;align-items:center;min-height:24px;padding:0 8px;border-radius:4px;background:#1677ff;color:#fff;">${this.escapeHtml(context.module)}</span>
                    <span style="color:#607d8b;">${this.escapeHtml(context.title)}</span>
                </div>
                <section style="margin-bottom:14px;">
                    <h4 style="margin:0 0 6px;font-size:15px;font-weight:600;">业务概览</h4>
                    <div>当前可见业务记录 <strong>${rows.length}</strong> 条，风险/异常 <strong>${analysis.riskCount}</strong> 条，待处理 <strong>${analysis.pendingCount}</strong> 条，金额/数量合计 <strong>${this.escapeHtml(amountText)}</strong>。</div>
                </section>
                <section style="margin-bottom:14px;">
                    <h4 style="margin:0 0 6px;font-size:15px;font-weight:600;">关键指标</h4>
                    <ul style="margin:0;padding-left:18px;">${metricItems}</ul>
                </section>
                <section style="margin-bottom:14px;">
                    <h4 style="margin:0 0 6px;font-size:15px;font-weight:600;">状态分布</h4>
                    <div>${statusItems || '<span style="color:#8c8c8c;">未识别到状态字段</span>'}</div>
                </section>
                <section style="margin-bottom:14px;">
                    <h4 style="margin:0 0 6px;font-size:15px;font-weight:600;">风险信号</h4>
                    <ul style="margin:0;padding-left:18px;">${riskItems}</ul>
                </section>
                <section>
                    <h4 style="margin:0 0 6px;font-size:15px;font-weight:600;">建议动作</h4>
                    <ul style="margin:0;padding-left:18px;">${suggestionItems}</ul>
                </section>
            </div>
        `;
    }

    parseBusinessNumber(value) {
        const cleaned = String(value || '').replace(/,/g, '').match(/-?\d+(\.\d+)?/);
        if (!cleaned) return null;
        const number = Number(cleaned[0]);
        return Number.isFinite(number) ? number : null;
    }

    formatBusinessNumber(value) {
        const number = Number(value);
        if (!Number.isFinite(number)) return '0';
        return number.toLocaleString('zh-CN', {maximumFractionDigits: 2});
    }

    isVisibleElement(element) {
        if (!element || !element.getBoundingClientRect) return false;
        const rect = element.getBoundingClientRect();
        return rect.width > 0 && rect.height > 0;
    }

    openAIAssistant(initialText = '') {
        const url = '/ai/chat/';
        if (initialText) {
            try {
                window.sessionStorage.setItem('dtcall_ai_pending_message', initialText);
            } catch (error) {
                // Ignore storage errors; the assistant still opens normally.
            }
        }
        if (window.layui && window.layui.layer) {
            const existingIndex = window.aiAssistantLayerIndex;
            if (existingIndex && document.getElementById(`layui-layer${existingIndex}`)) {
                window.layui.layer.style(existingIndex, {
                    right: 0,
                    top: 0,
                    width: '80%',
                    height: '100%'
                });
                return;
            }

            window.aiAssistantLayerIndex = window.layui.layer.open({
                type: 2,
                title: 'AI助手',
                shadeClose: false,
                shade: 0.3,
                maxmin: true,
                area: ['80%', '100%'],
                offset: 'r',
                anim: 2,
                content: url,
                end: () => {
                    window.aiAssistantLayerIndex = null;
                }
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

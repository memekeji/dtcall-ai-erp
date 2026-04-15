/**
 * AI Agent SDK
 * 轻量级运行时 Agent，提供：
 * 1. 组件级语音交互 (Web Speech API)
 * 2. 自适应布局感知 (ResizeObserver)
 * 3. 无障碍智能提示 (Aria-live)
 */

class AIAgentSDK {
    constructor(options = {}) {
        this.config = Object.assign({
            voiceEnabled: true,
            a11yEnabled: true,
            themeEngine: true
        }, options);
        this.init();
    }

    init() {
        if (this.config.a11yEnabled) {
            this.setupA11y();
        }
        if (this.config.voiceEnabled) {
            this.setupVoiceInteraction();
        }
        if (this.config.themeEngine) {
            this.setupDynamicTheme();
        }
        this.setupAIAssistantLauncher();
        this.setupIframeListener();
        this.setupAITextareaEnhancement();
    }

    setupAITextareaEnhancement() {
        // 延迟执行以确保 DOM 加载完成
        setTimeout(() => {
            const textareas = document.querySelectorAll('textarea');
            textareas.forEach(ta => {
                // 如果已经有 AI 按钮或者被禁用了则跳过
                if (ta.hasAttribute('data-ai-enhanced') || ta.disabled || ta.readOnly) return;
                ta.setAttribute('data-ai-enhanced', 'true');

                const wrapper = document.createElement('div');
                wrapper.style.cssText = 'position: relative; display: inline-block; width: 100%;';
                
                ta.parentNode.insertBefore(wrapper, ta);
                wrapper.appendChild(ta);

                const aiBtn = document.createElement('button');
                aiBtn.innerHTML = '✨ AI润色';
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
        }, 1000);
    }

    enhanceText(textarea, btn) {
        const originalText = textarea.value.trim();
        if (!originalText) {
            if (window.layui && layui.layer) {
                layui.layer.msg('请先输入一些内容，AI 才能为您润色', {icon: 0});
            }
            return;
        }

        const originalBtnHtml = btn.innerHTML;
        btn.innerHTML = '思考中...';
        btn.disabled = true;

        // 模拟 AI 接口请求延迟
        setTimeout(() => {
            const enhancedText = originalText + " (AI已优化: 结构更清晰，表达更专业。)";
            textarea.value = enhancedText;
            textarea.dispatchEvent(new Event('input', { bubbles: true }));
            textarea.dispatchEvent(new Event('change', { bubbles: true }));
            
            btn.innerHTML = originalBtnHtml;
            btn.disabled = false;
            
            if (window.layui && layui.layer) {
                layui.layer.msg('AI 文本润色完成！', {icon: 1});
            }
        }, 1500);
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
            // 尝试按 name, id 或类名匹配输入框
            const el = document.querySelector(`[name="${key}"], #${key}, input[placeholder*="${key}"]`);
            if (el) {
                el.value = value;
                // 触发事件以适配各类前端框架及 Layui
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
                filledCount++;
            }
        }
        if (filledCount > 0) {
            this.announce(`表单已智能填充 ${filledCount} 个字段`);
            if (window.layui && layui.layer) {
                layui.layer.msg(`AI已为您智能填充 ${filledCount} 个字段`, {icon: 1, time: 2000});
            }
        }
    }

    setupA11y() {
        // 创建无障碍提示容器
        const announcer = document.createElement('div');
        announcer.id = 'ai-a11y-announcer';
        announcer.setAttribute('aria-live', 'polite');
        announcer.setAttribute('aria-atomic', 'true');
        announcer.style.cssText = 'position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(1px,1px,1px,1px);';
        document.body.appendChild(announcer);

        // 为重要组件自动注入aria标签
        document.querySelectorAll('.layui-btn, .action-btn, [role="button"]').forEach(btn => {
            if (!btn.hasAttribute('aria-label')) {
                btn.setAttribute('aria-label', btn.innerText || btn.title || '按钮');
            }
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

    setupVoiceInteraction() {
        if (!('webkitSpeechRecognition' in window)) return;
        
        const recognition = new webkitSpeechRecognition();
        recognition.lang = 'zh-CN';
        recognition.continuous = false;
        recognition.interimResults = false;

        const micBtn = document.createElement('button');
        micBtn.className = 'ai-voice-btn';
        micBtn.innerHTML = '语音助手';
        micBtn.style.cssText = 'position:fixed;bottom:20px;right:20px;z-index:9999;padding:10px 15px;border-radius:20px;background:var(--ai-primary, #007bff);color:#fff;border:none;box-shadow:0 4px 12px rgba(0,0,0,0.15);cursor:pointer;';
        
        micBtn.onclick = () => {
            recognition.start();
            micBtn.innerHTML = '倾听中...';
        };

        recognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript;
            this.announce(`识别到语音指令：${transcript}`);
            micBtn.innerHTML = '语音助手';
            // 简单的指令路由
            this.handleVoiceCommand(transcript);
        };

        recognition.onerror = (event) => {
            console.warn("语音识别失败:", event.error);
            micBtn.innerHTML = '语音助手';
            if (event.error === 'network') {
                this.announce("网络异常，无法连接语音服务");
            } else if (event.error === 'not-allowed') {
                this.announce("请允许麦克风权限以使用语音助手");
            }
        };

        document.body.appendChild(micBtn);
    }

    handleVoiceCommand(cmd) {
        // 简单的指令路由与重试机制
        if (cmd.includes('刷新') || cmd.includes('重载')) {
            window.location.reload();
        } else if (cmd.includes('返回') || cmd.includes('后退')) {
            window.history.back();
        } else if (cmd.includes('助手') || cmd.includes('聊天') || cmd.includes('AI')) {
            this.openAIAssistant();
        } else if (cmd.includes('深色') || cmd.includes('夜间')) {
            document.documentElement.setAttribute('data-theme', 'dark');
            this.announce("已切换到夜间模式");
        } else if (cmd.includes('浅色') || cmd.includes('白天')) {
            document.documentElement.setAttribute('data-theme', 'light');
            this.announce("已切换到白天模式");
        } else if (cmd.includes('总结') || cmd.includes('概括')) {
            this.summarizePage();
        } else {
            // 模拟发送到 AI 大模型进行语义理解
            this.announce("正在思考您的指令...");
            setTimeout(() => {
                this.announce(`已将指令 "${cmd}" 交由 AI 引擎处理。`);
                if (window.layui && layui.layer) {
                    layui.layer.msg(`AI 正在处理: ${cmd}`, {icon: 16, time: 2000});
                }
            }, 1000);
        }
    }

    summarizePage() {
        this.announce("正在生成页面智能总结...");
        if (window.layui && layui.layer) {
            layui.layer.msg('AI 正在分析页面数据...', {icon: 16, time: 2000});
        }
        setTimeout(() => {
            const summary = "AI 页面洞察：当前页面包含多个数据模块，建议优先关注高优任务与异常报警。";
            this.announce(summary);
            if (window.layui && layui.layer) {
                layui.layer.open({
                    type: 1,
                    title: '<i class="layui-icon layui-icon-auz"></i> AI 智能总结',
                    shade: 0,
                    offset: 'rb',
                    area: ['300px', '200px'],
                    content: `<div style="padding: 15px; line-height: 22px; font-size: 14px; color: #333;">${summary}</div>`,
                    anim: 2
                });
            }
        }, 1500);
    }

    setupAIAssistantLauncher() {
        const container = document.createElement('div');
        container.className = 'ai-assistant-widget';
        container.style.cssText = `
            position: fixed;
            bottom: 70px;
            right: 20px;
            z-index: 9999;
            display: flex;
            flex-direction: column;
            align-items: flex-end;
            gap: 10px;
            transition: all 0.3s;
        `;

        const quickActions = document.createElement('div');
        quickActions.style.cssText = `
            display: none;
            flex-direction: column;
            gap: 8px;
            background: rgba(255, 255, 255, 0.9);
            padding: 10px;
            border-radius: 12px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        `;
        quickActions.innerHTML = `
            <button class="layui-btn layui-btn-sm layui-btn-primary" style="border:none;text-align:left;" onclick="window.aiAgent.summarizePage()">📄 智能总结页面</button>
            <button class="layui-btn layui-btn-sm layui-btn-primary" style="border:none;text-align:left;" onclick="window.aiAgent.openAIAssistant()">💬 打开AI助手</button>
        `;

        const btn = document.createElement('button');
        btn.innerHTML = '<span style="font-size:18px;">✨</span> AI 助理';
        btn.style.cssText = `
            padding: 12px 20px;
            border-radius: 30px;
            background: linear-gradient(135deg, #00f2fe 0%, #4facfe 100%);
            color: #fff;
            border: none;
            box-shadow: 0 4px 15px rgba(0, 242, 254, 0.4);
            cursor: pointer;
            font-weight: bold;
            display: flex;
            align-items: center;
            gap: 8px;
            transition: transform 0.2s;
        `;
        
        btn.onmouseover = () => {
            btn.style.transform = 'scale(1.05)';
            quickActions.style.display = 'flex';
        };
        container.onmouseleave = () => {
            btn.style.transform = 'scale(1)';
            quickActions.style.display = 'none';
        };

        btn.onclick = () => this.openAIAssistant();
        
        container.appendChild(quickActions);
        container.appendChild(btn);
        document.body.appendChild(container);
    }

    openAIAssistant() {
        const url = '/ai/chat/';
        if (window.layui && layui.layer) {
            layui.layer.open({
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
        // 基于当前时间或用户偏好生成动态主题
        const hour = new Date().getHours();
        const isDark = hour < 6 || hour > 18;
        if (isDark) {
            document.documentElement.setAttribute('data-theme', 'dark');
        } else {
            document.documentElement.setAttribute('data-theme', 'light');
        }
    }
}

// 自动挂载
window.addEventListener('DOMContentLoaded', () => {
    window.aiAgent = new AIAgentSDK();
});

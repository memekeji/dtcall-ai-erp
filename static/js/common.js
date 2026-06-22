// Common JavaScript functions for DTCall project

/**
 * 显示消息提示
 * @param {string} message 消息内容
 * @param {string} type 消息类型 (success, error, warning, info)
 */
function showMessage(message, type = 'info') {
    if (typeof layui !== 'undefined' && layui.layer) {
        let icon = 0;
        switch(type) {
            case 'success':
                icon = 1;
                break;
            case 'error':
                icon = 2;
                break;
            case 'warning':
                icon = 0;
                break;
            case 'info':
            default:
                icon = 0;
        }
        layui.layer.msg(message, {icon: icon, time: 2000});
    } else {
        alert(message);
    }
}

/**
 * 格式化日期时间
 * @param {string|Date} date 日期对象或字符串
 * @param {string} format 格式 (YYYY-MM-DD HH:mm:ss)
 * @returns {string} 格式化后的日期字符串
 */
function formatDate(date, format = 'YYYY-MM-DD HH:mm:ss') {
    if (!date) return '';
    
    const d = new Date(date);
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    const hours = String(d.getHours()).padStart(2, '0');
    const minutes = String(d.getMinutes()).padStart(2, '0');
    const seconds = String(d.getSeconds()).padStart(2, '0');
    
    return format
        .replace('YYYY', year)
        .replace('MM', month)
        .replace('DD', day)
        .replace('HH', hours)
        .replace('mm', minutes)
        .replace('ss', seconds);
}

/**
 * AJAX请求封装
 * @param {string} url 请求URL
 * @param {object} options 请求选项
 * @returns {Promise} Promise对象
 */
function ajaxRequest(url, options = {}) {
    const defaultOptions = {
        method: 'GET',
        data: null,
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/json'
        }
    };
    
    const mergedOptions = {...defaultOptions, ...options};
    
    return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open(mergedOptions.method, url, true);
        
        // 设置请求头
        Object.keys(mergedOptions.headers).forEach(key => {
            xhr.setRequestHeader(key, mergedOptions.headers[key]);
        });
        
        xhr.onload = function() {
            if (xhr.status >= 200 && xhr.status < 300) {
                try {
                    const response = JSON.parse(xhr.responseText);
                    resolve(response);
                } catch (e) {
                    resolve(xhr.responseText);
                }
            } else if (xhr.status === 401) {
                try {
                    const response = JSON.parse(xhr.responseText);
                    if (response.data && response.data.redirect_url) {
                        if (window.top !== window) {
                            window.top.location.href = response.data.redirect_url;
                        } else {
                            window.location.href = response.data.redirect_url;
                        }
                    } else {
                        window.location.href = '/user/login/';
                    }
                } catch (e) {
                    window.location.href = '/user/login/';
                }
            } else {
                reject(new Error(`请求失败: ${xhr.status}`));
            }
        };
        
        xhr.onerror = function() {
            reject(new Error('网络请求失败'));
        };
        
        if (mergedOptions.data && mergedOptions.method !== 'GET') {
            xhr.send(JSON.stringify(mergedOptions.data));
        } else {
            xhr.send();
        }
    });
}

/**
 * 获取指定Cookie值
 * @param {string} name Cookie名称
 * @returns {string} Cookie值
 */
function getCookie(name) {
    const escapedName = String(name || '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const match = document.cookie ? document.cookie.match(new RegExp('(?:^|;\\s*)' + escapedName + '=([^;]*)')) : null;
    return match ? decodeURIComponent(match[1]) : '';
}

/**
 * 获取CSRF令牌
 * @returns {string} CSRF令牌
 */
function getCsrfToken() {
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');
    if (csrfToken && csrfToken.value) {
        return csrfToken.value;
    }

    return getCookie('csrftoken');
}

/**
 * 转义HTML内容，避免动态表格/弹窗内容注入HTML。
 * @param {*} value 待转义的值
 * @returns {string} 安全HTML字符串
 */
function escapeHtml(value) {
    return String(value || '').replace(/[&<>"']/g, function(char) {
        return {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#39;'
        }[char];
    });
}

/**
 * 转义HTML属性值，补充处理反引号。
 * @param {*} value 待转义的值
 * @returns {string} 安全属性字符串
 */
function escapeAttr(value) {
    return escapeHtml(value).replace(/`/g, '&#96;');
}

/**
 * 打开右侧iframe弹窗，统一列表页新增/编辑体验。
 * @param {object} layer Layui layer实例
 * @param {string} title 弹窗标题
 * @param {string} url iframe地址
 * @param {object} options 弹窗配置
 * @returns {*} layer.open返回值
 */
function openRightPopup(layer, title, url, options = {}) {
    const width = options.width || '80%';
    const height = options.height || '100%';
    const onClose = options.onClose;

    return layer.open({
        type: 2,
        title: title,
        shadeClose: options.shadeClose === true,
        shade: options.shade === undefined ? 0.3 : options.shade,
        maxmin: options.maxmin !== false,
        area: [width, height],
        offset: options.offset || 'r',
        anim: options.anim === undefined ? 2 : options.anim,
        content: url,
        success: function(layero) {
            if (layero && typeof layero.css === 'function') {
                layero.css({
                    right: '0',
                    top: '0',
                    height: height
                });
            }
            if (typeof options.success === 'function') {
                options.success(layero);
            }
        },
        end: function() {
            if (typeof onClose === 'function') {
                onClose();
            }
        }
    });
}

/**
 * 页面加载完成后执行
 */
document.addEventListener('DOMContentLoaded', function() {
    
    if (typeof jQuery !== 'undefined') {
        jQuery(document).ajaxError(function(event, xhr, settings, error) {
            if (xhr.status === 401) {
                try {
                    var response = JSON.parse(xhr.responseText);
                    if (response.data && response.data.redirect_url) {
                        if (window.top !== window) {
                            window.top.location.href = response.data.redirect_url;
                        } else {
                            window.location.href = response.data.redirect_url;
                        }
                    } else {
                        window.location.href = '/user/login/';
                    }
                } catch (e) {
                    window.location.href = '/user/login/';
                }
            }
        });
    }
});

// 导出函数供其他模块使用
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        showMessage,
        formatDate,
        ajaxRequest,
        getCookie,
        getCsrfToken,
        escapeHtml,
        escapeAttr,
        openRightPopup
    };
}

if (typeof window !== 'undefined') {
    window.DTCallCommon = {
        showMessage,
        formatDate,
        ajaxRequest,
        getCookie,
        getCsrfToken,
        escapeHtml,
        escapeAttr,
        openRightPopup
    };
}

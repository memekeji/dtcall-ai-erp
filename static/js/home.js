// 确保DOM和LayUI加载完成后执行
document.addEventListener('DOMContentLoaded', function() {
    // 防止重复初始化
    if (window.dtcallHomeJsInitialized) {
        return;
    }
    window.dtcallHomeJsInitialized = true;

    const LOGIN_REDIRECT_MARKER_KEY = 'dtcallForceDashboardAfterLogin';

    function getActiveTabId() {
        const activeTab = document.querySelector('.layui-tab-title li.layui-this');
        return activeTab ? activeTab.getAttribute('lay-id') : '';
    }

    function buildTabId(url, title) {
        if (!url) {
            return `tab-${title}`;
        }

        if (url === '/home/dashboard/' || url === '/dashboard/' || title === '工作台') {
            return 'dashboard';
        }

        try {
            const parsed = new URL(url, window.location.origin);
            const normalizedPath = parsed.pathname.replace(/\/+$/g, '') || '/';
            const path = normalizedPath === '/disk/permission/manage' ? '/disk/permission' : normalizedPath;
            const query = Array.from(parsed.searchParams.entries())
                .map(([key, value]) => `${key}=${value}`)
                .sort()
                .join('&');
            return `tab-${path}${query ? `?${query}` : ''}`;
        } catch (error) {
            return `tab-${title}`;
        }
    }

    function getTabIframe(tabId) {
        if (!tabId) {
            return null;
        }
        return document.querySelector(`.layui-tab-content .layui-tab-item[lay-id="${tabId}"] iframe`);
    }

    function syncActiveTabState(tabId) {
        if (!tabId) {
            return;
        }

        const tabTitles = document.querySelectorAll('.layui-tab-title li');
        const tabItems = document.querySelectorAll('.layui-tab-content .layui-tab-item');

        tabTitles.forEach(tabTitle => {
            const isActive = tabTitle.getAttribute('lay-id') === tabId;
            tabTitle.classList.toggle('layui-this', isActive);
            if (isActive) {
                tabTitle.setAttribute('aria-selected', 'true');
            } else {
                tabTitle.removeAttribute('aria-selected');
            }
        });

        tabItems.forEach(tabItem => {
            tabItem.classList.toggle('layui-show', tabItem.getAttribute('lay-id') === tabId);
        });

        localStorage.setItem('activeTabId', tabId);
    }

    function activateTab(tabId) {
        if (!tabId) {
            return;
        }

        const tabTitle = document.querySelector(`.layui-tab-title li[lay-id="${tabId}"]`);
        if (tabTitle) {
            tabTitle.click();
            return;
        }

        if (typeof layui !== 'undefined') {
            layui.use(['element'], function() {
                const element = layui.element;
                element.tabChange('main-tab', tabId);
                syncActiveTabState(tabId);
            });
        }
    }

    function getTabTitleElement(tabId) {
        if (!tabId) {
            return null;
        }

        return Array.from(document.querySelectorAll('.layui-tab-title li'))
            .find(tabTitle => tabTitle.getAttribute('lay-id') === tabId) || null;
    }

    function getTabContentElement(tabId) {
        if (!tabId) {
            return null;
        }

        return Array.from(document.querySelectorAll('.layui-tab-content .layui-tab-item'))
            .find(tabItem => tabItem.getAttribute('lay-id') === tabId) || null;
    }

    function closeTabById(tabId, options) {
        const settings = Object.assign({
            keepAtLeastOne: true,
            activateFallback: true
        }, options || {});

        if (!tabId) {
            return false;
        }

        const tabTitle = getTabTitleElement(tabId);
        const tabContent = getTabContentElement(tabId);
        if (!tabTitle) {
            return false;
        }

        const tabTitles = Array.from(document.querySelectorAll('.layui-tab-title li'));
        if (settings.keepAtLeastOne && tabTitles.length <= 1) {
            return false;
        }

        const isActive = tabTitle.classList.contains('layui-this');
        let fallbackTabId = '';

        if (isActive && settings.activateFallback !== false) {
            const nextTab = tabTitle.nextElementSibling && tabTitle.nextElementSibling.matches('li')
                ? tabTitle.nextElementSibling
                : null;
            const prevTab = !nextTab && tabTitle.previousElementSibling && tabTitle.previousElementSibling.matches('li')
                ? tabTitle.previousElementSibling
                : null;
            const replacementTab = nextTab || prevTab || tabTitles.find(li => li !== tabTitle) || null;
            fallbackTabId = replacementTab ? replacementTab.getAttribute('lay-id') : '';
        }

        tabTitle.remove();
        if (tabContent) {
            tabContent.remove();
        }

        if (fallbackTabId) {
            syncActiveTabState(fallbackTabId);
            activateTab(fallbackTabId);
        } else if (typeof layui !== 'undefined') {
            layui.use(['element'], function() {
                const element = layui.element;
                element.render('tab');
            });
        }

        saveTabs();
        return true;
    }

    function closeOtherTabs(tabId) {
        if (!tabId) {
            return false;
        }

        const tabTitles = Array.from(document.querySelectorAll('.layui-tab-title li'));
        let changed = false;

        tabTitles.forEach(tabTitle => {
            const currentTabId = tabTitle.getAttribute('lay-id');
            if (currentTabId && currentTabId !== tabId) {
                closeTabById(currentTabId, {
                    keepAtLeastOne: false,
                    activateFallback: false
                });
                changed = true;
            }
        });

        if (changed) {
            syncActiveTabState(tabId);
            activateTab(tabId);
            saveTabs();
        }

        return changed;
    }

    function closeAllTabs() {
        const tabTitles = Array.from(document.querySelectorAll('.layui-tab-title li'));
        if (tabTitles.length <= 1) {
            return false;
        }

        const firstTabId = tabTitles[0].getAttribute('lay-id');
        tabTitles.slice(1).forEach(tabTitle => {
            const tabId = tabTitle.getAttribute('lay-id');
            if (tabId) {
                closeTabById(tabId, {
                    keepAtLeastOne: false,
                    activateFallback: false
                });
            }
        });

        if (firstTabId) {
            syncActiveTabState(firstTabId);
            activateTab(firstTabId);
        }

        saveTabs();
        return true;
    }

    function navigateCurrentTab(direction) {
        const activeTabId = getActiveTabId();
        const iframe = getTabIframe(activeTabId);
        if (!iframe || !iframe.contentWindow) {
            if (typeof layui !== 'undefined') {
                layui.use(['layer'], function() {
                    layui.layer.msg('当前标签页不可导航');
                });
            }
            return;
        }

        try {
            if (direction === 'back') {
                iframe.contentWindow.history.back();
            } else if (direction === 'forward') {
                iframe.contentWindow.history.forward();
            }
        } catch (error) {
            console.warn('当前标签页历史导航失败:', error);
            if (typeof layui !== 'undefined') {
                layui.use(['layer'], function() {
                    layui.layer.msg('当前页面不支持此操作');
                });
            }
        }
    }
    
    // 菜单点击事件处理 - 使用原生JavaScript实现，避免jQuery和LayUI的冲突
    function handleMenuClick(e) {
        // 检查是否点击的是菜单链接
        const target = e.target.closest('.layui-nav a');
        if (!target) {
            return;
        }
        
        // 获取链接URL
        const url = target.getAttribute('href');
        
        // 检查是否是有子菜单的父菜单
        const hasSubmenu = target.parentElement.classList.contains('layui-nav-item') &&
                          target.parentElement.querySelector('.layui-nav-child');
        const menuUrl = target.getAttribute('data-menu-url') || url;
        
        // 如果没有真实地址，就保留 LayUI 的展开/收起行为
        if (!url || url === '#' || (url === 'javascript:;' && (!menuUrl || menuUrl === 'javascript:;'))) {
            // 不阻止默认行为，让LayUI内置菜单展开逻辑正常工作
            return;
        }
        
        // 阻止默认行为和事件冒泡，只处理实际的导航链接
        e.preventDefault();
        e.stopPropagation();
        
        // 登出链接直接跳转
        if (url === '/logout/') {
            localStorage.removeItem('layuiTabs');
            localStorage.removeItem('activeTabId');
            localStorage.removeItem('lastLoginTime');
            window.location.href = url;
            return;
        }
        
        // 检查是否已经加载了LayUI
        if (typeof layui === 'undefined') {
            console.error('LayUI未加载，无法处理菜单点击');
            return;
        }
        
        // 使用LayUI的element模块处理标签页
        layui.use(['element'], function() {
            const element = layui.element;
            
            // 获取菜单标题
            const title = target.textContent.trim();
            const openUrl = menuUrl || url;
            const id = buildTabId(openUrl, title);
            
            // 检查标签页容器是否存在
            const tabContainer = document.querySelector('.layui-tab[lay-filter="main-tab"]');
            if (!tabContainer) {
                console.error('未找到标签页容器');
                return;
            }
            
            // 检查标签页是否已存在
            const tabTitleContainer = tabContainer.querySelector('.layui-tab-title');
            const existingTab = tabTitleContainer.querySelector(`[lay-id="${id}"]`);
            
            // 如果标签页不存在，创建新标签页
            if (!existingTab) {
                // 创建标签页标题
                const tabTitle = document.createElement('li');
                tabTitle.setAttribute('lay-id', id);
                tabTitle.innerHTML = `${title}<i class="layui-icon layui-icon-close layui-unselect layui-tab-close"></i>`;
                tabTitleContainer.appendChild(tabTitle);
                
                // 创建标签页内容
                const tabContentContainer = tabContainer.querySelector('.layui-tab-content');
                const tabContent = document.createElement('div');
                tabContent.className = 'layui-tab-item';
                tabContent.setAttribute('lay-id', id);
                tabContent.innerHTML = `<iframe src="${openUrl}" style="width:100%;height:100%;border:none;"></iframe>`;
                tabContentContainer.appendChild(tabContent);
                
                // 渲染标签页
                element.render('tab');
            }
            
            // 切换到对应的标签页
            element.tabChange('main-tab', id);
            activateTab(id);
            
            // 保存标签页状态到localStorage
            saveTabs();
        });
    }
    
    // 添加标签页的全局函数
    window.addTab = function(url, title) {
        if (typeof layui === 'undefined') {
            console.error('LayUI未加载，无法添加标签页');
            window.location.href = url;
            return;
        }
        
        layui.use(['element'], function() {
            const element = layui.element;
            
            // 生成标签页ID
            const id = buildTabId(url, title);
            
            // 检查标签页容器是否存在
            const tabContainer = document.querySelector('.layui-tab[lay-filter="main-tab"]');
            if (!tabContainer) {
                console.error('未找到标签页容器');
                window.location.href = url;
                return;
            }
            
            // 获取标签页标题和内容容器
            const tabTitleContainer = tabContainer.querySelector('.layui-tab-title');
            const tabContentContainer = tabContainer.querySelector('.layui-tab-content');
            
            // 检查标签页是否已存在
            const existingTab = tabTitleContainer.querySelector(`[lay-id="${id}"]`);
            
            if (!existingTab) {
                // 创建标签页标题
                const tabTitle = document.createElement('li');
                tabTitle.setAttribute('lay-id', id);
                tabTitle.innerHTML = `${title}<i class="layui-icon layui-icon-close layui-unselect layui-tab-close"></i>`;
                tabTitleContainer.appendChild(tabTitle);
                
                // 创建标签页内容
                const tabContent = document.createElement('div');
                tabContent.className = 'layui-tab-item';
                tabContent.setAttribute('lay-id', id);
                tabContent.innerHTML = `<iframe src="${url}" style="width:100%;height:100%;border:none;"></iframe>`;
                tabContentContainer.appendChild(tabContent);
                
                // 渲染标签页
                element.render('tab');
            }
            
            // 切换到对应的标签页
            element.tabChange('main-tab', id);
            activateTab(id);
            
            // 保存标签页状态
            saveTabs();
        });
    };

    function openDashboardTab(forceReset) {
        if (forceReset) {
            localStorage.removeItem('layuiTabs');
            localStorage.removeItem('activeTabId');
        }
        window.addTab('/home/dashboard/', '工作台');
    }

    function normalizeSavedTabUrl(url) {
        if (!url) {
            return url;
        }

        try {
            const parsed = new URL(url, window.location.origin);
            if (parsed.pathname.replace(/\/+$/g, '') === '/disk/permission/manage') {
                parsed.pathname = '/disk/permission/';
            }
            return parsed.pathname + parsed.search + parsed.hash;
        } catch (error) {
            return url.replace('/disk/permission/manage/', '/disk/permission/');
        }
    }
    
    // 绑定菜单点击事件 - 使用事件委托，确保所有菜单层级都能正确处理
    // 绑定到document，使用捕获阶段，确保动态生成的菜单也能被处理
    document.addEventListener('click', handleMenuClick, true);
    
    // 初始化标签页系统
    function initTabSystem() {
        // 检查是否已经加载了LayUI
        if (typeof layui === 'undefined') {
            console.error('LayUI未加载，无法初始化标签页系统');
            return;
        }
        
        layui.use(['element'], function() {
            const element = layui.element;
            
            // 渲染导航和标签页
            element.render('nav');
            element.render('tab');
            
            // 获取标签页容器
            const tabTitleContainer = document.querySelector('.layui-tab-title');
            const tabContentContainer = document.querySelector('.layui-tab-content');
            
            if (tabTitleContainer && tabContentContainer) {
                // 直接获取当前页面加载时HTML中已有的标签页
                const existingTabs = tabTitleContainer.querySelectorAll('li');
                const forceOpenDashboard = sessionStorage.getItem(LOGIN_REDIRECT_MARKER_KEY) === '1';
                
                // 如果有已存在的标签页，保存它们到localStorage
                // 这是为了处理第一次访问系统时的情况
                if (existingTabs.length > 0) {
                    // 只在localStorage中没有保存的标签页时才保存
                    if (!localStorage.getItem('layuiTabs')) {
                        saveTabs();
                    }
                    if (forceOpenDashboard) {
                        sessionStorage.removeItem(LOGIN_REDIRECT_MARKER_KEY);
                        openDashboardTab(true);
                    }
                } else {
                    // 从localStorage恢复标签页
                    const savedTabs = JSON.parse(localStorage.getItem('layuiTabs') || '[]');
                    const activeTabId = localStorage.getItem('activeTabId');

                    if (forceOpenDashboard) {
                        sessionStorage.removeItem(LOGIN_REDIRECT_MARKER_KEY);
                        openDashboardTab(true);
                        return;
                    }
                    
                    // 恢复保存的标签页
                    savedTabs.forEach(tab => {
                        const normalizedUrl = normalizeSavedTabUrl(tab.url);
                        // 创建标签页标题
                        const tabTitle = document.createElement('li');
                        tabTitle.setAttribute('lay-id', tab.id);
                        tabTitle.innerHTML = `${tab.title}<i class="layui-icon layui-icon-close layui-unselect layui-tab-close"></i>`;
                        tabTitleContainer.appendChild(tabTitle);
                        
                        // 创建标签页内容
                        const tabContent = document.createElement('div');
                        tabContent.className = 'layui-tab-item';
                        tabContent.setAttribute('lay-id', tab.id);
                        tabContent.innerHTML = `<iframe src="${normalizedUrl}" style="width:100%;height:100%;border:none;"></iframe>`;
                        tabContentContainer.appendChild(tabContent);
                    });
                    
                    // 渲染标签页
                    element.render('tab');
                    
                    // 切换到对应的标签页
                    let targetTabId = null;
                    
                    // 优先使用保存的activeTabId
                    if (activeTabId) {
                        // 检查保存的activeTabId是否存在于当前标签页列表中
                        const tabExists = document.querySelector(`[lay-id="${activeTabId}"]`);
                        if (tabExists) {
                            targetTabId = activeTabId;
                        }
                    }
                    
                    // 如果没有有效的targetTabId，使用第一个标签页
                    if (!targetTabId && tabTitleContainer.children.length > 0) {
                        const firstTab = tabTitleContainer.firstElementChild;
                        targetTabId = firstTab.getAttribute('lay-id');
                    }
                    
                    // 如果有有效的targetTabId，切换到目标标签页
                    if (targetTabId) {
                        element.tabChange('main-tab', targetTabId);
                        activateTab(targetTabId);
                    } else {
                        // 首次登录且没有任何已保存标签时，默认打开工作台
                        openDashboardTab(false);
                    }
                }
            }
        });
    }
    
    // 初始化右键菜单
    function initContextMenu() {
        let currentTabId = null;
        
        // 获取右键菜单元素
        const contextMenu = document.getElementById('tab-contextmenu');
        if (!contextMenu) {
            return;
        }
        
        // 右键点击标签页标题显示菜单
        document.addEventListener('contextmenu', function(e) {
            const tabTitle = e.target.closest('.layui-tab-title li');
            if (!tabTitle) {
                // 点击其他区域隐藏菜单
                contextMenu.style.display = 'none';
                return;
            }
            
            e.preventDefault();
            currentTabId = tabTitle.getAttribute('lay-id');
            
            // 显示菜单
            contextMenu.style.left = e.pageX + 'px';
            contextMenu.style.top = e.pageY + 'px';
            contextMenu.style.display = 'block';
        });
        
        // 点击其他区域隐藏菜单
        document.addEventListener('click', function() {
            contextMenu.style.display = 'none';
        });
        
        // 刷新当前标签
        const refreshTabBtn = document.getElementById('refresh-tab');
        if (refreshTabBtn) {
            refreshTabBtn.addEventListener('click', function() {
                if (currentTabId) {
                    const iframe = document.querySelector(`div[lay-id="${currentTabId}"] iframe`);
                    if (iframe) {
                        // 使用更可靠的刷新方法，兼容所有浏览器
                        iframe.contentWindow.location.reload(true);
                    }
                }
                contextMenu.style.display = 'none';
            });
        }
        
        // 关闭当前标签
        const closeTabBtn = document.getElementById('close-tab');
        if (closeTabBtn) {
            closeTabBtn.addEventListener('click', function() {
                closeTabById(currentTabId);
                contextMenu.style.display = 'none';
            });
        }
        
        // 关闭其他标签
        const closeOtherTabsBtn = document.getElementById('close-other-tabs');
        if (closeOtherTabsBtn) {
            closeOtherTabsBtn.addEventListener('click', function() {
                closeOtherTabs(currentTabId);
                contextMenu.style.display = 'none';
            });
        }
        
        // 关闭所有标签
        const closeAllTabsBtn = document.getElementById('close-all-tabs');
        if (closeAllTabsBtn) {
            closeAllTabsBtn.addEventListener('click', function() {
                closeAllTabs();
                contextMenu.style.display = 'none';
            });
        }
    }
    
    // 修复标签页关闭按钮功能
    function fixTabCloseButtons() {
        // 为所有标签页关闭按钮添加点击事件处理
        document.addEventListener('click', function(e) {
            const closeBtn = e.target.closest('.layui-tab-close');
            if (closeBtn) {
                e.preventDefault();
                e.stopPropagation();
                
                // 获取对应的标签页ID
                const tabTitle = closeBtn.closest('.layui-tab-title li');
                if (tabTitle) {
                    const tabId = tabTitle.getAttribute('lay-id');
                    closeTabById(tabId);
                }
            }
        }, true);
    }

    function initTabNavigationButtons() {
        const backBtn = document.getElementById('current-tab-back');
        const forwardBtn = document.getElementById('current-tab-forward');

        if (backBtn) {
            backBtn.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                navigateCurrentTab('back');
            });
        }

        if (forwardBtn) {
            forwardBtn.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                navigateCurrentTab('forward');
            });
        }
    }
    
    // 保存当前标签页状态到localStorage
    function saveTabs() {
        if (typeof layui === 'undefined') {
            return;
        }
        
        const tabTitleContainer = document.querySelector('.layui-tab-title');
        if (!tabTitleContainer) {
            return;
        }
        
        const tabTitles = tabTitleContainer.querySelectorAll('li');
        const tabs = [];
        
        // 遍历所有当前存在的标签页
        tabTitles.forEach(title => {
            const id = title.getAttribute('lay-id');
            const tabContent = document.querySelector(`.layui-tab-content [lay-id="${id}"] iframe`);
            if (tabContent) {
                const url = tabContent.getAttribute('src');
                // 正确获取标签页标题文本，移除关闭按钮图标和多余空格
                const titleText = title.textContent.replace(/\s*\[.+\]\s*/g, '').replace(/\s*×\s*/g, '').trim();
                tabs.push({
                    id: id,
                    title: titleText,
                    url: url
                });
            }
        });
        
        // 保存到localStorage
        localStorage.setItem('layuiTabs', JSON.stringify(tabs));
        
        // 同时保存当前激活的标签页ID
        const activeTab = document.querySelector('.layui-tab-title li.layui-this');
        if (activeTab) {
            const activeTabId = activeTab.getAttribute('lay-id');
            localStorage.setItem('activeTabId', activeTabId);
        }
    }
    
    // 初始化标签页系统
    initTabSystem();
    
    // 初始化右键菜单
    initContextMenu();
    
    // 修复标签页关闭按钮功能
    fixTabCloseButtons();

    // 初始化当前标签页前进/后退按钮
    initTabNavigationButtons();
    
    // 监听LayUI标签页切换事件，保存当前激活标签页
    if (typeof layui !== 'undefined') {
        layui.use(['element'], function() {
            const element = layui.element;
            
            // 监听标签页切换事件
            element.on('tab(main-tab)', function(data) {
                const activeTabId = this.getAttribute('lay-id');
                localStorage.setItem('activeTabId', activeTabId);
                saveTabs();
            });
            
            // 监听标签页删除事件
            element.on('tabDelete(main-tab)', function(data) {
                saveTabs();
            });
        });
    }
    
    // 监听页面卸载事件，在刷新前保存当前激活标签页ID
    window.addEventListener('beforeunload', function() {
        // 保存当前激活的标签页ID
        const activeTab = document.querySelector('.layui-tab-title li.layui-this');
        if (activeTab) {
            const activeTabId = activeTab.getAttribute('lay-id');
            localStorage.setItem('activeTabId', activeTabId);
            // 同时保存标签页状态
            saveTabs();
        }
    });
});

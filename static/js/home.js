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

    function shouldForceRefreshTab(url) {
        if (!url) {
            return false;
        }

        try {
            const parsed = new URL(url, window.location.origin);
            const normalizedPath = parsed.pathname.replace(/\/+$/g, '') || '/';
            return normalizedPath === '/contract/ai/review/list';
        } catch (error) {
            return String(url).replace(/\/+$/g, '') === '/contract/ai/review/list';
        }
    }

    function buildIframeSrc(url) {
        if (!url) {
            return url;
        }

        try {
            const parsed = new URL(url, window.location.origin);
            if (shouldForceRefreshTab(parsed.pathname + parsed.search + parsed.hash)) {
                parsed.searchParams.set('_ts', Date.now().toString());
            }
            return parsed.pathname + parsed.search + parsed.hash;
        } catch (error) {
            if (!shouldForceRefreshTab(url)) {
                return url;
            }
            const separator = String(url).indexOf('?') >= 0 ? '&' : '?';
            return `${url}${separator}_ts=${Date.now()}`;
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

    function getQuickMenuIconCandidates(menu) {
        const title = menu && menu.title ? menu.title : '';
        const iconBase = '/static/img/icon/';
        const encodeFilename = name => name.split('/').map(part => encodeURIComponent(part)).join('/');
        const buildUrl = fileName => iconBase + encodeFilename(fileName);
        const defaultIcon = (typeof window._quickMenuDefaultIcon === 'string' && window._quickMenuDefaultIcon)
            ? window._quickMenuDefaultIcon
            : '功能节点.png';

        const rules = Array.isArray(window._quickMenuIconRules) ? window._quickMenuIconRules : [];
        const resolveFallbackIcon = t => {
            const matchedRule = rules.find(rule => rule.keywords.some(keyword => t.includes(keyword)));
            return matchedRule ? matchedRule.icon : defaultIcon;
        };

        const directPng = title ? buildUrl(`${title}.png`) : '';
        const directSvg = title ? buildUrl(`${title}.svg`) : '';
        const fallbackIcon = buildUrl(resolveFallbackIcon(title));
        const defaultIconUrl = buildUrl(defaultIcon);

        return [...new Set([directPng, directSvg, fallbackIcon, defaultIconUrl].filter(Boolean))];
    }

    function getQuickMenuIconSrc(menu) {
        const candidates = getQuickMenuIconCandidates(menu);
        return candidates[0] || '/static/img/icon/' + encodeURIComponent('功能节点.png');
    }

    function applyQuickMenuIconFallback(icon, menu) {
        if (!icon) {
            return;
        }

        const candidates = getQuickMenuIconCandidates(menu);
        const defaultIconUrl = candidates[candidates.length - 1] || '/static/img/icon/' + encodeURIComponent('功能节点.png');

        icon.dataset.iconIndex = '0';
        icon.dataset.iconCandidates = JSON.stringify(candidates);
        icon.onerror = function() {
            const candidateList = JSON.parse(this.dataset.iconCandidates || '[]');
            const nextIndex = Number(this.dataset.iconIndex || 0) + 1;

            if (nextIndex < candidateList.length) {
                this.dataset.iconIndex = String(nextIndex);
                this.src = candidateList[nextIndex];
                return;
            }

            this.onerror = null;
            this.src = defaultIconUrl;
        };
        icon.src = candidates[0] || defaultIconUrl;
    }

    function recordQuickMenuUsage(menuId) {
        if (!menuId) {
            return;
        }

        fetch('/home/menu-usage/', {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': typeof getCsrfToken === 'function' ? getCsrfToken() : ''
            },
            body: JSON.stringify({ menu_id: Number(menuId) })
        }).catch(error => {
            console.warn('记录常用菜单失败:', error);
        });
    }

    function toggleQuickMenuPin(menuId, isPinned) {
        if (!menuId) {
            return;
        }

        fetch('/home/quick-menus/pin/', {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': typeof getCsrfToken === 'function' ? getCsrfToken() : ''
            },
            body: JSON.stringify({
                menu_id: Number(menuId),
                is_pinned: Boolean(isPinned)
            })
        }).then(response => {
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            return response.json();
        }).then(() => {
            renderQuickMenus();
        }).catch(error => {
            console.warn('更新固定菜单失败:', error);
            if (typeof layui !== 'undefined') {
                layui.use(['layer'], function() {
                    layui.layer.msg('固定菜单更新失败');
                });
            }
        });
    }

    function buildQuickMenuItem(menu, options) {
        const item = document.createElement('a');
        item.className = 'quick-menu-item';
        item.href = 'javascript:;';
        item.setAttribute('data-menu-id', menu.id);
        item.setAttribute('data-menu-url', menu.src || '');
        item.setAttribute('data-menu-title', menu.title || '');
        item.setAttribute('title', menu.title || '');
        if (options && options.pinned) {
            item.classList.add('is-pinned');
        }

        const icon = document.createElement('img');
        icon.className = 'quick-menu-icon';
        icon.alt = '';
        icon.loading = 'lazy';
        applyQuickMenuIconFallback(icon, menu);

        const title = document.createElement('span');
        title.className = 'quick-menu-title';
        title.textContent = menu.title || '';

        const pinButton = document.createElement('button');
        pinButton.type = 'button';
        pinButton.className = 'quick-menu-pin';
        pinButton.title = options && options.pinned ? '取消固定' : '固定菜单';
        pinButton.setAttribute('aria-label', pinButton.title);
        pinButton.innerHTML = `<i class="layui-icon ${options && options.pinned ? 'layui-icon-rate-solid' : 'layui-icon-rate'}"></i>`;
        pinButton.addEventListener('click', function(event) {
            event.preventDefault();
            event.stopPropagation();
            toggleQuickMenuPin(menu.id, !(options && options.pinned));
        });

        item.appendChild(icon);
        item.appendChild(title);
        item.appendChild(pinButton);

        item.addEventListener('click', function(event) {
            event.preventDefault();
            event.stopPropagation();
            if (menu.src) {
                recordQuickMenuUsage(menu.id);
                window.addTab(menu.src, menu.title || '');
            }
        });

        return item;
    }

    function renderQuickMenuList(container, menus, options) {
        if (!container) {
            return;
        }

        container.innerHTML = '';
        const safeMenus = Array.isArray(menus) ? menus : [];
        if (safeMenus.length === 0) {
            const empty = document.createElement('span');
            empty.className = 'quick-menu-empty';
            empty.textContent = options && options.emptyText ? options.emptyText : '暂无';
            container.appendChild(empty);
            _syncQuickMenuOverflowFade(container);
            return;
        }

        safeMenus.forEach(menu => {
            container.appendChild(buildQuickMenuItem(menu, options));
        });

        _syncQuickMenuOverflowFade(container);
    }

    function _syncQuickMenuOverflowFade(listEl) {
        if (!listEl) return;
        var group = listEl.closest('.quick-menu-group');
        if (!group) return;
        var hasOverflow = listEl.scrollWidth > listEl.clientWidth + 1;
        if (hasOverflow) {
            group.classList.add('has-overflow-fade');
        } else {
            group.classList.remove('has-overflow-fade');
        }
    }

    function renderQuickMenus() {
        const pinnedContainer = document.getElementById('pinnedQuickMenus');
        const frequentContainer = document.getElementById('frequentQuickMenus');
        if (!pinnedContainer || !frequentContainer) {
            return;
        }

        fetch('/home/quick-menus/', {
            method: 'GET',
            credentials: 'same-origin',
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        }).then(response => response.json()).then(payload => {
            renderQuickMenuList(pinnedContainer, payload.pinned_menus || [], {
                pinned: true,
                emptyText: '暂无固定菜单'
            });
            renderQuickMenuList(frequentContainer, payload.frequent_menus || [], {
                pinned: false,
                emptyText: '暂无常用菜单'
            });
        }).catch(error => {
            console.warn('加载常用菜单失败:', error);
            renderQuickMenuList(pinnedContainer, [], { pinned: true, emptyText: '暂无固定菜单' });
            renderQuickMenuList(frequentContainer, [], { pinned: false, emptyText: '暂无常用菜单' });
        });
    }

    function openQuickMenuManager() {
        if (typeof layui === 'undefined') return;
        layui.use(['layer'], function() {
            const layer = layui.layer;
            const loadIndex = layer.load(1);

            fetch('/home/quick-menus/', {
                method: 'GET',
                credentials: 'same-origin',
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            }).then(response => response.json()).then(payload => {
                layer.close(loadIndex);
                var pinnedMenus = payload.pinned_menus || [];
                var frequentMenus = payload.frequent_menus || [];
                var pinnedIds = {};
                pinnedMenus.forEach(function(m) { pinnedIds[m.id] = true; });

                var allMenus = pinnedMenus.slice();
                frequentMenus.forEach(function(m) {
                    if (!pinnedIds[m.id]) {
                        allMenus.push(m);
                        pinnedIds[m.id] = true;
                    }
                });

                if (allMenus.length === 0) {
                    layer.msg('当前没有可管理的菜单', { icon: 0 });
                    return;
                }

                var rows = [];
                allMenus.forEach(function(menu) {
                    var isPinned = pinnedMenus.some(function(p) { return p.id === menu.id; });
                    var iconSrc = getQuickMenuIconSrc(menu);
                    rows.push(
                        '<div class="qm-manager-row" style="display:flex;align-items:center;gap:10px;padding:8px 16px;">',
                        '<img src="' + iconSrc + '" style="width:20px;height:20px;object-fit:contain;" alt="" onerror="this.src=\'/static/img/icon/' + encodeURIComponent('功能节点.png') + '\'">',
                        '<span style="flex:1;font-size:14px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">' + (menu.title || '') + '</span>',
                        '<button type="button" class="qm-manager-pin-btn" data-menu-id="' + menu.id + '" data-pinned="' + isPinned + '" style="flex:0 0 auto;border:1px solid #e2e8f0;border-radius:6px;padding:4px 10px;font-size:12px;cursor:pointer;background:' + (isPinned ? '#fef3c7' : '#f8fafc') + ';color:' + (isPinned ? '#92400e' : '#475569') + ';">' + (isPinned ? '已固定' : '固定') + '</button>',
                        '</div>'
                    );
                });

                layer.open({
                    type: 1,
                    title: '管理固定菜单',
                    area: ['440px', '480px'],
                    content: '<div style="max-height:420px;overflow-y:auto;padding:8px 0;">' + rows.join('') + '</div>',
                    btn: ['关闭'],
                    yes: function(index) { layer.close(index); },
                    success: function(layero) {
                        var root = layero && layero[0] ? layero[0] : layero;
                        if (!root || typeof root.querySelectorAll !== 'function') {
                            return;
                        }
                        root.querySelectorAll('.qm-manager-pin-btn').forEach(function(btn) {
                            btn.addEventListener('click', function(e) {
                                e.stopPropagation();
                                var menuId = this.getAttribute('data-menu-id');
                                var currentlyPinned = this.getAttribute('data-pinned') === 'true';
                                toggleQuickMenuPin(menuId, !currentlyPinned);
                                this.setAttribute('data-pinned', String(!currentlyPinned));
                                this.textContent = !currentlyPinned ? '已固定' : '固定';
                                this.style.background = !currentlyPinned ? '#fef3c7' : '#f8fafc';
                                this.style.color = !currentlyPinned ? '#92400e' : '#475569';
                            });
                        });
                    }
                });
            }).catch(function(error) {
                layer.close(loadIndex);
                console.warn('加载菜单管理失败:', error);
                layer.msg('加载失败，请重试', { icon: 2 });
            });
        });
    }

    window.openQuickMenuManager = openQuickMenuManager;
    
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
        
        // 有子菜单的父级项交给 LayUI 自己处理展开/收起
        if (hasSubmenu) {
            return;
        }

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

            const menuId = target.getAttribute('data-menu-id');
            recordQuickMenuUsage(menuId);
            
            // 保存标签页状态到localStorage
            saveTabs();
        });
    }

    document.addEventListener('click', function(e) {
        const quickMenuItem = e.target.closest('.quick-menu-item');
        if (!quickMenuItem) {
            return;
        }

        const pinButton = e.target.closest('.quick-menu-pin');
        if (pinButton) {
            return;
        }

        const menuId = quickMenuItem.getAttribute('data-menu-id');
        const menuUrl = quickMenuItem.getAttribute('data-menu-url');
        const menuTitle = quickMenuItem.getAttribute('data-menu-title') || quickMenuItem.textContent.trim();

        if (!menuUrl || menuUrl === 'javascript:;') {
            return;
        }

        e.preventDefault();
        e.stopPropagation();
        recordQuickMenuUsage(menuId);
        window.addTab(menuUrl, menuTitle);
    }, true);
    
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
                tabContent.innerHTML = `<iframe src="${buildIframeSrc(url)}" style="width:100%;height:100%;border:none;"></iframe>`;
                tabContentContainer.appendChild(tabContent);
                
                // 渲染标签页
                element.render('tab');
            } else if (shouldForceRefreshTab(url)) {
                const existingIframe = getTabIframe(id);
                if (existingIframe) {
                    existingIframe.setAttribute('src', buildIframeSrc(url));
                }
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
                        tabContent.innerHTML = `<iframe src="${buildIframeSrc(normalizedUrl)}" style="width:100%;height:100%;border:none;"></iframe>`;
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
    renderQuickMenus();

    const quickMenuManageBtn = document.getElementById('quickMenuManageBtn');
    if (quickMenuManageBtn) {
        quickMenuManageBtn.addEventListener('click', function(event) {
            event.preventDefault();
            event.stopPropagation();
            openQuickMenuManager();
        });
    }
    
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

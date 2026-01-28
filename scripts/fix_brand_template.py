"""
修复brand_list.html模板标签问题
"""
import os

# 读取brand_list.html
with open('templates/asset/brand_list.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 新的完整HTML头部
new_header = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>资产品牌管理</title>
    <link rel="stylesheet" href="/static/layui/css/layui.css">
    <link rel="stylesheet" href="/static/css/font-awesome.min.css">
    
    <style>
        :root {
            --primary: #3b82f6;
            --primary-hover: #2563eb;
            --success: #10b981;
            --danger: #ef4444;
            --warning: #f59e0b;
            --gray-50: #f9fafb;
            --gray-100: #f3f4f6;
            --gray-200: #e5e7eb;
            --gray-300: #d1d5db;
            --gray-400: #9ca3af;
            --gray-500: #6b7280;
            --gray-600: #4b5563;
            --gray-700: #374151;
            --gray-800: #1f2937;
            --gray-900: #111827;
            --border-radius: 8px;
            --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
            --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
            --transition: all 0.3s ease;
        }
        
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: var(--gray-50);
            min-height: 100vh;
            color: var(--gray-800);
        }
        
        .brand-container { padding: 0; }
        
        .page-header {
            margin-bottom: 0;
            padding: 20px 24px;
            background: linear-gradient(135deg, var(--primary), var(--primary-hover));
            color: white;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        
        .page-header h2 {
            font-size: 18px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .page-header h2 i { font-size: 24px; }
        
        .btn-add {
            background: white;
            color: var(--primary);
            border: none;
            border-radius: var(--border-radius);
            padding: 0 20px;
            height: 40px;
            font-weight: 500;
            cursor: pointer;
            transition: var(--transition);
            box-shadow: 0 2px 4px rgba(59, 130, 246, 0.2);
            display: flex;
            align-items: center;
            gap: 6px;
        }
        
        .btn-add:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 8px rgba(59, 130, 246, 0.3);
            color: var(--primary-hover);
        }
        
        .toolbar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: white;
            padding: 16px 20px;
            border-radius: var(--border-radius);
            box-shadow: var(--shadow-sm);
            margin-bottom: 20px;
            flex-wrap: wrap;
            gap: 12px;
        }
        
        .search-group {
            display: flex;
            align-items: center;
            gap: 12px;
            flex: 1;
            min-width: 300px;
        }
        
        .search-input {
            position: relative;
            flex: 1;
            min-width: 200px;
        }
        
        .search-input .layui-input {
            padding-left: 40px;
            height: 40px;
            border-radius: var(--border-radius);
            border: 1px solid var(--gray-200);
            transition: var(--transition);
        }
        
        .search-input .layui-input:focus {
            border-color: var(--primary);
            box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
        }
        
        .search-input i {
            position: absolute;
            left: 14px;
            top: 50%;
            transform: translateY(-50%);
            color: var(--gray-400);
        }
        
        .toolbar-right { display: flex; gap: 10px; }
        
        .btn {
            padding: 10px 20px;
            border-radius: var(--border-radius);
            font-size: 14px;
            cursor: pointer;
            transition: var(--transition);
            display: inline-flex;
            align-items: center;
            gap: 6px;
            border: none;
        }
        
        .btn-search {
            background: linear-gradient(135deg, var(--primary), var(--primary-hover));
            color: white;
            box-shadow: 0 2px 4px rgba(59, 130, 246, 0.2);
        }
        
        .btn-search:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 8px rgba(59, 130, 246, 0.3);
            color: white;
        }
        
        .btn-reset {
            background: white;
            color: var(--gray-700);
            border: 1px solid var(--gray-300);
        }
        
        .btn-reset:hover {
            border-color: var(--gray-400);
            color: var(--gray-700);
        }
        
        .btn-edit {
            padding: 6px 12px;
            font-size: 12px;
            background: var(--primary);
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            transition: var(--transition);
        }
        
        .btn-edit:hover { background: var(--primary-hover); color: white; }
        
        .btn-delete {
            padding: 6px 12px;
            font-size: 12px;
            background: white;
            color: var(--danger);
            border: 1px solid var(--danger);
            border-radius: 4px;
            cursor: pointer;
            transition: var(--transition);
        }
        
        .btn-delete:hover { background: var(--danger); color: white; }
        
        .table-container {
            background: white;
            border-radius: var(--border-radius);
            box-shadow: var(--shadow-md);
            overflow: hidden;
            margin-bottom: 20px;
        }
        
        .table-container .layui-table { margin: 0; }
        .table-container .layui-table th {
            background: var(--gray-50);
            font-weight: 600;
            color: var(--gray-700);
        }
        .table-container .layui-table td { color: var(--gray-700); }
        
        .brand-row {
            transition: var(--transition);
            animation: fadeIn 0.3s ease forwards;
            opacity: 0;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .brand-row:hover { background-color: var(--gray-50); }
        
        .brand-row code {
            background: var(--gray-100);
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 12px;
            color: var(--primary);
        }
        
        .status-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 500;
        }
        
        .status-badge.active {
            background: rgba(16, 185, 129, 0.1);
            color: #059669;
        }
        
        .status-badge.inactive {
            background: rgba(107, 114, 128, 0.1);
            color: #6b7280;
        }
        
        .action-buttons { display: flex; gap: 8px; }
        
        .pagination-container {
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: white;
            padding: 16px 20px;
            border-radius: var(--border-radius);
            box-shadow: var(--shadow-sm);
            margin-bottom: 20px;
        }
        
        .pagination-info { font-size: 14px; color: var(--gray-600); }
        .pagination-controls { display: flex; gap: 8px; }
        
        .pagination-btn {
            padding: 8px 16px;
            border: 1px solid var(--gray-300);
            background: white;
            border-radius: var(--border-radius);
            font-size: 14px;
            cursor: pointer;
            transition: var(--transition);
            color: var(--gray-700);
        }
        
        .pagination-btn:hover:not(:disabled) {
            border-color: var(--primary);
            color: var(--primary);
        }
        
        .pagination-btn.active {
            background: var(--primary);
            border-color: var(--primary);
            color: white;
        }
        
        .pagination-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        
        .pagination-jump {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-left: 16px;
        }
        
        .pagination-jump input {
            width: 60px;
            padding: 8px;
            border: 1px solid var(--gray-300);
            border-radius: var(--border-radius);
            text-align: center;
        }
        
        .pagination-jump button {
            padding: 8px 16px;
            background: var(--primary);
            color: white;
            border: none;
            border-radius: var(--border-radius);
            cursor: pointer;
        }
        
        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: var(--gray-500);
        }
        
        .empty-state i {
            font-size: 64px;
            margin-bottom: 16px;
            opacity: 0.5;
        }
        
        .loading-spinner {
            width: 40px;
            height: 40px;
            border: 3px solid var(--gray-200);
            border-top-color: var(--primary);
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        @media (max-width: 768px) {
            .toolbar { flex-direction: column; align-items: stretch; }
            .search-group { flex-direction: column; min-width: auto; }
            .pagination-container { flex-direction: column; align-items: stretch; }
            .pagination-controls { flex-wrap: wrap; justify-content: center; }
        }
    </style>
</head>
<body>
    <div id="brand-app" class="brand-container">
        <div class="page-header">
            <h2><i class="fa fa-copyright"></i> 资产品牌管理</h2>
            <button class="btn-add" onclick="openAddForm()">
                <i class="fa fa-plus"></i> 新增品牌
            </button>
        </div>
        
        <div style="padding: 20px; position: relative;">
            <div class="toolbar">
                <div class="search-group">
                    <div class="search-input">
                        <i class="fa fa-search"></i>
                        <input type="text" v-model="searchKeyword" placeholder="搜索品牌编码或名称" 
                            class="layui-input" @keyup.enter="handleSearch">
                    </div>
                    <div class="toolbar-right">
                        <button class="btn btn-search" @click="handleSearch">
                            <i class="fa fa-search"></i> 搜索
                        </button>
                        <button class="btn btn-reset" @click="resetSearch">
                            <i class="fa fa-refresh"></i> 重置
                        </button>
                    </div>
                </div>
            </div>
            
            <div class="table-container" style="position: relative;">
                <table class="layui-table">
                    <thead>
                        <tr>
                            <th style="width: 80px;">序号</th>
                            <th>品牌编码</th>
                            <th>品牌名称</th>
                            <th style="width: 100px;">状态</th>
                            <th style="width: 150px;">创建时间</th>
                            <th style="width: 150px;">操作</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr v-if="loading">
                            <td colspan="6" style="padding: 40px; text-align: center;">
                                <div class="loading-spinner"></div>
                                <p style="margin-top: 10px; color: #999;">加载中...</p>
                            </td>
                        </tr>
                        <tr v-else-if="brands.length === 0">
                            <td colspan="6">
                                <div class="empty-state">
                                    <i class="fa fa-inbox"></i>
                                    <p>暂无数据</p>
                                </div>
                            </td>
                        </tr>
                        <template v-else>
                            <tr v-for="(brand, index) in brands" :key="brand.id" class="brand-row" :style="{ animationDelay: index * 0.05 + 's' }">
                                <td>[[ currentPage === 1 ? index + 1 : (currentPage - 1) * pageSize + index + 1 ]]</td>
                                <td><code>[[ brand.code ]]</code></td>
                                <td>[[ brand.name ]]</td>
                                <td>
                                    <span class="status-badge" :class="brand.is_active ? 'active' : 'inactive'">
                                        [[ brand.is_active ? '启用' : '停用' ]]
                                    </span>
                                </td>
                                <td>[[ brand.create_time ]]</td>
                                <td>
                                    <div class="action-buttons">
                                        <button class="btn-edit" :data-id="brand.id" onclick="openEditForm(this)">
                                            <i class="fa fa-pencil"></i> 编辑
                                        </button>
                                        <button class="btn-delete" :data-id="brand.id" :data-name="brand.name" onclick="showDeleteConfirm(this)">
                                            <i class="fa fa-trash"></i> 删除
                                        </button>
                                    </div>
                                </td>
                            </tr>
                        </template>
                    </tbody>
                </table>
            </div>
            
            <div class="pagination-container" v-if="brands.length > 0">
                <div class="pagination-info">
                    共 <strong>[[ totalCount ]]</strong> 条数据，每页 <strong>[[ pageSize ]]</strong> 条，当前第 <strong>[[ currentPage ]]</strong>/<strong>[[ totalPages ]]</strong> 页
                </div>
                <div class="pagination-controls">
                    <button class="pagination-btn" :disabled="currentPage === 1" @click="changePage(1)">
                        <i class="fa fa-step-backward"></i>
                    </button>
                    <button class="pagination-btn" :disabled="currentPage === 1" @click="changePage(currentPage - 1)">
                        <i class="fa fa-chevron-left"></i>
                    </button>
                    
                    <button v-for="page in displayPages" :key="page" 
                        class="pagination-btn" 
                        :class="{ active: page === currentPage }"
                        @click="changePage(page)">
                        [[ page ]]
                    </button>
                    
                    <button class="pagination-btn" :disabled="currentPage === totalPages" @click="changePage(currentPage + 1)">
                        <i class="fa fa-chevron-right"></i>
                    </button>
                    <button class="pagination-btn" :disabled="currentPage === totalPages" @click="changePage(totalPages)">
                        <i class="fa fa-step-forward"></i>
                    </button>
                    
                    <div class="pagination-jump">
                        <input type="number" v-model="jumpPage" min="1" :max="totalPages" @keyup.enter="jumpToPage">
                        <button @click="jumpToPage">跳转</button>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script src="/static/js/vue.global.prod.js"></script>
    <script src="/static/layui/layui.js"></script>
    
    <script>
        const { createApp, ref, computed, onMounted } = Vue;
        
        const BrandApp = {
            setup() {
                const brands = ref([]);
                const loading = ref(false);
                const searchKeyword = ref('');
                const currentPage = ref(1);
                const pageSize = ref(10);
                const totalCount = ref(0);
                const jumpPage = ref(1);
                
                const totalPages = computed(() => Math.ceil(totalCount.value / pageSize.value) || 1);
                
                const displayPages = computed(() => {
                    const pages = [];
                    const total = totalPages.value;
                    const current = currentPage.value;
                    
                    let start = Math.max(1, current - 2);
                    let end = Math.min(total, current + 2);
                    
                    if (current <= 3) { end = Math.min(5, total); }
                    if (current >= total - 2) { start = Math.max(1, total - 4); }
                    
                    for (let i = start; i <= end; i++) { pages.push(i); }
                    return pages;
                });
                
                const loadBrands = async () => {
                    loading.value = true;
                    try {
                        const params = new URLSearchParams({
                            keyword: searchKeyword.value,
                            page: currentPage.value,
                            page_size: pageSize.value
                        });
                        
                        const response = await fetch("/system/admin_office/asset/brand/data/?" + params);
                        const data = await response.json();
                        
                        if (data.code === 0) {
                            brands.value = data.data;
                            totalCount.value = data.count;
                        }
                    } catch (error) {
                        console.error("加载品牌数据失败:", error);
                    } finally {
                        loading.value = false;
                    }
                };
                
                const handleSearch = () => {
                    currentPage.value = 1;
                    loadBrands();
                };
                
                const resetSearch = () => {
                    searchKeyword.value = "";
                    currentPage.value = 1;
                    loadBrands();
                };
                
                const changePage = (page) => {
                    if (page >= 1 && page <= totalPages.value) {
                        currentPage.value = page;
                        loadBrands();
                    }
                };
                
                const jumpToPage = () => {
                    const page = parseInt(jumpPage.value);
                    if (page >= 1 && page <= totalPages.value) {
                        changePage(page);
                    }
                };
                
                onMounted(() => {
                    loadBrands();
                });
                
                return {
                    brands, loading, searchKeyword, currentPage, pageSize, totalCount,
                    totalPages, displayPages, jumpPage,
                    loadBrands, handleSearch, resetSearch, changePage, jumpToPage
                };
            },
            delimiters: ["[[", "]]"]
        };
        
        const app = createApp(BrandApp);
        app.mount("#brand-app");
        
        function openAddForm() {
            layer.open({
                type: 2,
                title: "<i class='fa fa-plus-circle'></i> 新增资产品牌",
                shadeClose: false,
                shade: 0.3,
                maxmin: true,
                area: ["80%", "100%"],
                offset: "r",
                content: "/system/admin_office/asset/brand/create/",
                success: function(layero) {
                    layero.css({"right": "0", "top": "0", "height": "100%", "margin": "0", "padding": "0"});
                    var iframe = layero.find("iframe");
                    if (iframe.length) { iframe.css({"height": "100%", "width": "100%"}); }
                },
                end: function() { window.location.reload(); }
            });
        }
        
        function openEditForm(button) {
            const id = button.getAttribute("data-id");
            layer.open({
                type: 2,
                title: "<i class='fa fa-pencil'></i> 编辑资产品牌",
                shadeClose: false,
                shade: 0.3,
                maxmin: true,
                area: ["80%", "100%"],
                offset: "r",
                content: "/system/admin_office/asset/brand/" + id + "/update/",
                success: function(layero) {
                    layero.css({"right": "0", "top": "0", "height": "100%", "margin": "0", "padding": "0"});
                    var iframe = layero.find("iframe");
                    if (iframe.length) { iframe.css({"height": "100%", "width": "100%"}); }
                },
                end: function() { window.location.reload(); }
            });
        }
        
        function showDeleteConfirm(button) {
            const id = button.getAttribute("data-id");
            const name = button.getAttribute("data-name");
            layer.open({
                type: 1,
                title: "<i class='fa fa-exclamation-triangle' style='color: #f59e0b;'>确认删除</i>",
                area: ["400px", "auto"],
                content: "<div style='padding: 24px;'><p style='margin-bottom: 16px; color: #6b7280;'>确定要删除品牌 \"" + name + "\" 吗？删除后无法恢复。</p><div style='text-align: right;'><button class='btn-cancel' onclick='layer.closeAll()' style='padding: 10px 24px; background: white; border: 1px solid #d1d5db; border-radius: 8px; cursor: pointer; margin-right: 12px;'>取消</button><button class='btn-confirm' onclick=\"executeDelete('" + id + "')\" style='padding: 10px 24px; background: #ef4444; color: white; border: none; border-radius: 8px; cursor: pointer;'>确定</button></div></div>"
            });
        }
        
        function executeDelete(id) {
            fetch("/system/admin_office/asset/brand/" + id + "/delete/", {
                method: "POST",
                headers: { "X-CSRFToken": getCsrfToken() }
            })
            .then(response => response.json())
            .then(data => {
                layer.closeAll();
                if (data.code === 0) {
                    layer.msg("删除成功", { icon: 1 });
                    setTimeout(() => window.location.reload(), 1000);
                } else {
                    layer.msg(data.msg || "删除失败", { icon: 2 });
                }
            })
            .catch(error => {
                console.error("删除失败:", error);
                layer.msg("删除失败", { icon: 2 });
            });
        }
        
        function getCsrfToken() {
            const name = "csrftoken";
            const value = "; " + document.cookie;
            const parts = value.split("; " + name + "=");
            if (parts.length === 2) return parts.pop().split(";").shift();
            return "";
        }
    </script>
</body>
</html>'''

# 替换Django模板标签
new_content = content.replace("{% load static %}", new_header)
new_content = new_content.replace("{% endblock %}", "")
new_content = new_content.replace("{% endblock %}", "")

# 写回文件
with open('templates/asset/brand_list.html', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("brand_list.html 修复完成!")
print("文件大小:", os.path.getsize('templates/asset/brand_list.html'), "bytes")

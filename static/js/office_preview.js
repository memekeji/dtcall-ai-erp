// 统一的Office文档预览组件
function standardOfficePreview(data) {
    // 构建文档信息区域
    var infoText = '<div style="margin-bottom:15px;padding:10px;background:#f5f7fa;border-radius:4px;">' +
                 '<div style="color:#606266;margin-bottom:5px;"><strong>文档信息</strong></div>' +
                 '<div style="color:#909399;font-size:12px;">' +
                 '文件名: ' + escapeHtml(data.name || '未知') + ' | ' +
                 '类型: ' + (data.office_type || '未知') +
                 '</div></div>';
    
    layui.use(['layer'], function() {
        var layer = layui.layer;
        
        // 统一的样式定义
        const style = `
            <style>
                .office-preview-content h3 {
                    color: #333;
                    font-size: 18px;
                    margin-bottom: 20px;
                    border-bottom: 2px solid #1E9FFF;
                    padding-bottom: 10px;
                }
                .word-content {
                    font-size: 14px;
                    line-height: 1.8;
                    color: #333;
                    white-space: pre-wrap;
                    word-wrap: break-word;
                    background: white;
                    padding: 20px;
                    border-radius: 4px;
                    box-shadow: 0 1px 2px rgba(0,0,0,0.1);
                }
                .layui-table {
                    background: white;
                }
                .office-preview-empty {
                    text-align: center;
                    color: #999;
                    padding: 40px 20px;
                }
            </style>
        `;
        
        // 构建预览内容（直接显示第一个预览选项）
        var contentHtml = '';
        
        if (data.preview_options && data.preview_options.length > 0) {
            // 获取第一个预览选项
            var firstOption = data.preview_options[0];
            
            switch(firstOption.type) {
                case 'text':
                    contentHtml += '<div style="padding:15px;">' +
                                 '<div class="word-content">' + escapeHtml(firstOption.content || '') + '</div>' +
                                 '</div>';
                    break;
                    
                case 'table':
                    // Excel表格预览
                    if (firstOption.sheets && firstOption.sheets.length > 0) {
                        contentHtml += '<div style="padding:15px;overflow:auto;max-height:400px;">';
                        
                        // 显示第一个工作表的数据
                        var firstSheet = firstOption.sheets[0];
                        if (firstSheet.data && firstSheet.data.length > 0) {
                            contentHtml += '<table class="layui-table" style="margin:0;">';
                            
                            // 生成表头
                            if (firstSheet.hasHeader) {
                                contentHtml += '<thead><tr>';
                                firstSheet.data[0].forEach(function(cell, colIndex) {
                                    contentHtml += '<th>' + escapeHtml(cell || '') + '</th>';
                                });
                                contentHtml += '</tr></thead><tbody>';
                                
                                // 生成表格数据（从第二行开始）
                                for (let i = 1; i < firstSheet.data.length; i++) {
                                    contentHtml += '<tr>';
                                    firstSheet.data[i].forEach(function(cell) {
                                        contentHtml += '<td>' + escapeHtml(cell || '') + '</td>';
                                    });
                                    contentHtml += '</tr>';
                                }
                            } else {
                                // 直接显示所有数据
                                contentHtml += '<tbody>';
                                firstSheet.data.forEach(function(row) {
                                    contentHtml += '<tr>';
                                    row.forEach(function(cell) {
                                        contentHtml += '<td>' + escapeHtml(cell || '') + '</td>';
                                    });
                                    contentHtml += '</tr>';
                                });
                            }
                            
                            contentHtml += '</tbody></table>';
                        }
                        
                        contentHtml += '</div>';
                    }
                    break;
                    
                case 'slides':
                    // PowerPoint幻灯片预览
                    if (firstOption.slides) {
                        contentHtml += '<div style="padding:15px;max-height:400px;overflow:auto;">';
                        
                        firstOption.slides.forEach(function(slide) {
                            contentHtml += '<div style="margin-bottom:20px;padding:15px;border:1px solid #eee;border-radius:4px;">' +
                                         '<h3 style="margin:0 0 10px 0;color:#333;">' + escapeHtml(slide.title || '') + '</h3>' +
                                         '<div style="color:#666;line-height:1.6;">' + escapeHtml(slide.content || '') + '</div>' +
                                         '</div>';
                        });
                        
                        contentHtml += '</div>';
                    }
                    break;
                    
                default:
                    // 其他类型内容
                    contentHtml += '<div style="padding:15px;">' +
                                 '<div class="word-content">' + escapeHtml(firstOption.content || '') + '</div>' +
                                 '</div>';
            }
        } else {
            // 没有预览选项时显示默认内容
            contentHtml = '<div class="office-preview-empty">该文档暂无可用预览内容</div>';
        }
        
        var fullContent = style + contentHtml;
        
        // 打开预览弹窗
        layer.open({
            type: 1,
            title: '文档预览：' + (data.name || '未知文件名'),
            shade: 0.8,
            area: ['80%', '100%'],
            content: '<div style="padding:20px;">' + 
                     infoText +
                     fullContent + 
                     '</div>',
            btn: ['下载原文件', '关闭'],
            btn1: function(index) {
                if (typeof downloadFile === 'function') {
                    downloadFile(data.file_id || data.fileId);
                } else {
                    window.location.href = '/adm/disk/file/download/' + (data.file_id || data.fileId) + '/';
                }
                return false; // 不关闭弹窗
            },
            success: function(layero, index) {
                // 设置弹窗样式
                $(layero).find('.layui-layer-content').css({
                    'overflow-y': 'auto',
                    'background-color': '#f9f9f9'
                });
            }
        });
    });
}

// HTML转义函数
function escapeHtml(text) {
    if (!text) return '';
    var map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, function(m) { return map[m]; });
}
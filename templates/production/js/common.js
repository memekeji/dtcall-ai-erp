/**
 * 生产管理模块公共JavaScript函数
 * 减少重复代码，提供统一的交互处理
 */

layui.define(['layer', 'form'], function(exports){
    var layer = layui.layer;
    var form = layui.form;
    
    var ProductionCommon = {
        // 通用删除确认
        deleteConfirm: function(url, id, callback) {
            layer.confirm('确定要删除这条记录吗？', {
                icon: 3,
                title: '确认删除'
            }, function(index) {
                $.post(url, {id: id, csrfmiddlewaretoken: getCsrfToken()}, function(res) {
                    if (res.success) {
                        layer.msg('删除成功', {icon: 1});
                        if (callback) callback();
                        else setTimeout(function() { location.reload(); }, 500);
                    } else {
                        layer.msg(res.error || '删除失败', {icon: 2});
                    }
                }).fail(function() {
                    layer.msg('删除失败', {icon: 2});
                });
                layer.close(index);
            });
        },
        
        // 通用表单提交
        formSubmit: function(formElement, callback) {
            $(formElement).on('submit', function(e) {
                e.preventDefault();
                var btn = $(this).find('button[type="submit"]');
                btn.prop('disabled', true).addClass('layui-btn-disabled');
                
                $.ajax({
                    url: $(this).attr('action'),
                    type: $(this).attr('method') || 'POST',
                    data: $(this).serialize(),
                    success: function(res) {
                        if (res.success) {
                            layer.msg('操作成功', {icon: 1});
                            if (callback) callback(res);
                            else if (res.redirect) location.href = res.redirect;
                            else location.reload();
                        } else {
                            layer.msg(res.error || '操作失败', {icon: 2});
                        }
                    },
                    error: function() {
                        layer.msg('操作失败', {icon: 2});
                    },
                    complete: function() {
                        btn.prop('disabled', false).removeClass('layui-btn-disabled');
                    }
                });
            });
        },
        
        // 打开弹窗表单
        openForm: function(title, url, width, height, callback) {
            width = width || 600;
            height = height || 500;
            
            layer.open({
                type: 2,
                title: title,
                area: [width + 'px', height + 'px'],
                content: url,
                end: function() {
                    if (callback) callback();
                }
            });
        },
        
        // 表格操作按钮渲染
        renderActions: function(d, options) {
            var actions = [];
            options = options || {};
            
            if (options.view !== false) {
                actions.push('<a class="layui-btn layui-btn-xs" onclick="ProductionCommon.viewRecord(' + d.id + ', \'' + options.viewUrl + '\')">查看</a>');
            }
            if (options.edit !== false) {
                actions.push('<a class="layui-btn layui-btn-xs layui-btn-normal" onclick="ProductionCommon.editRecord(' + d.id + ', \'' + options.editUrl + '\')">编辑</a>');
            }
            if (options.delete !== false) {
                actions.push('<a class="layui-btn layui-btn-xs layui-btn-danger" onclick="ProductionCommon.deleteRecord(' + d.id + ', \'' + options.deleteUrl + '\')">删除</a>');
            }
            
            return actions.join(' ');
        },
        
        // 查看记录
        viewRecord: function(id, url) {
            ProductionCommon.openForm('查看详情', url + '?id=' + id, 800, 600);
        },
        
        // 编辑记录
        editRecord: function(id, url) {
            ProductionCommon.openForm('编辑', url + '?id=' + id, 800, 600);
        },
        
        // 删除记录
        deleteRecord: function(id, url) {
            ProductionCommon.deleteConfirm(url, id);
        },
        
        // 批量删除
        batchDelete: function(url, ids, callback) {
            if (!ids || ids.length === 0) {
                layer.msg('请先选择要删除的记录', {icon: 3});
                return;
            }
            
            layer.confirm('确定要删除选中的 ' + ids.length + ' 条记录吗？', {
                icon: 3,
                title: '批量删除'
            }, function(index) {
                $.post(url, {
                    ids: JSON.stringify(ids),
                    csrfmiddlewaretoken: getCsrfToken()
                }, function(res) {
                    if (res.success) {
                        layer.msg('批量删除成功', {icon: 1});
                        if (callback) callback();
                        else setTimeout(function() { location.reload(); }, 500);
                    } else {
                        layer.msg(res.error || '批量删除失败', {icon: 2});
                    }
                }).fail(function() {
                    layer.msg('批量删除失败', {icon: 2});
                });
                layer.close(index);
            });
        },
        
        // 状态切换
        toggleStatus: function(url, id, callback) {
            $.post(url, {id: id, csrfmiddlewaretoken: getCsrfToken()}, function(res) {
                if (res.success) {
                    layer.msg('状态更新成功', {icon: 1});
                    if (callback) callback();
                    else setTimeout(function() { location.reload(); }, 500);
                } else {
                    layer.msg(res.error || '状态更新失败', {icon: 2});
                }
            }).fail(function() {
                layer.msg('状态更新失败', {icon: 2});
            });
        },
        
        // 显示加载动画
        showLoading: function(elem) {
            return layer.load(2, {
                shade: [0.3, '#fff'],
                content: '正在加载...',
                success: function(layero, index) {
                    if (elem) {
                        $(layero).css('top', $(elem).offset().top + 100);
                    }
                }
            });
        },
        
        // 关闭加载动画
        closeLoading: function(index) {
            layer.close(index);
        }
    };
    
    // 获取CSRF Token
    function getCsrfToken() {
        return $('input[name="csrfmiddlewaretoken"]').val() || 
               $.cookie('csrftoken') || '';
    }
    
    // 初始化表格选择功能
    ProductionCommon.initTableCheckbox = function(tableId) {
        $('#' + tableId + ' thead tr').append('<th><input type="checkbox" id="checkAll"/></th>');
        $('#' + tableId + ' tbody tr').each(function() {
            $(this).find('td:first').before('<td><input type="checkbox" class="row-check"/></td>');
        });
        
        $('#checkAll').on('change', function() {
            $('.row-check').prop('checked', this.checked);
        });
        
        form.render('checkbox');
    };
    
    // 获取选中的行ID
    ProductionCommon.getSelectedIds = function(tableId) {
        var ids = [];
        $('#' + tableId + ' tbody .row-check:checked').each(function() {
            var row = $(this).closest('tr');
            var index = row.data('index');
            ids.push(index);
        });
        return ids;
    };
    
    exports('production_common', ProductionCommon);
});

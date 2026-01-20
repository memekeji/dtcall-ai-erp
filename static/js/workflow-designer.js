/**
 * DTCall Workflow Designer - Modern Frontend Solution
 * Achieve interaction experience comparable to Dify and Coze platforms
 * 
 * Technical Architecture:
 * - Native JavaScript + Modular Design
 * - SVG/Canvas Hybrid Rendering
 * - Virtualized List Optimization
 * - Complete Undo/Redo System
 */

(function(global) {
    'use strict';

    const WorkflowDesigner = {
        version: '2.0.0',
        config: {
            nodeWidth: 220,
            nodeMinHeight: 80,
            portRadius: 6,
            connectionStrokeWidth: 2,
            gridSize: 20,
            snapToGrid: true,
            animateConnections: true,
            undoLimit: 50
        },
        
        state: {
            nodes: new Map(),
            connections: new Map(),
            selectedNodes: new Set(),
            selectedConnections: new Set(),
            history: [],
            historyIndex: -1,
            scale: 1,
            offsetX: 0,
            offsetY: 0,
            isDragging: false,
            isConnecting: false,
            connectionStartNode: null,
            connectionStartPort: null,
            tempConnectionPath: null,
            clipboard: null,
            modified: false
        },
        
        containers: {
            canvas: null,
            container: null,
            nodesLayer: null,
            connectionsLayer: null,
            tempLayer: null,
            toolPanel: null,
            propertyPanel: null
        },
        
        nodeTypes: {
            'start': { name: '开始', category: 'basic', icon: '▶', color: '#52c41a' },
            'end': { name: '结束', category: 'basic', icon: '◼', color: '#ff4d4f' },
            'data_input': { name: '数据输入', category: 'basic', icon: '↓', color: '#1890ff' },
            'data_output': { name: '数据输出', category: 'basic', icon: '↑', color: '#722ed1' },
            'ai_model': { name: 'AI模型', category: 'ai', icon: '🤖', color: '#fa8c16' },
            'ai_generation': { name: 'AI生成', category: 'ai', icon: '✨', color: '#eb2f96' },
            'ai_classification': { name: 'AI分类', category: 'ai', icon: '📊', color: '#13c2c2' },
            'ai_extraction': { name: 'AI信息提取', category: 'ai', icon: '🎯', color: '#f5222d' },
            'knowledge_retrieval': { name: '知识检索', category: 'ai', icon: '📚', color: '#2f54eb' },
            'intent_recognition': { name: '意图识别', category: 'ai', icon: '🎯', color: '#722ed1' },
            'sentiment_analysis': { name: '情感分析', category: 'ai', icon: '💭', color: '#eb2f96' },
            'condition': { name: '条件判断', category: 'logic', icon: '?', color: '#faad14' },
            'switch': { name: '多条件分支', category: 'logic', icon: '⇄', color: '#52c41a' },
            'loop': { name: '循环处理', category: 'logic', icon: '↻', color: '#722ed1' },
            'iterator': { name: '迭代器', category: 'logic', icon: '⟳', color: '#13c2c2' },
            'parallel': { name: '并行处理', category: 'logic', icon: '∥', color: '#13c2c2' },
            'api_call': { name: 'API调用', category: 'integration', icon: '🌐', color: '#1890ff' },
            'http_request': { name: 'HTTP请求', category: 'integration', icon: '🔗', color: '#1890ff' },
            'webhook': { name: 'Webhook', category: 'integration', icon: '🪝', color: '#eb2f96' },
            'code_execution': { name: '代码执行', category: 'integration', icon: '⚡', color: '#fa8c16' },
            'code_block': { name: '代码块', category: 'integration', icon: '{ }', color: '#fa8c16' },
            'tool_call': { name: '工具调用', category: 'integration', icon: '🔧', color: '#52c41a' },
            'database_query': { name: '数据库查询', category: 'integration', icon: '🗄️', color: '#2f54eb' },
            'message_queue': { name: '消息队列', category: 'integration', icon: '📨', color: '#13c2c2' },
            'variable_aggregation': { name: '变量聚合', category: 'data', icon: '⊕', color: '#2f54eb' },
            'parameter_aggregator': { name: '参数聚合', category: 'data', icon: '⊗', color: '#2f54eb' },
            'variable_assign': { name: '变量赋值', category: 'data', icon: '←', color: '#722ed1' },
            'data_transformation': { name: '数据转换', category: 'data', icon: '⇄', color: '#13c2c2' },
            'data_filter': { name: '数据过滤', category: 'data', icon: '🔍', color: '#13c2c2' },
            'data_aggregation': { name: '数据聚合', category: 'data', icon: '⊕', color: '#2f54eb' },
            'data_format': { name: '数据格式化', category: 'data', icon: '📋', color: '#faad14' },
            'text_processing': { name: '文本处理', category: 'data', icon: '📝', color: '#1890ff' },
            'template': { name: '模板渲染', category: 'data', icon: '📋', color: '#faad14' },
            'file_operation': { name: '文件操作', category: 'data', icon: '📁', color: '#722ed1' },
            'document_extractor': { name: '文档提取', category: 'data', icon: '📄', color: '#722ed1' },
            'image_processing': { name: '图片处理', category: 'data', icon: '🖼️', color: '#eb2f96' },
            'audio_processing': { name: '音频处理', category: 'data', icon: '🎵', color: '#52c41a' },
            'notification': { name: '通知', category: 'system', icon: '🔔', color: '#faad14' },
            'delay': { name: '延迟', category: 'system', icon: '⏱', color: '#8c8c8c' },
            'wait': { name: '等待', category: 'system', icon: '⏸', color: '#8c8c8c' },
            'scheduled_task': { name: '定时任务', category: 'system', icon: '⏰', color: '#722ed1' },
            'question_answer': { name: '问答交互', category: 'interaction', icon: '💬', color: '#52c41a' },
            'conversation_history': { name: '对话历史', category: 'interaction', icon: '📜', color: '#13c2c2' },
            'workflow_trigger': { name: '工作流触发', category: 'interaction', icon: '🚀', color: '#f5222d' }
        },
        
        validNodeTypes: null,
        
        init: function(containerId, options = {}) {
            const container = document.getElementById(containerId);
            if (!container) {
                console.error(`Container with id "${containerId}" not found`);
                return null;
            }
            
            this.config = { ...this.config, ...options };
            this.containers.container = container;
            
            this._createDOMStructure();
            this._bindEvents();
            this._initToolbar();
            this._loadDefaultWorkflow();
            
            console.log('Workflow Designer initialized successfully');
            return this;
        },
        
        isValidNodeType: function(nodeType) {
            return nodeType && nodeType in this.nodeTypes;
        },
        
        validateNode: function(node) {
            const errors = [];
            const nodeType = node.type;
            
            if (!nodeType) {
                errors.push('节点缺少type字段');
                return errors;
            }
            
            if (!this.isValidNodeType(nodeType)) {
                errors.push(`未知的节点类型: ${nodeType}`);
                errors.push(`允许的节点类型: ${Object.keys(this.nodeTypes).join(', ')}`);
                return errors;
            }
            
            const typeConfig = this.nodeTypes[nodeType];
            
            if (!node.name || node.name.trim() === '') {
                errors.push('节点名称不能为空');
            }
            
            if (typeof node.x !== 'number' || typeof node.y !== 'number') {
                errors.push('节点位置坐标必须为数字');
            }
            
            return errors;
        },
        
        _createDOMStructure: function() {
            const container = this.containers.container;
            container.innerHTML = '';
            container.className = 'workflow-designer';
            
            this.containers.toolPanel = this._createToolPanel();
            this.containers.canvas = this._createCanvas();
            this.containers.propertyPanel = this._createPropertyPanel();
            
            container.appendChild(this.containers.toolPanel);
            container.appendChild(this.containers.canvas);
            container.appendChild(this.containers.propertyPanel);
        },
        
        _createToolPanel: function() {
            const panel = document.createElement('div');
            panel.className = 'designer-tool-panel';
            panel.innerHTML = `
                <div class="panel-header">
                    <span class="panel-title">节点类型</span>
                </div>
                <div class="panel-content" id="node-type-list"></div>
            `;
            
            const nodeList = panel.querySelector('#node-type-list');
            const categories = {
                'basic': { name: '基础节点', order: 1 },
                'ai': { name: 'AI节点', order: 2 },
                'logic': { name: '逻辑控制', order: 3 },
                'integration': { name: '集成节点', order: 4 },
                'data': { name: '数据处理', order: 5 },
                'system': { name: '系统节点', order: 6 },
                'interaction': { name: '交互节点', order: 7 }
            };
            
            Object.entries(categories)
                .sort((a, b) => a[1].order - b[1].order)
                .forEach(([category, info]) => {
                    const group = document.createElement('div');
                    group.className = 'node-type-group';
                    group.innerHTML = `<div class="group-title">${info.name}</div>`;
                    
                    Object.entries(this.nodeTypes)
                        .filter(([type, config]) => config.category === category)
                        .forEach(([type, config]) => {
                            const item = document.createElement('div');
                            item.className = 'node-type-item';
                            item.dataset.nodeType = type;
                            item.draggable = true;
                            item.innerHTML = `
                                <span class="node-icon">${config.icon}</span>
                                <span class="node-name">${config.name}</span>
                            `;
                            group.appendChild(item);
                        });
                    
                    nodeList.appendChild(group);
                });
            
            return panel;
        },
        
        _createCanvas: function() {
            const canvas = document.createElement('div');
            canvas.className = 'designer-canvas';
            canvas.tabIndex = 0;
            
            canvas.innerHTML = `
                <div class="canvas-toolbar">
                    <button class="canvas-btn" data-action="zoom-in" title="放大 (Ctrl +)">
                        <span>＋</span>
                    </button>
                    <button class="canvas-btn" data-action="zoom-out" title="缩小 (Ctrl -)">
                        <span>－</span>
                    </button>
                    <button class="canvas-btn" data-action="zoom-reset" title="重置缩放 (Ctrl 0)">
                        <span>⊞</span>
                    </button>
                    <span class="zoom-indicator">100%</span>
                    <div class="canvas-divider"></div>
                    <button class="canvas-btn" data-action="undo" title="撤销 (Ctrl Z)" disabled>
                        <span>↶</span>
                    </button>
                    <button class="canvas-btn" data-action="redo" title="重做 (Ctrl Y)" disabled>
                        <span>↷</span>
                    </button>
                    <div class="canvas-divider"></div>
                    <button class="canvas-btn" data-action="delete" title="删除 (Delete)" disabled>
                        <span>🗑</span>
                    </button>
                    <button class="canvas-btn" data-action="select-all" title="全选 (Ctrl A)">
                        <span>☑</span>
                    </button>
                    <div class="canvas-divider"></div>
                    <button class="canvas-btn" data-action="execute" title="执行工作流">
                        <span>▶</span>
                    </button>
                    <button class="canvas-btn" data-action="debug" title="调试模式">
                        <span>🐛</span>
                    </button>
                </div>
                <div class="canvas-container">
                    <svg class="connections-layer" id="connections-layer"></svg>
                    <div class="nodes-layer" id="nodes-layer"></div>
                    <svg class="temp-layer" id="temp-layer"></svg>
                </div>
                <div class="minimap" id="minimap">
                    <div class="minimap-viewport"></div>
                </div>
                <div class="canvas-background" id="canvas-background"></div>
            `;
            
            this.containers.nodesLayer = canvas.querySelector('#nodes-layer');
            this.containers.connectionsLayer = canvas.querySelector('#connections-layer');
            this.containers.tempLayer = canvas.querySelector('#temp-layer');
            
            return canvas;
        },
        
        _createPropertyPanel: function() {
            const panel = document.createElement('div');
            panel.className = 'designer-property-panel';
            panel.innerHTML = `
                <div class="panel-header">
                    <span class="panel-title">属性配置</span>
                </div>
                <div class="panel-content" id="property-content">
                    <div class="no-selection">
                        <div class="no-selection-icon">◇</div>
                        <div class="no-selection-text">选择一个节点以编辑属性</div>
                    </div>
                </div>
            `;
            
            return panel;
        },
        
        _initToolbar: function() {
            const toolbar = this.containers.canvas.querySelector('.canvas-toolbar');
            toolbar.addEventListener('click', (e) => {
                const btn = e.target.closest('.canvas-btn');
                if (btn && !btn.disabled) {
                    const action = btn.dataset.action;
                    this._handleToolbarAction(action);
                }
            });
        },
        
        _handleToolbarAction: function(action) {
            switch (action) {
                case 'zoom-in':
                    this._setZoom(this.state.scale * 1.2);
                    break;
                case 'zoom-out':
                    this._setZoom(this.state.scale / 1.2);
                    break;
                case 'zoom-reset':
                    this._setZoom(1);
                    break;
                case 'undo':
                    this._undo();
                    break;
                case 'redo':
                    this._redo();
                    break;
                case 'delete':
                    this._deleteSelected();
                    break;
                case 'select-all':
                    this._selectAll();
                    break;
                case 'execute':
                    this._executeWorkflow();
                    break;
                case 'debug':
                    this._toggleDebugMode();
                    break;
            }
        },
        
        _bindEvents: function() {
            const container = this.containers.container;
            const canvas = this.containers.canvas;
            const nodeList = this.containers.toolPanel.querySelector('#node-type-list');
            const canvasContainer = canvas.querySelector('.canvas-container');
            
            nodeList.addEventListener('dragstart', (e) => {
                if (e.target.classList.contains('node-type-item')) {
                    e.dataTransfer.setData('nodeType', e.target.dataset.nodeType);
                    e.dataTransfer.effectAllowed = 'copy';
                }
            });
            
            canvas.addEventListener('dragover', (e) => {
                e.preventDefault();
                e.dataTransfer.dropEffect = 'copy';
            });
            
            canvas.addEventListener('drop', (e) => {
                e.preventDefault();
                const nodeType = e.dataTransfer.getData('nodeType');
                if (nodeType && this.nodeTypes[nodeType]) {
                    const rect = canvasContainer.getBoundingClientRect();
                    const scrollLeft = canvasContainer.scrollLeft || 0;
                    const scrollTop = canvasContainer.scrollTop || 0;
                    const x = (e.clientX - rect.left + scrollLeft - this.state.offsetX) / this.state.scale;
                    const y = (e.clientY - rect.top + scrollTop - this.state.offsetY) / this.state.scale;
                    this._addNode(nodeType, x, y);
                }
            });
            
            canvas.addEventListener('keydown', (e) => {
                this._handleKeydown(e);
            });
            
            canvasContainer.addEventListener('mousedown', (e) => {
                if (e.target === canvasContainer || e.target.classList.contains('canvas-background')) {
                    if (e.button === 0) {
                        this._startSelectionBox(e);
                    } else if (e.button === 1) {
                        e.preventDefault();
                        this._startPan(e);
                    }
                } else if (e.target === canvas || e.target.classList.contains('canvas-background')) {
                    this._clearSelection();
                }
            });
            
            canvasContainer.addEventListener('wheel', (e) => {
                this._handleWheel(e);
            }, { passive: false });
            
            window.addEventListener('mousemove', (e) => {
                this._handleMouseMove(e);
            });
            
            window.addEventListener('mouseup', (e) => {
                this._handleMouseUp(e);
            });
            
            window.addEventListener('resize', () => {
                this._updateMinimap();
            });
        },
        
        _startPan: function(e) {
            this.state.isPanning = true;
            this.state.panStartX = e.clientX;
            this.state.panStartY = e.clientY;
            this.state.panOffsetX = this.state.offsetX;
            this.state.panOffsetY = this.state.offsetY;
            this.containers.canvas.classList.add('panning');
            this.containers.canvas.style.cursor = 'grabbing';
        },
        
        _startSelectionBox: function(e) {
            this.state.isSelecting = true;
            this.state.selectionStartX = e.clientX;
            this.state.selectionStartY = e.clientY;
            
            let selectionBox = this.containers.canvas.querySelector('.selection-box');
            if (!selectionBox) {
                selectionBox = document.createElement('div');
                selectionBox.className = 'selection-box';
                this.containers.canvas.querySelector('.canvas-container').appendChild(selectionBox);
            }
            selectionBox.style.display = 'block';
            selectionBox.style.left = e.clientX + 'px';
            selectionBox.style.top = e.clientY + 'px';
            selectionBox.style.width = '0px';
            selectionBox.style.height = '0px';
        },
        
        _updateSelectionBox: function(e) {
            if (!this.state.isSelecting) return;
            
            const selectionBox = this.containers.canvas.querySelector('.selection-box');
            if (!selectionBox) return;
            
            const canvasContainer = this.containers.canvas.querySelector('.canvas-container');
            const rect = canvasContainer.getBoundingClientRect();
            
            const startX = this.state.selectionStartX - rect.left;
            const startY = this.state.selectionStartY - rect.top;
            const currentX = e.clientX - rect.left;
            const currentY = e.clientY - rect.top;
            
            const left = Math.min(startX, currentX);
            const top = Math.min(startY, currentY);
            const width = Math.abs(currentX - startX);
            const height = Math.abs(currentY - startY);
            
            selectionBox.style.left = left + 'px';
            selectionBox.style.top = top + 'px';
            selectionBox.style.width = width + 'px';
            selectionBox.style.height = height + 'px';
            
            this.state.selectionBox = { left, top, width, height };
        },
        
        _endSelectionBox: function() {
            if (!this.state.isSelecting) return;
            
            const selectionBox = this.containers.canvas.querySelector('.selection-box');
            if (selectionBox) {
                selectionBox.style.display = 'none';
            }
            
            if (this.state.selectionBox && this.state.selectionBox.width > 5 && this.state.selectionBox.height > 5) {
                this._selectNodesInBox();
            }
            
            this.state.isSelecting = false;
            this.state.selectionBox = null;
        },
        
        _selectNodesInBox: function() {
            const box = this.state.selectionBox;
            if (!box) return;
            
            const canvasContainer = this.containers.canvas.querySelector('.canvas-container');
            const scrollLeft = canvasContainer.scrollLeft || 0;
            const scrollTop = canvasContainer.scrollTop || 0;
            
            this.state.nodes.forEach((node, nodeId) => {
                const nodeEl = this.containers.nodesLayer.querySelector(`[data-node-id="${nodeId}"]`);
                if (nodeEl) {
                    const nodeLeft = node.x;
                    const nodeTop = node.y;
                    const nodeRight = node.x + this.config.nodeWidth;
                    const nodeBottom = node.y + 80;
                    
                    const boxLeft = (box.left - scrollLeft + this.state.offsetX) / this.state.scale;
                    const boxTop = (box.top - scrollTop + this.state.offsetY) / this.state.scale;
                    const boxRight = boxLeft + box.width / this.state.scale;
                    const boxBottom = boxTop + box.height / this.state.scale;
                    
                    if (nodeLeft >= boxLeft && nodeRight <= boxRight && 
                        nodeTop >= boxTop && nodeBottom <= boxBottom) {
                        this.state.selectedNodes.add(nodeId);
                        nodeEl.classList.add('selected');
                    }
                }
            });
            
            this._updateToolbarButtons();
        },
        
        _handleKeydown: function(e) {
            const key = e.key.toLowerCase();
            const ctrl = e.ctrlKey || e.metaKey;
            
            if (ctrl && key === 'z') {
                e.preventDefault();
                if (e.shiftKey) {
                    this._redo();
                } else {
                    this._undo();
                }
            } else if (ctrl && key === 'y') {
                e.preventDefault();
                this._redo();
            } else if (ctrl && key === 'a') {
                e.preventDefault();
                this._selectAll();
            } else if (key === 'delete' || key === 'backspace') {
                if (document.activeElement.tagName !== 'INPUT' && 
                    document.activeElement.tagName !== 'TEXTAREA') {
                    e.preventDefault();
                    this._deleteSelected();
                }
            } else if (ctrl && key === '=') {
                e.preventDefault();
                this._setZoom(this.state.scale * 1.2);
            } else if (ctrl && key === '-') {
                e.preventDefault();
                this._setZoom(this.state.scale / 1.2);
            } else if (ctrl && key === '0') {
                e.preventDefault();
                this._setZoom(1);
            } else if (key === 'escape') {
                this._cancelConnection();
                this._clearSelection();
            }
        },
        
        _handleMouseMove: function(e) {
            if (this.state.isPanning) {
                const canvas = this.containers.canvas;
                const canvasContainer = canvas.querySelector('.canvas-container');
                const deltaX = e.clientX - this.state.panStartX;
                const deltaY = e.clientY - this.state.panStartY;
                
                this.state.offsetX = this.state.panOffsetX + deltaX;
                this.state.offsetY = this.state.panOffsetY + deltaY;
                
                const transformStyle = `scale(${this.state.scale}) translate(${this.state.offsetX}px, ${this.state.offsetY}px)`;
                
                if (this.containers.nodesLayer) {
                    this.containers.nodesLayer.style.transform = transformStyle;
                }
                
                if (this.containers.connectionsLayer) {
                    this.containers.connectionsLayer.style.transform = transformStyle;
                }
                
                if (this.containers.tempLayer) {
                    this.containers.tempLayer.style.transform = transformStyle;
                }
                
                this._updateMinimap();
                return;
            }
            
            if (this.state.isSelecting) {
                this._updateSelectionBox(e);
                return;
            }
            
            if (this.state.isDragging && this.state.dragNode) {
                const canvas = this.containers.canvas;
                const canvasContainer = canvas.querySelector('.canvas-container');
                const rect = canvasContainer.getBoundingClientRect();
                const scrollLeft = canvasContainer.scrollLeft || 0;
                const scrollTop = canvasContainer.scrollTop || 0;
                
                const x = (e.clientX - rect.left + scrollLeft - this.state.offsetX) / this.state.scale;
                const y = (e.clientY - rect.top + scrollTop - this.state.offsetY) / this.state.scale;
                
                const snappedX = this.config.snapToGrid 
                    ? Math.round(x / this.config.gridSize) * this.config.gridSize 
                    : x;
                const snappedY = this.config.snapToGrid 
                    ? Math.round(y / this.config.gridSize) * this.config.gridSize 
                    : y;
                
                const node = this.state.dragNode;
                node.x = snappedX;
                node.y = snappedY;
                
                const el = this.containers.nodesLayer.querySelector(`[data-node-id="${node.id}"]`);
                if (el) {
                    el.style.left = node.x + 'px';
                    el.style.top = node.y + 'px';
                }
                
                this._updateConnectedConnections(node.id);
                this._updateMinimap();
            }
            
            if (this.state.isConnecting) {
                this._updateTempConnection(e);
            }
        },
        
        _handleMouseUp: function(e) {
            if (this.state.isPanning) {
                this.state.isPanning = false;
                this.containers.canvas.classList.remove('panning');
                this.containers.canvas.style.cursor = '';
                return;
            }
            
            if (this.state.isSelecting) {
                this._endSelectionBox();
                return;
            }
            
            if (this.state.isDragging && this.state.dragNode) {
                const node = this.state.dragNode;
                const el = this.containers.nodesLayer.querySelector(`[data-node-id="${node.id}"]`);
                if (el) {
                    el.classList.remove('dragging');
                }
                
                this._saveHistory();
                this.state.modified = true;
                
                this.state.isDragging = false;
                this.state.dragNode = null;
            }
            
            if (this.state.isConnecting) {
                this._cancelConnection();
            }
        },
        
        _handleWheel: function(e) {
            e.preventDefault();
            
            const delta = e.deltaY > 0 ? 0.9 : 1.1;
            const canvas = this.containers.canvas;
            const canvasContainer = canvas.querySelector('.canvas-container');
            const rect = canvasContainer.getBoundingClientRect();
            
            const mouseX = e.clientX - rect.left;
            const mouseY = e.clientY - rect.top;
            
            const scrollLeft = canvasContainer.scrollLeft || 0;
            const scrollTop = canvasContainer.scrollTop || 0;
            
            const newScale = Math.max(0.1, Math.min(3, this.state.scale * delta));
            
            const scaleRatio = newScale / this.state.scale;
            
            this.state.offsetX = mouseX - (mouseX - this.state.offsetX - scrollLeft) * scaleRatio - scrollLeft;
            this.state.offsetY = mouseY - (mouseY - this.state.offsetY - scrollTop) * scaleRatio - scrollTop;
            
            this._setZoom(newScale);
        },
        
        _addNode: function(nodeType, x, y) {
            const nodeId = this._generateId('node');
            const typeConfig = this.nodeTypes[nodeType];
            
            const node = {
                id: nodeId,
                type: nodeType,
                name: typeConfig.name,
                x: x - this.config.nodeWidth / 2,
                y: y - 40,
                config: this._getDefaultNodeConfig(nodeType),
                status: 'pending'
            };
            
            this.state.nodes.set(nodeId, node);
            this._renderNode(node);
            this._saveHistory();
            this.state.modified = true;
            
            return node;
        },
        
        _getDefaultNodeConfig: function(nodeType) {
            const configs = {
                'start': { output_variables: [] },
                'end': { input_variable: '' },
                'data_input': { input_data: '', output_variable: 'input' },
                'data_output': { input_variable: '', output_type: 'result' },
                'ai_model': { model_id: '', prompt: '', output_variable: 'ai_result' },
                'ai_generation': { model_id: '', content_type: 'text', output_variable: 'generated' },
                'ai_classification': { model_id: '', categories: [], output_variable: 'category' },
                'ai_extraction': { model_id: '', extraction_schema: {}, output_variable: 'extraction' },
                'knowledge_retrieval': { knowledge_base_id: '', query_variable: '', top_k: 5 },
                'intent_recognition': { input_variable: '', intents: [], output_intent: 'intent' },
                'sentiment_analysis': { input_variable: '', output_variable: 'sentiment' },
                'condition': { condition_variable: '', condition_type: 'if_else', expressions: [] },
                'switch': { condition_variable: '', cases: [] },
                'loop': { loop_type: 'for', iterable_variable: '', max_iterations: 100 },
                'iterator': { iterable_variable: '', item_variable: 'item' },
                'parallel': { tasks: [], max_concurrent: 3 },
                'delay': { delay_seconds: 5 },
                'wait': { wait_type: 'time', duration: 60 },
                'api_call': { url: '', method: 'GET', headers: {}, body: '' },
                'http_request': { url: '', method: 'GET', timeout: 30, output_variable: 'response' },
                'webhook': { webhook_url: '', method: 'POST' },
                'code_execution': { code: '', input_variables: [], output_variables: [] },
                'code_block': { code: '', language: 'python' },
                'tool_call': { tool_name: '', parameters: {} },
                'database_query': { query: '', output_variable: 'query_result' },
                'message_queue': { queue_name: '', action: 'send', message: '' },
                'variable_aggregation': { source_variables: [], aggregation_type: 'object' },
                'parameter_aggregator': { parameters: [], output_variable: 'aggregated' },
                'variable_assign': { variable_name: '', value: '' },
                'data_transformation': { transformation_type: 'map', mapping: {} },
                'data_filter': { filter_conditions: [], output_variable: 'filtered' },
                'data_aggregation': { group_by: [], aggregations: [] },
                'data_format': { format_type: 'json', template: '' },
                'text_processing': { operation: 'trim', text: '' },
                'template': { template: '', variables: {} },
                'file_operation': { operation: 'read', file_path: '', output_variable: 'file_content' },
                'document_extractor': { file_variable: '', output_variable: 'content' },
                'image_processing': { operation: 'resize', width: 0, height: 0 },
                'audio_processing': { operation: 'transcribe', output_variable: 'transcript' },
                'notification': { notification_type: 'toast', message: '' },
                'scheduled_task': { cron_expression: '', action: '' },
                'question_answer': { question: '', answer_variable: 'user_answer' },
                'conversation_history': { max_messages: 10, output_variable: 'history' },
                'workflow_trigger': { trigger_type: 'manual', workflow_id: '' }
            };
            
            return configs[nodeType] || {};
        },
        
        _renderNode: function(node) {
            const nodeType = node.type;
            
            if (!nodeType) {
                console.error('节点缺少type字段:', node);
                return null;
            }
            
            if (!this.isValidNodeType(nodeType)) {
                console.error('未知的节点类型:', nodeType, '允许的类型:', Object.keys(this.nodeTypes));
                return null;
            }
            
            const typeConfig = this.nodeTypes[nodeType];
            const el = document.createElement('div');
            el.className = 'workflow-node';
            el.dataset.nodeId = node.id;
            el.dataset.nodeType = nodeType;
            el.style.left = node.x + 'px';
            el.style.top = node.y + 'px';
            
            el.innerHTML = `
                <div class="node-header" style="border-left: 3px solid ${typeConfig.color}">
                    <span class="node-icon">${typeConfig.icon}</span>
                    <span class="node-name">${node.name}</span>
                    <div class="node-actions">
                        <button class="node-btn" data-action="config" title="配置">⚙</button>
                        <button class="node-btn" data-action="delete" title="删除">×</button>
                    </div>
                </div>
                <div class="node-content" id="content-${node.id}">
                    ${this._getNodeContentPreview(node)}
                </div>
                <div class="node-status" id="status-${node.id}"></div>
                <div class="node-ports">
                    <div class="port in-port" data-port="in" data-node="${node.id}"></div>
                    <div class="port out-port" data-port="out" data-node="${node.id}"></div>
                </div>
            `;
            
            el.addEventListener('mousedown', (e) => {
                if (e.target.classList.contains('port')) return;
                if (e.target.classList.contains('node-btn')) {
                    this._handleNodeButtonClick(e, node);
                    return;
                }
                
                e.stopPropagation();
                this._selectNode(node.id, e.shiftKey);
                this.state.isDragging = true;
                this.state.dragNode = node;
                el.classList.add('dragging');
            });
            
            el.addEventListener('dblclick', () => {
                this._showNodeConfig(node.id);
            });
            
            const inPort = el.querySelector('.in-port');
            const outPort = el.querySelector('.out-port');
            
            inPort.addEventListener('mousedown', (e) => this._startConnection(e, node.id, 'in'));
            outPort.addEventListener('mousedown', (e) => this._startConnection(e, node.id, 'out'));
            
            inPort.addEventListener('mouseup', (e) => this._endConnection(e, node.id, 'in'));
            outPort.addEventListener('mouseup', (e) => this._endConnection(e, node.id, 'out'));
            
            this.containers.nodesLayer.appendChild(el);
        },
        
        _getNodeContentPreview: function(node) {
            const config = node.config;
            switch (node.type) {
                case 'ai_model':
                    return config.model_id ? `模型: ${config.model_id}` : '未配置模型';
                case 'knowledge_retrieval':
                    return config.knowledge_base_id ? '已配置知识库' : '未选择知识库';
                case 'api_call':
                    return config.url || '未配置API';
                case 'condition':
                    return config.condition_variable || '未设置条件';
                default:
                    return '';
            }
        },
        
        _updateNodePosition: function(nodeId) {
            const node = this.state.nodes.get(nodeId);
            if (!node) return;
            
            const el = this.containers.nodesLayer.querySelector(`[data-node-id="${nodeId}"]`);
            if (el) {
                el.style.left = node.x + 'px';
                el.style.top = node.y + 'px';
            }
        },
        
        _selectNode: function(nodeId, addToSelection = false) {
            const node = this.state.nodes.get(nodeId);
            if (!node) return;
            
            if (!addToSelection) {
                this._clearSelection();
            }
            
            this.state.selectedNodes.add(nodeId);
            const el = this.containers.nodesLayer.querySelector(`[data-node-id="${nodeId}"]`);
            if (el) el.classList.add('selected');
            
            this._updateToolbarButtons();
            this._showNodeConfig(nodeId);
        },
        
        _clearSelection: function() {
            this.state.selectedNodes.forEach(nodeId => {
                const el = this.containers.nodesLayer.querySelector(`[data-node-id="${nodeId}"]`);
                if (el) el.classList.remove('selected');
            });
            this.state.selectedNodes.clear();
            this._updatePropertyPanel();
            this._updateToolbarButtons();
        },
        
        _updateToolbarButtons: function() {
            const toolbar = this.containers.canvas.querySelector('.canvas-toolbar');
            const deleteBtn = toolbar.querySelector('[data-action="delete"]');
            const undoBtn = toolbar.querySelector('[data-action="undo"]');
            const redoBtn = toolbar.querySelector('[data-action="redo"]');
            
            deleteBtn.disabled = this.state.selectedNodes.size === 0;
            undoBtn.disabled = this.state.historyIndex <= 0;
            redoBtn.disabled = this.state.historyIndex >= this.state.history.length - 1;
        },
        
        _handleNodeButtonClick: function(e, node) {
            const action = e.target.dataset.action;
            if (action === 'config' || action === undefined) {
                this._showNodeConfig(node.id);
            } else if (action === 'delete') {
                this._deleteNode(node.id);
            }
        },
        
        _deleteNode: function(nodeId) {
            const node = this.state.nodes.get(nodeId);
            if (!node) return;
            
            this.state.connections.forEach((conn, connId) => {
                if (conn.source === nodeId || conn.target === nodeId) {
                    this._deleteConnection(connId);
                }
            });
            
            const el = this.containers.nodesLayer.querySelector(`[data-node-id="${nodeId}"]`);
            if (el) el.remove();
            
            this.state.nodes.delete(nodeId);
            this.state.selectedNodes.delete(nodeId);
            
            this._saveHistory();
            this.state.modified = true;
        },
        
        _deleteSelected: function() {
            const nodesToDelete = Array.from(this.state.selectedNodes);
            nodesToDelete.forEach(nodeId => this._deleteNode(nodeId));
        },
        
        _selectAll: function() {
            this.state.nodes.forEach((node, nodeId) => {
                this.state.selectedNodes.add(nodeId);
                const el = this.containers.nodesLayer.querySelector(`[data-node-id="${nodeId}"]`);
                if (el) el.classList.add('selected');
            });
            this._updateToolbarButtons();
        },
        
        _startConnection: function(e, nodeId, portType) {
            e.stopPropagation();
            this.state.isConnecting = true;
            this.state.connectionStartNode = nodeId;
            this.state.connectionStartPort = portType;
            
            const svg = this.containers.tempLayer;
            while (svg.firstChild) svg.removeChild(svg.firstChild);
            
            this.containers.canvas.classList.add('connecting');
        },
        
        _endConnection: function(e, nodeId, portType) {
            if (!this.state.isConnecting) return;
            
            if (this.state.connectionStartNode !== nodeId) {
                const sourceNode = this.state.connectionStartNode;
                const sourcePort = this.state.connectionStartPort;
                
                if (sourcePort !== portType) {
                    this._addConnection(sourceNode, nodeId, sourcePort, portType);
                }
            }
            
            this._cancelConnection();
        },
        
        _cancelConnection: function() {
            this.state.isConnecting = false;
            this.state.connectionStartNode = null;
            this.state.connectionStartPort = null;
            
            const svg = this.containers.tempLayer;
            while (svg.firstChild) svg.removeChild(svg.firstChild);
            
            this.containers.canvas.classList.remove('connecting');
        },
        
        _updateTempConnection: function(e) {
            if (!this.state.isConnecting) return;
            
            const canvas = this.containers.canvas;
            const canvasContainer = canvas.querySelector('.canvas-container');
            const rect = canvasContainer.getBoundingClientRect();
            const scrollLeft = canvasContainer.scrollLeft || 0;
            const scrollTop = canvasContainer.scrollTop || 0;
            
            const mouseX = (e.clientX - rect.left + scrollLeft - this.state.offsetX) / this.state.scale;
            const mouseY = (e.clientY - rect.top + scrollTop - this.state.offsetY) / this.state.scale;
            
            const startNode = this.state.nodes.get(this.state.connectionStartNode);
            if (!startNode) return;
            
            const startX = this.state.connectionStartPort === 'out' 
                ? startNode.x + this.config.nodeWidth 
                : startNode.x;
            const startY = startNode.y + 40;
            
            const path = this._createBezierPath(startX, startY, mouseX, mouseY);
            
            let pathEl = this.containers.tempLayer.querySelector('path');
            if (!pathEl) {
                pathEl = document.createElementNS('http://www.w3.org/2000/svg', 'path');
                pathEl.setAttribute('stroke', '#1890ff');
                pathEl.setAttribute('stroke-width', '2');
                pathEl.setAttribute('fill', 'none');
                pathEl.setAttribute('stroke-dasharray', '5,5');
                this.containers.tempLayer.appendChild(pathEl);
            }
            pathEl.setAttribute('d', path);
        },
        
        _addConnection: function(sourceNodeId, targetNodeId, sourcePort, targetPort) {
            const connId = this._generateId('conn');
            
            const connection = {
                id: connId,
                source: sourceNodeId,
                target: targetNodeId,
                sourcePort: sourcePort,
                targetPort: targetPort,
                condition: null
            };
            
            this.state.connections.set(connId, connection);
            this._renderConnection(connection);
            this._saveHistory();
            this.state.modified = true;
            
            return connection;
        },
        
        _renderConnection: function(connection) {
            const sourceNode = this.state.nodes.get(connection.source);
            const targetNode = this.state.nodes.get(connection.target);
            if (!sourceNode || !targetNode) return;
            
            const sourceX = connection.sourcePort === 'out' 
                ? sourceNode.x + this.config.nodeWidth 
                : sourceNode.x;
            const sourceY = sourceNode.y + 40;
            const targetX = connection.targetPort === 'out' 
                ? targetNode.x + this.config.nodeWidth 
                : targetNode.x;
            const targetY = targetNode.y + 40;
            
            const pathData = this._createBezierPath(sourceX, sourceY, targetX, targetY);
            
            const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            path.setAttribute('id', `conn-${connection.id}`);
            path.setAttribute('d', pathData);
            path.setAttribute('stroke', '#999');
            path.setAttribute('stroke-width', '2');
            path.setAttribute('fill', 'none');
            path.dataset.connectionId = connection.id;
            
            path.addEventListener('click', (e) => {
                e.stopPropagation();
                this._selectConnection(connection.id);
            });
            
            path.addEventListener('dblclick', () => {
                this._showConnectionConfig(connection.id);
            });
            
            const marker = document.createElementNS('http://www.w3.org/2000/svg', 'marker');
            marker.setAttribute('id', `arrow-${connection.id}`);
            marker.setAttribute('markerWidth', '10');
            marker.setAttribute('markerHeight', '10');
            marker.setAttribute('refX', '9');
            marker.setAttribute('refY', '5');
            marker.setAttribute('orient', 'auto');
            marker.innerHTML = '<path d="M0,0 L10,5 L0,10" fill="#999"/>';
            
            this.containers.connectionsLayer.appendChild(marker);
            path.setAttribute('marker-end', `url(#arrow-${connection.id})`);
            this.containers.connectionsLayer.appendChild(path);
        },
        
        _createBezierPath: function(x1, y1, x2, y2) {
            const dx = Math.abs(x2 - x1) * 0.5;
            return `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`;
        },
        
        _updateConnectedConnections: function(nodeId) {
            this.state.connections.forEach((conn, connId) => {
                if (conn.source === nodeId || conn.target === nodeId) {
                    const path = this.containers.connectionsLayer.querySelector(`#conn-${connId}`);
                    if (path) {
                        const sourceNode = this.state.nodes.get(conn.source);
                        const targetNode = this.state.nodes.get(conn.target);
                        
                        if (!sourceNode || !targetNode) return;
                        
                        const sourceX = conn.sourcePort === 'out' 
                            ? sourceNode.x + this.config.nodeWidth 
                            : sourceNode.x;
                        const sourceY = sourceNode.y + 40;
                        const targetX = conn.targetPort === 'out' 
                            ? targetNode.x + this.config.nodeWidth 
                            : targetNode.x;
                        const targetY = targetNode.y + 40;
                        
                        path.setAttribute('d', this._createBezierPath(sourceX, sourceY, targetX, targetY));
                    }
                }
            });
        },
        
        _deleteConnection: function(connId) {
            const path = this.containers.connectionsLayer.querySelector(`#conn-${connId}`);
            const marker = this.containers.connectionsLayer.querySelector(`#arrow-${connId}`);
            if (path) path.remove();
            if (marker) marker.remove();
            
            this.state.connections.delete(connId);
            this._saveHistory();
        },
        
        _selectConnection: function(connId) {
            this.state.selectedConnections.add(connId);
            const path = this.containers.connectionsLayer.querySelector(`#conn-${connId}`);
            if (path) path.setAttribute('stroke', '#1890ff');
        },
        
        _showNodeConfig: function(nodeId) {
            const node = this.state.nodes.get(nodeId);
            if (!node) return;
            
            const nodeType = node.type;
            if (!nodeType || !this.isValidNodeType(nodeType)) {
                console.error('无效的节点类型:', nodeType);
                return;
            }
            
            const typeConfig = this.nodeTypes[nodeType];
            const panel = this.containers.propertyPanel.querySelector('#property-content');
            
            let html = `
                <div class="config-node-header">
                    <span class="node-icon" style="color: ${typeConfig.color}">${typeConfig.icon}</span>
                    <span class="node-name">${node.name}</span>
                    <span class="node-id">#${node.id.substring(0, 8)}</span>
                </div>
                <div class="config-form">
                    <div class="form-group">
                        <label>节点名称</label>
                        <input type="text" id="node-name-input" value="${node.name}" />
                    </div>
                    <div class="form-group">
                        <label>节点类型</label>
                        <input type="text" id="node-type-input" value="${typeConfig.name}" disabled />
                    </div>
            `;
            
            html += this._generateConfigForm(nodeType, node.config);
            
            html += `
                    <div class="config-actions">
                        <button class="layui-btn layui-btn-primary" id="cancel-config">取消</button>
                        <button class="layui-btn layui-btn-normal" id="save-config">保存</button>
                    </div>
                </div>
            `;
            
            panel.innerHTML = html;
            
            panel.querySelector('#save-config').addEventListener('click', () => {
                this._saveNodeConfig(nodeId);
            });
            
            panel.querySelector('#cancel-config').addEventListener('click', () => {
                this._updatePropertyPanel();
            });
        },
        
        _generateConfigForm: function(nodeType, config) {
            let html = '';
            
            // 尝试从后端API获取节点配置Schema
            fetch(`/ai/workflow/nodes/${nodeType}/fields/`)
                .then(response => response.json())
                .then(data => {
                    if (data.success && Object.keys(data.data || {}).length > 0) {
                        this._renderSchemaForm(nodeType, config, data.data);
                    } else {
                        this._renderHardcodedForm(nodeType, config);
                    }
                })
                .catch(error => {
                    console.warn('获取节点配置失败，使用默认表单:', error);
                    this._renderHardcodedForm(nodeType, config);
                });
            
            // 立即返回加载中的状态
            return `
                <div class="form-group">
                    <label>正在加载配置...</label>
                    <div id="config-form-container" class="config-form-container">
                        ${this._renderHardcodedForm(nodeType, config, true)}
                    </div>
                </div>
            `;
        },
        
        _renderSchemaForm: function(nodeType, config, schema) {
            const container = document.getElementById('config-form-container');
            if (!container) return;
            
            let html = '';
            
            for (const [fieldName, fieldSchema] of Object.entries(schema)) {
                const fieldId = `config-${fieldName}`;
                const value = config[fieldName] !== undefined ? config[fieldName] : fieldSchema.default;
                
                let inputHtml = '';
                const tooltip = fieldSchema.description ? `<span class="field-tooltip" title="${fieldSchema.description}">?</span>` : '';
                const desc = fieldSchema.description ? `<div class="field-description">${fieldSchema.description}</div>` : '';
                
                switch (fieldSchema.type) {
                    case 'select':
                        const options = (fieldSchema.options || []).map(opt => 
                            `<option value="${opt.value}" ${value === opt.value ? 'selected' : ''}>${opt.label}</option>`
                        ).join('');
                        inputHtml = `<select id="${fieldId}" name="${fieldName}" class="form-input">${options}</select>`;
                        break;
                        
                    case 'number':
                        const minAttr = fieldSchema.min_value !== undefined ? `min="${fieldSchema.min_value}"` : '';
                        const maxAttr = fieldSchema.max_value !== undefined ? `max="${fieldSchema.max_value}"` : '';
                        inputHtml = `<input type="number" id="${fieldId}" name="${fieldName}" class="form-input" ${minAttr} ${maxAttr} value="${value || ''}">`;
                        break;
                        
                    case 'boolean':
                        inputHtml = `<input type="checkbox" id="${fieldId}" name="${fieldName}" ${value ? 'checked' : ''}>`;
                        break;
                        
                    case 'text':
                    case 'string':
                    default:
                        inputHtml = `<input type="text" id="${fieldId}" name="${fieldName}" class="form-input" placeholder="${fieldSchema.placeholder || ''}" value="${value || ''}">`;
                }
                
                html += `
                    <div class="form-group">
                        <label for="${fieldId}">${fieldSchema.label || fieldName} ${tooltip}</label>
                        ${inputHtml}
                        ${desc}
                    </div>
                `;
            }
            
            container.innerHTML = html || '<div class="form-group"><label>此节点无需额外配置</label></div>';
        },
        
        _renderHardcodedForm: function(nodeType, config, returnOnly = false) {
            let html = '';
            
            // 需要动态加载选项的节点类型
            const dynamicOptionNodes = ['ai_model', 'ai_generation', 'ai_classification', 'ai_extraction', 
                                       'knowledge_retrieval', 'intent_recognition', 'sentiment_analysis'];
            
            // 获取动态选项
            if (dynamicOptionNodes.includes(nodeType)) {
                html += '<div id="dynamic-options-loading" class="form-group"><label>正在加载选项...</label></div>';
            }
            
            switch (nodeType) {
                case 'ai_model':
                    html += `
                        <div class="form-group">
                            <label>AI模型</label>
                            <select id="config-model_id">
                                <option value="">请选择模型...</option>
                                <option value="gpt-3.5-turbo" ${config.model_id === 'gpt-3.5-turbo' ? 'selected' : ''}>GPT-3.5 Turbo</option>
                                <option value="gpt-4" ${config.model_id === 'gpt-4' ? 'selected' : ''}>GPT-4</option>
                                <option value="deepseek-chat" ${config.model_id === 'deepseek-chat' ? 'selected' : ''}>DeepSeek Chat</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label>系统提示词</label>
                            <textarea id="config-prompt" rows="4" placeholder="输入系统提示词，可以使用 {{变量名}} 引用变量">${config.prompt || ''}</textarea>
                        </div>
                        <div class="form-group">
                            <label>输出变量名</label>
                            <input type="text" id="config-output_variable" value="${config.output_variable || 'ai_result'}" />
                        </div>
                    `;
                    break;
                    
                case 'ai_generation':
                    html += `
                        <div class="form-group">
                            <label>模型</label>
                            <select id="config-model_id">
                                <option value="">请选择模型...</option>
                                <option value="gpt-3.5-turbo" ${config.model_id === 'gpt-3.5-turbo' ? 'selected' : ''}>GPT-3.5 Turbo</option>
                                <option value="gpt-4" ${config.model_id === 'gpt-4' ? 'selected' : ''}>GPT-4</option>
                                <option value="deepseek-chat" ${config.model_id === 'deepseek-chat' ? 'selected' : ''}>DeepSeek Chat</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label>提示词</label>
                            <textarea id="config-prompt" rows="4" placeholder="输入提示词">${config.prompt || ''}</textarea>
                        </div>
                        <div class="form-group">
                            <label>输出变量名</label>
                            <input type="text" id="config-output_variable" value="${config.output_variable || 'result'}" />
                        </div>
                    `;
                    break;
                    
                case 'ai_classification':
                    html += `
                        <div class="form-group">
                            <label>模型</label>
                            <select id="config-model_id">
                                <option value="">请选择模型...</option>
                                <option value="gpt-3.5-turbo">GPT-3.5 Turbo</option>
                                <option value="gpt-4">GPT-4</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label>分类类别</label>
                            <textarea id="config-categories" rows="3" placeholder="每行一个类别">${config.categories ? config.categories.join('\n') : ''}</textarea>
                        </div>
                        <div class="form-group">
                            <label>输出变量名</label>
                            <input type="text" id="config-output_variable" value="${config.output_variable || 'category'}" />
                        </div>
                    `;
                    break;
                    
                case 'ai_extraction':
                    html += `
                        <div class="form-group">
                            <label>模型</label>
                            <select id="config-model_id">
                                <option value="">请选择模型...</option>
                                <option value="gpt-3.5-turbo">GPT-3.5 Turbo</option>
                                <option value="gpt-4">GPT-4</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label>提取Schema</label>
                            <textarea id="config-extraction_schema" rows="4" placeholder='{"name": "姓名", "age": "年龄"}'>${JSON.stringify(config.extraction_schema || {}, null, 2)}</textarea>
                        </div>
                        <div class="form-group">
                            <label>输出变量名</label>
                            <input type="text" id="config-output_variable" value="${config.output_variable || 'extraction'}" />
                        </div>
                    `;
                    break;
                    
                case 'knowledge_retrieval':
                    html += `
                        <div class="form-group">
                            <label>知识库</label>
                            <select id="config-knowledge_base_id">
                                <option value="">请选择知识库...</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label>查询变量</label>
                            <input type="text" id="config-query_variable" value="${config.query_variable || ''}" placeholder="输入查询内容的变量名" />
                        </div>
                        <div class="form-group">
                            <label>返回数量</label>
                            <input type="number" id="config-top_k" value="${config.top_k || 5}" min="1" max="20" />
                        </div>
                    `;
                    break;
                    
                case 'api_call':
                case 'http_request':
                    html += `
                        <div class="form-group">
                            <label>API地址</label>
                            <input type="text" id="config-url" value="${config.url || ''}" placeholder="https://api.example.com/endpoint" />
                        </div>
                        <div class="form-group">
                            <label>请求方法</label>
                            <select id="config-method">
                                <option value="GET" ${config.method === 'GET' ? 'selected' : ''}>GET</option>
                                <option value="POST" ${config.method === 'POST' ? 'selected' : ''}>POST</option>
                                <option value="PUT" ${config.method === 'PUT' ? 'selected' : ''}>PUT</option>
                                <option value="DELETE" ${config.method === 'DELETE' ? 'selected' : ''}>DELETE</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label>Content-Type</label>
                            <select id="config-content_type">
                                <option value="application/json" ${config.content_type === 'application/json' ? 'selected' : ''}>application/json</option>
                                <option value="application/x-www-form-urlencoded" ${config.content_type === 'application/x-www-form-urlencoded' ? 'selected' : ''}>application/x-www-form-urlencoded</option>
                                <option value="multipart/form-data" ${config.content_type === 'multipart/form-data' ? 'selected' : ''}>multipart/form-data</option>
                                <option value="text/plain" ${config.content_type === 'text/plain' ? 'selected' : ''}>text/plain</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label>请求体 (JSON)</label>
                            <textarea id="config-body" rows="4" placeholder='{"key": "value"}'>${config.body || ''}</textarea>
                        </div>
                        <div class="form-group">
                            <label>输出变量名</label>
                            <input type="text" id="config-output_variable" value="${config.output_variable || 'response'}" />
                        </div>
                    `;
                    break;
                    
                case 'condition':
                    html += `
                        <div class="form-group">
                            <label>条件变量</label>
                            <input type="text" id="config-condition_variable" value="${config.condition_variable || ''}" placeholder="输入条件判断的变量名" />
                        </div>
                        <div class="form-group">
                            <label>条件类型</label>
                            <select id="config-condition_type">
                                <option value="if_else" ${config.condition_type === 'if_else' ? 'selected' : ''}>如果...否则...</option>
                                <option value="switch" ${config.condition_type === 'switch' ? 'selected' : ''}>多条件分支</option>
                            </select>
                        </div>
                    `;
                    
                    if (config.condition_type === 'switch') {
                        html += `
                            <div class="form-group">
                                <label>分支配置</label>
                                <textarea id="config-cases" rows="4" placeholder='[{"value": "A", "output": "result_a"}, {"value": "B", "output": "result_b"}]'>${JSON.stringify(config.cases || [], null, 2)}</textarea>
                            </div>
                        `;
                    }
                    break;
                    
                case 'multi_condition':
                    html += `
                        <div class="form-group">
                            <label>条件表达式</label>
                            <textarea id="config-expressions" rows="4" placeholder='[{"expression": "{{value}} > 10", "output": "result_a"}]'>${JSON.stringify(config.expressions || [], null, 2)}</textarea>
                        </div>
                        <div class="form-group">
                            <label>默认输出</label>
                            <input type="text" id="config-default_output" value="${config.default_output || ''}" placeholder="默认输出值" />
                        </div>
                    `;
                    break;
                    
                case 'data_input':
                    html += `
                        <div class="form-group">
                            <label>输入数据</label>
                            <textarea id="config-input_data" rows="3" placeholder="输入数据内容">${config.input_data || ''}</textarea>
                        </div>
                        <div class="form-group">
                            <label>输出变量名</label>
                            <input type="text" id="config-output_variable" value="${config.output_variable || 'input'}" />
                        </div>
                    `;
                    break;
                    
                case 'data_output':
                    html += `
                        <div class="form-group">
                            <label>输入变量</label>
                            <input type="text" id="config-input_variable" value="${config.input_variable || ''}" placeholder="输入变量名" />
                        </div>
                        <div class="form-group">
                            <label>输出类型</label>
                            <select id="config-output_type">
                                <option value="result" ${config.output_type === 'result' ? 'selected' : ''}>结果</option>
                                <option value="json" ${config.output_type === 'json' ? 'selected' : ''}>JSON</option>
                            </select>
                        </div>
                    `;
                    break;
                    
                case 'database_query':
                    html += `
                        <div class="form-group">
                            <label>SQL查询</label>
                            <textarea id="config-query" rows="4" placeholder="SELECT * FROM table">${config.query || ''}</textarea>
                        </div>
                        <div class="form-group">
                            <label>数据源</label>
                            <select id="config-datasource_id">
                                <option value="">默认数据源</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label>输出变量名</label>
                            <input type="text" id="config-output_variable" value="${config.output_variable || 'query_result'}" />
                        </div>
                    `;
                    break;
                    
                case 'delay':
                    html += `
                        <div class="form-group">
                            <label>延迟秒数</label>
                            <input type="number" id="config-delay_seconds" value="${config.delay_seconds || 5}" min="1" />
                        </div>
                    `;
                    break;
                    
                case 'notification':
                    html += `
                        <div class="form-group">
                            <label>通知类型</label>
                            <select id="config-notification_type">
                                <option value="toast" ${config.notification_type === 'toast' ? 'selected' : ''}>Toast提示</option>
                                <option value="email" ${config.notification_type === 'email' ? 'selected' : ''}>邮件</option>
                                <option value="sms" ${config.notification_type === 'sms' ? 'selected' : ''}>短信</option>
                                <option value="webhook" ${config.notification_type === 'webhook' ? 'selected' : ''}>Webhook</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label>通知内容</label>
                            <textarea id="config-message" rows="3">${config.message || ''}</textarea>
                        </div>
                    `;
                    break;
                    
                case 'workflow_trigger':
                    html += `
                        <div class="form-group">
                            <label>触发类型</label>
                            <select id="config-trigger_type">
                                <option value="manual" ${config.trigger_type === 'manual' ? 'selected' : ''}>手动触发</option>
                                <option value="webhook" ${config.trigger_type === 'webhook' ? 'selected' : ''}>Webhook触发</option>
                                <option value="schedule" ${config.trigger_type === 'schedule' ? 'selected' : ''}>定时触发</option>
                                <option value="event" ${config.trigger_type === 'event' ? 'selected' : ''}>事件触发</option>
                            </select>
                        </div>
                    `;
                    break;
                    
                default:
                    html += `
                        <div class="form-group">
                            <label>此节点暂无额外配置</label>
                            <p class="config-hint">节点类型: ${nodeType}</p>
                        </div>
                    `;
            }
            
            if (returnOnly) {
                return html;
            }
            
            const container = document.getElementById('config-form-container');
            if (container) {
                container.innerHTML = html;
                
                // 动态加载选项
                if (dynamicOptionNodes.includes(nodeType)) {
                    this._loadDynamicOptions(nodeType);
                }
            }
            
            return html;
        },
        
        _loadDynamicOptions: function(nodeType) {
            const self = this;
            
            // 获取动态选项
            fetch(`/ai/workflow/nodes/${nodeType}/options/`)
                .then(response => response.json())
                .then(data => {
                    if (data.success && data.options) {
                        for (const [fieldName, options] of Object.entries(data.options)) {
                            const select = document.getElementById(`config-${fieldName}`);
                            if (select && options.length > 0) {
                                // 保留第一个空选项
                                const firstOption = select.options[0];
                                select.innerHTML = '';
                                select.appendChild(firstOption);
                                
                                // 添加动态选项
                                options.forEach(opt => {
                                    const option = document.createElement('option');
                                    option.value = opt.value;
                                    option.textContent = opt.label || opt.value;
                                    
                                    // 添加provider或knowledge_type属性
                                    if (opt.provider) {
                                        option.setAttribute('data-provider', opt.provider);
                                    }
                                    if (opt.knowledge_type) {
                                        option.setAttribute('data-knowledge-type', opt.knowledge_type);
                                    }
                                    
                                    select.appendChild(option);
                                });
                            }
                        }
                    }
                })
                .catch(error => {
                    console.warn('加载动态选项失败:', error);
                });
        },
        
        _saveNodeConfig: function(nodeId) {
            const node = this.state.nodes.get(nodeId);
            if (!node) return;
            
            const nameInput = document.getElementById('node-name-input');
            if (nameInput) {
                node.name = nameInput.value;
            }
            
            const configFields = [
                'model_id', 'prompt', 'output_variable', 'knowledge_base_id', 
                'query_variable', 'top_k', 'url', 'method', 'body', 'condition_variable', 
                'condition_type', 'input_variable', 'input_data', 'output_type',
                'delay_seconds', 'notification_type', 'message', 'trigger_type',
                'categories', 'extraction_schema', 'query', 'delay_seconds'
            ];
            
            configFields.forEach(field => {
                const input = document.getElementById(`config-${field}`);
                if (input) {
                    let value;
                    if (input.type === 'number') {
                        value = parseInt(input.value);
                    } else if (input.type === 'checkbox') {
                        value = input.checked;
                    } else if (field === 'categories') {
                        value = input.value.split('\n').filter(v => v.trim());
                    } else {
                        value = input.value;
                    }
                    node.config[field] = value;
                }
            });

            const contentEl = document.getElementById(`content-${nodeId}`);
            if (contentEl) {
                contentEl.textContent = this._getNodeContentPreview(node);
            }
            
            const headerEl = this.containers.nodesLayer.querySelector(`[data-node-id="${nodeId}"] .node-name`);
            if (headerEl) {
                headerEl.textContent = node.name;
            }
            
            this._saveHistory();
            this.state.modified = true;
            
            if (typeof layer !== 'undefined') {
                layer.msg('配置已保存', { icon: 1, time: 1500 });
            } else {
                alert('配置已保存');
            }
        },
        
        _showConnectionConfig: function(connId) {
            const connection = this.state.connections.get(connId);
            if (!connection) return;
            
            const panel = this.containers.propertyPanel.querySelector('#property-content');
            panel.innerHTML = `
                <div class="config-node-header">
                    <span class="node-name">连接配置</span>
                </div>
                <div class="form-group">
                    <label>条件表达式 (可选)</label>
                    <textarea id="conn-condition" rows="3" placeholder="例如: {{variable}} > 10">${connection.condition || ''}</textarea>
                </div>
                <div class="config-actions">
                    <button class="layui-btn layui-btn-danger" id="delete-conn">删除连接</button>
                    <button class="layui-btn layui-btn-normal" id="save-conn">保存</button>
                </div>
            `;
            
            panel.querySelector('#save-conn').addEventListener('click', () => {
                const conditionInput = document.getElementById('conn-condition');
                if (conditionInput) {
                    connection.condition = conditionInput.value.trim() || null;
                }
                layer.msg('连接已更新', { icon: 1, time: 1500 });
            });
            
            panel.querySelector('#delete-conn').addEventListener('click', () => {
                this._deleteConnection(connId);
                this._updatePropertyPanel();
                layer.msg('连接已删除', { icon: 1, time: 1500 });
            });
        },
        
        _updatePropertyPanel: function() {
            const panel = this.containers.propertyPanel.querySelector('#property-content');
            panel.innerHTML = `
                <div class="no-selection">
                    <div class="no-selection-icon">◇</div>
                    <div class="no-selection-text">选择一个节点以编辑属性</div>
                </div>
            `;
        },
        
        _setZoom: function(scale) {
            scale = Math.max(0.1, Math.min(3, scale));
            this.state.scale = scale;
            
            const transformStyle = `scale(${scale}) translate(${this.state.offsetX}px, ${this.state.offsetY}px)`;
            
            if (this.containers.nodesLayer) {
                this.containers.nodesLayer.style.transform = transformStyle;
                this.containers.nodesLayer.style.transformOrigin = '0 0';
            }
            
            if (this.containers.connectionsLayer) {
                this.containers.connectionsLayer.style.transform = transformStyle;
                this.containers.connectionsLayer.style.transformOrigin = '0 0';
            }
            
            if (this.containers.tempLayer) {
                this.containers.tempLayer.style.transform = transformStyle;
                this.containers.tempLayer.style.transformOrigin = '0 0';
            }
            
            const zoomIndicator = this.containers.canvas.querySelector('.zoom-indicator');
            if (zoomIndicator) {
                zoomIndicator.textContent = Math.round(scale * 100) + '%';
            }
            
            this._updateMinimap();
        },
        
        _updateMinimap: function() {
            const minimap = this.containers.canvas.querySelector('#minimap');
            if (!minimap) return;
            
            const nodes = Array.from(this.state.nodes.values());
            if (nodes.length === 0) {
                minimap.style.display = 'none';
                return;
            }
            
            minimap.style.display = 'block';
            
            const minX = Math.min(...nodes.map(n => n.x)) - 50;
            const minY = Math.min(...nodes.map(n => n.y)) - 50;
            const maxX = Math.max(...nodes.map(n => n.x)) + this.config.nodeWidth + 50;
            const maxY = Math.max(...nodes.map(n => n.y)) + 100 + 50;
            
            const mapWidth = 200;
            const mapHeight = (maxY - minY) / (maxX - minX) * mapWidth;
            
            minimap.style.width = mapWidth + 'px';
            minimap.style.height = mapHeight + 'px';
            
            const scale = mapWidth / (maxX - minX);
            
            const viewport = minimap.querySelector('.minimap-viewport');
            const containerRect = this.containers.canvas.querySelector('.canvas-container').getBoundingClientRect();
            const canvasRect = this.containers.canvas.getBoundingClientRect();
            
            viewport.style.left = (-this.state.offsetX * scale) + 'px';
            viewport.style.top = (-this.state.offsetY * scale) + 'px';
            viewport.style.width = (containerRect.width * scale * this.state.scale) + 'px';
            viewport.style.height = (containerRect.height * scale * this.state.scale) + 'px';
        },
        
        _saveHistory: function() {
            const stateSnapshot = {
                nodes: Array.from(this.state.nodes.entries()),
                connections: Array.from(this.state.connections.entries())
            };
            
            this.state.history = this.state.history.slice(0, this.state.historyIndex + 1);
            this.state.history.push(JSON.parse(JSON.stringify(stateSnapshot)));
            
            if (this.state.history.length > this.config.undoLimit) {
                this.state.history.shift();
            } else {
                this.state.historyIndex++;
            }
            
            this._updateToolbarButtons();
        },
        
        _undo: function() {
            if (this.state.historyIndex > 0) {
                this.state.historyIndex--;
                this._restoreHistory();
            }
        },
        
        _redo: function() {
            if (this.state.historyIndex < this.state.history.length - 1) {
                this.state.historyIndex++;
                this._restoreHistory();
            }
        },
        
        _restoreHistory: function() {
            const snapshot = this.state.history[this.state.historyIndex];
            
            this.containers.nodesLayer.innerHTML = '';
            this.containers.connectionsLayer.innerHTML = '';
            this.state.nodes.clear();
            this.state.connections.clear();
            
            snapshot.nodes.forEach(([id, node]) => {
                this.state.nodes.set(id, node);
                this._renderNode(node);
            });
            
            snapshot.connections.forEach(([id, conn]) => {
                this.state.connections.set(id, conn);
                this._renderConnection(conn);
            });
            
            this._updateToolbarButtons();
        },
        
        _executeWorkflow: function() {
            const workflowData = this._exportWorkflow();
            
            fetch(`/ai/workflow/${workflowData.id}/enhanced-execute/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this._getCsrfToken()
                },
                body: JSON.stringify(workflowData)
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    layer.msg('工作流执行成功', { icon: 1, time: 3000 });
                    this._showExecutionResult(data);
                } else {
                    layer.msg('工作流执行失败: ' + data.message, { icon: 2, time: 3000 });
                }
            })
            .catch(error => {
                console.error('执行工作流失败:', error);
                layer.msg('执行工作流失败', { icon: 2, time: 3000 });
            });
        },
        
        _showExecutionResult: function(result) {
            const panel = this.containers.propertyPanel.querySelector('#property-content');
            panel.innerHTML = `
                <div class="execution-result">
                    <h4>执行结果</h4>
                    <pre>${JSON.stringify(result.output_data, null, 2)}</pre>
                </div>
            `;
        },
        
        _toggleDebugMode: function() {
            this.containers.canvas.classList.toggle('debug-mode');
            layer.msg(this.containers.canvas.classList.contains('debug-mode') ? '调试模式已开启' : '调试模式已关闭');
        },
        
        _exportWorkflow: function() {
            return {
                id: this.containers.container.dataset.workflowId || '',
                nodes: Array.from(this.state.nodes.values()),
                connections: Array.from(this.state.connections.values())
            };
        },
        
        _importWorkflow: function(data) {
            this._clearCanvas();
            
            data.nodes.forEach(node => {
                this.state.nodes.set(node.id, node);
                this._renderNode(node);
            });
            
            data.connections.forEach(conn => {
                this.state.connections.set(conn.id, conn);
                this._renderConnection(conn);
            });
            
            this._saveHistory();
        },
        
        _clearCanvas: function() {
            this.containers.nodesLayer.innerHTML = '';
            this.containers.connectionsLayer.innerHTML = '';
            this.state.nodes.clear();
            this.state.connections.clear();
            this.state.selectedNodes.clear();
            this._updatePropertyPanel();
        },
        
        _loadDefaultWorkflow: function() {
            if (window.DEFAULT_WORKFLOW_DATA) {
                this._importWorkflow(window.DEFAULT_WORKFLOW_DATA);
            }
        },
        
        _generateId: function(prefix) {
            return `${prefix}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        },
        
        _getCsrfToken: function() {
            let token = '';
            
            // 尝试从cookie获取
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.indexOf('csrftoken=') === 0) {
                    token = cookie.substring('csrftoken='.length, cookie.length);
                    break;
                }
            }
            
            // 如果cookie中没有，尝试从DOM获取
            if (!token) {
                const input = document.querySelector('[name="csrfmiddlewaretoken"]');
                if (input) {
                    token = input.value;
                }
            }
            
            // 尝试从meta标签获取
            if (!token) {
                const meta = document.querySelector('meta[name="csrf-token"]');
                if (meta) {
                    token = meta.getAttribute('content');
                }
            }
            
            return token;
        }
    };
    
    global.WorkflowDesigner = WorkflowDesigner;
    
})(typeof window !== 'undefined' ? window : this);

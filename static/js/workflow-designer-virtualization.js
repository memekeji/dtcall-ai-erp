/**
 * Virtualized Workflow Designer - Performance Optimization Module
 * Implements virtualization for large-scale workflow rendering
 * 
 * Key Features:
 * - Viewport-based rendering (only render visible nodes)
 * - Efficient diff algorithm for updates
 * - Batched DOM updates
 * - Lazy loading of node configurations
 * - Connection culling optimization
 */

(function(global) {
    'use strict';

    const VirtualizedWorkflowDesigner = {
        config: {
            viewportMargin: 200,
            minVisibleNodes: 5,
            batchUpdateInterval: 16,
            connectionCullDistance: 500,
            lazyLoadConfig: true,
            useRAF: true
        },

        state: {
            viewport: { x: 0, y: 0, width: 0, height: 0 },
            visibleRange: { start: 0, end: 100 },
            visibleNodes: new Set(),
            visibleConnections: new Set(),
            nodePositions: new Map(),
            isAnimating: false,
            pendingUpdates: [],
            lastRenderTime: 0,
            renderCount: 0
        },

        virtualizer: null,

        init: function(workflowDesigner, options = {}) {
            this.config = { ...this.config, ...options };
            this.designer = workflowDesigner;
            this.virtualizer = new ViewportVirtualizer(this);
            this._bindEvents();
            console.log('Virtualized renderer initialized');
            return this;
        },

        _bindEvents: function() {
            const canvas = this.designer.containers.canvas;
            if (!canvas) return;

            canvas.addEventListener('scroll', () => this._handleScroll());
            
            let scrollTimeout;
            const handleScrollEnd = () => {
                clearTimeout(scrollTimeout);
                scrollTimeout = setTimeout(() => {
                    this._handleScrollEnd();
                }, 150);
            };
            canvas.addEventListener('scroll', handleScrollEnd);
        },

        _handleScroll: function() {
            if (this.config.useRAF && this.state.isAnimating) return;
            
            this.state.isAnimating = true;
            
            if (this.config.useRAF) {
                requestAnimationFrame(() => this._updateViewport());
            } else {
                this._updateViewport();
            }
        },

        _handleScrollEnd: function() {
            this.state.isAnimating = false;
            this._performFullUpdate();
        },

        _updateViewport: function() {
            const canvas = this.designer.containers.canvas;
            const container = canvas.querySelector('.canvas-container');
            if (!container) return;

            const scrollLeft = container.scrollLeft || 0;
            const scrollTop = container.scrollTop || 0;

            this.state.viewport = {
                x: scrollLeft / this.designer.state.scale,
                y: scrollTop / this.designer.state.scale,
                width: container.clientWidth / this.designer.state.scale,
                height: container.clientHeight / this.designer.state.scale,
                scale: this.designer.state.scale
            };

            this._calculateVisibleRange();
            this._updateVisibleNodes();
            this._updateVisibleConnections();
            this._scheduleRender();

            this.state.isAnimating = false;
        },

        _calculateVisibleRange: function() {
            const nodes = Array.from(this.designer.state.nodes.values());
            if (nodes.length === 0) {
                this.state.visibleRange = { start: 0, end: 0 };
                return;
            }

            const viewport = this.state.viewport;
            const margin = this.config.viewportMargin / viewport.scale;
            
            const visibleNodes = nodes.filter(node => {
                return node.x + this.designer.config.nodeWidth >= viewport.x - margin &&
                       node.x <= viewport.x + viewport.width + margin &&
                       node.y >= viewport.y - margin &&
                       node.y <= viewport.y + viewport.height + margin;
            });

            const nodeIds = visibleNodes.map(n => n.id);
            this.state.visibleNodes = new Set(nodeIds);
            
            this.state.visibleRange = {
                start: nodeIds[0] || null,
                end: nodeIds[nodeIds.length - 1] || null,
                count: nodeIds.length
            };
        },

        _updateVisibleNodes: function() {
            const nodesLayer = this.designer.containers.nodesLayer;
            if (!nodesLayer) return;

            const currentVisible = new Set();
            this.designer.state.nodes.forEach((node, nodeId) => {
                if (this.state.visibleNodes.has(nodeId)) {
                    currentVisible.add(nodeId);
                    this._ensureNodeRendered(node);
                } else {
                    this._hideNode(nodeId);
                }
            });
        },

        _ensureNodeRendered: function(node) {
            let el = this.designer.containers.nodesLayer.querySelector(`[data-node-id="${node.id}"]`);
            
            if (!el) {
                this.designer._renderNode(node);
                el = this.designer.containers.nodesLayer.querySelector(`[data-node-id="${node.id}"]`);
            }

            if (el && el.style.display === 'none') {
                el.style.display = '';
                el.style.willChange = 'transform, opacity';
            }

            this._updateNodePosition(node);
        },

        _hideNode: function(nodeId) {
            const el = this.designer.containers.nodesLayer.querySelector(`[data-node-id="${nodeId}"]`);
            if (el && el.style.display !== 'none') {
                el.style.display = 'none';
                el.style.willChange = '';
            }
        },

        _updateNodePosition: function(node) {
            const el = this.designer.containers.nodesLayer.querySelector(`[data-node-id="${node.id}"]`);
            if (el) {
                el.style.transform = `translate(${node.x}px, ${node.y}px)`;
                el.style.position = 'absolute';
                el.style.left = '0';
                el.style.top = '0';
            }
        },

        _updateVisibleConnections: function() {
            const connectionLayer = this.designer.containers.connectionsLayer;
            if (!connectionLayer) return;

            const viewport = this.state.viewport;
            const cullDistance = this.config.connectionCullDistance / viewport.scale;

            this.designer.state.connections.forEach((conn, connId) => {
                const sourceNode = this.designer.state.nodes.get(conn.source);
                const targetNode = this.designer.state.nodes.get(conn.target);

                if (!sourceNode || !targetNode) return;

                const sourceVisible = this.state.visibleNodes.has(conn.source);
                const targetVisible = this.state.visibleNodes.has(conn.target);
                const connectionsVisible = this.state.visibleConnections.has(connId);

                if (sourceVisible && targetVisible) {
                    if (!connectionsVisible) {
                        this._renderConnection(conn);
                    }
                } else if (connectionsVisible || (sourceVisible && !targetVisible) || (!sourceVisible && targetVisible)) {
                    const midX = (sourceNode.x + targetNode.x) / 2;
                    const midY = (sourceNode.y + targetNode.y) / 2;

                    const inViewport = midX >= viewport.x - cullDistance &&
                                      midX <= viewport.x + viewport.width + cullDistance &&
                                      midY >= viewport.y - cullDistance &&
                                      midY <= viewport.y + viewport.height + cullDistance;

                    if (inViewport) {
                        if (!connectionsVisible) {
                            this._renderConnection(conn);
                        }
                    } else {
                        this._hideConnection(connId);
                    }
                }
            });
        },

        _renderConnection: function(connection) {
            const path = this.designer.containers.connectionsLayer.querySelector(`#conn-${connection.id}`);
            if (path) {
                path.style.display = '';
            } else {
                this.designer._renderConnection(connection);
            }
        },

        _hideConnection: function(connId) {
            const path = this.designer.containers.connectionsLayer.querySelector(`#conn-${connId}`);
            if (path) {
                path.style.display = 'none';
            }
        },

        _scheduleRender: function() {
            if (this.state.pendingUpdates.length === 0) return;

            const now = performance.now();
            if (now - this.state.lastRenderTime < this.config.batchUpdateInterval) {
                if (!this.state.isAnimating && this.config.useRAF) {
                    requestAnimationFrame(() => this._performBatchedUpdate());
                }
            } else {
                this._performBatchedUpdate();
            }
        },

        _performBatchedUpdate: function() {
            const updates = this.state.pendingUpdates.splice(0);
            
            const startTime = performance.now();
            
            updates.forEach(update => {
                if (update.type === 'node') {
                    this._ensureNodeRendered(update.node);
                } else if (update.type === 'connection') {
                    this._renderConnection(update.connection);
                } else if (update.type === 'hideNode') {
                    this._hideNode(update.nodeId);
                } else if (update.type === 'hideConnection') {
                    this._hideConnection(update.connectionId);
                }
            });

            this.state.lastRenderTime = performance.now();
            this.state.renderCount++;
        },

        queueUpdate: function(type, data) {
            this.state.pendingUpdates.push({ type, ...data });
        },

        _performFullUpdate: function() {
            this._updateViewport();
            
            const nodesLayer = this.designer.containers.nodesLayer;
            const connectionsLayer = this.designer.containers.connectionsLayer;

            nodesLayer.querySelectorAll('.workflow-node').forEach(el => {
                el.style.willChange = '';
            });
        },

        getPerformanceStats: function() {
            return {
                renderCount: this.state.renderCount,
                visibleNodeCount: this.state.visibleNodes.size,
                visibleConnectionCount: this.state.visibleConnections.size,
                pendingUpdates: this.state.pendingUpdates.length,
                viewport: this.state.viewport
            };
        },

        setViewport: function(x, y, width, height) {
            this.state.viewport = { x, y, width, height, scale: this.designer.state.scale };
            this._calculateVisibleRange();
            this._updateVisibleNodes();
            this._updateVisibleConnections();
        },

        refresh: function() {
            this._performFullUpdate();
        }
    };

    class ViewportVirtualizer {
        constructor(virtualizedDesigner) {
            this.vd = virtualizedDesigner;
            this.observer = null;
            this.resizeObserver = null;
            this._initObservers();
        }

        _initObservers() {
            if (typeof IntersectionObserver !== 'undefined') {
                this.observer = new IntersectionObserver(
                    (entries) => this._handleIntersection(entries),
                    {
                        root: null,
                        rootMargin: '200px',
                        threshold: 0
                    }
                );
            }

            if (typeof ResizeObserver !== 'undefined') {
                this.resizeObserver = new ResizeObserver(
                    (entries) => this._handleResize(entries)
                );
            }
        }

        _handleIntersection(entries) {
            entries.forEach(entry => {
                const nodeId = entry.target.dataset.nodeId;
                if (entry.isIntersecting) {
                    this.vd.state.visibleNodes.add(nodeId);
                    this.vd.queueUpdate('node', { node: this.vd.designer.state.nodes.get(nodeId) });
                } else {
                    this.vd.state.visibleNodes.delete(nodeId);
                    this.vd.queueUpdate('hideNode', { nodeId });
                }
            });
        }

        _handleResize(entries) {
            entries.forEach(entry => {
                this.vd._updateViewport();
            });
        }

        observe(element) {
            if (this.observer) {
                this.observer.observe(element);
            }
            if (this.resizeObserver) {
                this.resizeObserver.observe(element);
            }
        }

        disconnect() {
            if (this.observer) {
                this.observer.disconnect();
            }
            if (this.resizeObserver) {
                this.resizeObserver.disconnect();
            }
        }
    }

    class NodePool {
        constructor(createFn, resetFn, maxSize = 100) {
            this.createFn = createFn;
            this.resetFn = resetFn;
            this.maxSize = maxSize;
            this.pool = [];
        }

        acquire() {
            if (this.pool.length > 0) {
                return this.pool.pop();
            }
            return this.createFn();
        }

        release(obj) {
            if (this.pool.length < this.maxSize) {
                this.resetFn(obj);
                this.pool.push(obj);
            }
        }

        clear() {
            this.pool = [];
        }
    }

    class ConnectionOptimizer {
        constructor(workflowDesigner) {
            this.designer = workflowDesigner;
            this.cache = new Map();
            this.dirtyConnections = new Set();
        }

        calculatePath(sourceX, sourceY, targetX, targetY) {
            const key = `${Math.round(sourceX)},${Math.round(sourceY)}->${Math.round(targetX)},${Math.round(targetY)}`;
            
            if (this.cache.has(key)) {
                return this.cache.get(key);
            }

            const path = this._computeBezierPath(sourceX, sourceY, targetX, targetY);
            this.cache.set(key, path);

            if (this.cache.size > 1000) {
                this._pruneCache();
            }

            return path;
        }

        _computeBezierPath(x1, y1, x2, y2) {
            const dx = Math.abs(x2 - x1) * 0.5;
            return `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`;
        }

        _pruneCache() {
            const entries = Array.from(this.cache.entries());
            entries.slice(0, 500).forEach(([key]) => {
                this.cache.delete(key);
            });
        }

        markDirty(connId) {
            this.dirtyConnections.add(connId);
        }

        getDirtyConnections() {
            const dirty = Array.from(this.dirtyConnections);
            this.dirtyConnections.clear();
            return dirty;
        }

        clear() {
            this.cache.clear();
            this.dirtyConnections.clear();
        }
    }

    class BatchRenderer {
        constructor() {
            this.pending = [];
            this.processing = false;
            this.batchSize = 50;
        }

        add(renderFn) {
            this.pending.push(renderFn);
            if (!this.processing) {
                this._process();
            }
        }

        _process() {
            this.processing = true;
            
            const startTime = performance.now();
            
            while (this.pending.length > 0 && performance.now() - startTime < 16) {
                const batch = this.pending.splice(0, this.batchSize);
                batch.forEach(fn => fn());
            }

            if (this.pending.length > 0) {
                requestAnimationFrame(() => this._process());
            } else {
                this.processing = false;
            }
        }

        flush() {
            while (this.pending.length > 0) {
                const batch = this.pending.splice(0, this.batchSize);
                batch.forEach(fn => fn());
            }
            this.processing = false;
        }
    }

    global.VirtualizedWorkflowDesigner = VirtualizedWorkflowDesigner;
    global.ViewportVirtualizer = ViewportVirtualizer;
    global.NodePool = NodePool;
    global.ConnectionOptimizer = ConnectionOptimizer;
    global.BatchRenderer = BatchRenderer;

})(typeof window !== 'undefined' ? window : this);

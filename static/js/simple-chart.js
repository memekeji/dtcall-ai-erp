(function () {
    if (window.Chart) return;

    function toArray(value) {
        return Array.isArray(value) ? value : [];
    }

    function toNumber(value) {
        var n = Number(value);
        return Number.isFinite(n) ? n : 0;
    }

    function fitCanvas(canvas) {
        var rect = canvas.getBoundingClientRect();
        var ratio = window.devicePixelRatio || 1;
        var width = Math.max(rect.width || canvas.parentElement.clientWidth || 300, 240);
        var height = Math.max(rect.height || canvas.parentElement.clientHeight || 220, 180);
        canvas.width = Math.floor(width * ratio);
        canvas.height = Math.floor(height * ratio);
        var ctx = canvas.getContext('2d');
        ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
        return { ctx: ctx, width: width, height: height };
    }

    function hasData(datasets) {
        return datasets.some(function (dataset) {
            return toArray(dataset.data).some(function (value) {
                return toNumber(value) !== 0;
            });
        });
    }

    function drawNoData(ctx, width, height) {
        ctx.save();
        ctx.clearRect(0, 0, width, height);
        ctx.fillStyle = '#9CA3AF';
        ctx.font = '14px Arial, sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('No data', width / 2, height / 2);
        ctx.restore();
    }

    function drawLegend(ctx, datasets, x, y) {
        var cursor = x;
        ctx.save();
        ctx.font = '12px Arial, sans-serif';
        ctx.textBaseline = 'middle';
        datasets.forEach(function (dataset) {
            var label = dataset.label || '';
            if (!label) return;
            ctx.fillStyle = dataset.borderColor || dataset.backgroundColor || '#3B82F6';
            ctx.fillRect(cursor, y - 5, 10, 10);
            ctx.fillStyle = '#6B7280';
            ctx.fillText(label, cursor + 14, y);
            cursor += ctx.measureText(label).width + 42;
        });
        ctx.restore();
    }

    function drawAxis(ctx, width, height, padding, maxValue) {
        ctx.save();
        ctx.strokeStyle = 'rgba(107, 114, 128, 0.2)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(padding.left, padding.top);
        ctx.lineTo(padding.left, height - padding.bottom);
        ctx.lineTo(width - padding.right, height - padding.bottom);
        ctx.stroke();

        ctx.fillStyle = '#9CA3AF';
        ctx.font = '11px Arial, sans-serif';
        ctx.textAlign = 'right';
        ctx.textBaseline = 'middle';
        for (var i = 0; i <= 4; i++) {
            var y = padding.top + (height - padding.top - padding.bottom) * i / 4;
            var value = maxValue * (4 - i) / 4;
            ctx.fillText(Math.round(value).toLocaleString(), padding.left - 8, y);
            ctx.beginPath();
            ctx.moveTo(padding.left, y);
            ctx.lineTo(width - padding.right, y);
            ctx.strokeStyle = 'rgba(107, 114, 128, 0.08)';
            ctx.stroke();
        }
        ctx.restore();
    }

    function drawLine(ctx, width, height, data) {
        var labels = toArray(data.labels);
        var datasets = toArray(data.datasets);
        if (!labels.length || !hasData(datasets)) return drawNoData(ctx, width, height);

        var padding = { top: 34, right: 18, bottom: 30, left: 52 };
        var values = [];
        datasets.forEach(function (dataset) {
            values = values.concat(toArray(dataset.data).map(toNumber));
        });
        var maxValue = Math.max.apply(Math, values.concat([1])) * 1.15;
        drawLegend(ctx, datasets, padding.left, 16);
        drawAxis(ctx, width, height, padding, maxValue);

        var plotWidth = width - padding.left - padding.right;
        var plotHeight = height - padding.top - padding.bottom;
        datasets.forEach(function (dataset) {
            var points = toArray(dataset.data).map(toNumber);
            ctx.save();
            ctx.strokeStyle = dataset.borderColor || '#3B82F6';
            ctx.fillStyle = dataset.backgroundColor || 'rgba(59, 130, 246, 0.12)';
            ctx.lineWidth = dataset.borderWidth || 2;
            ctx.beginPath();
            points.forEach(function (value, index) {
                var x = padding.left + (labels.length === 1 ? plotWidth / 2 : plotWidth * index / (labels.length - 1));
                var y = height - padding.bottom - (value / maxValue) * plotHeight;
                if (index === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            });
            ctx.stroke();
            points.forEach(function (value, index) {
                var x = padding.left + (labels.length === 1 ? plotWidth / 2 : plotWidth * index / (labels.length - 1));
                var y = height - padding.bottom - (value / maxValue) * plotHeight;
                ctx.beginPath();
                ctx.arc(x, y, 3, 0, Math.PI * 2);
                ctx.fillStyle = dataset.borderColor || '#3B82F6';
                ctx.fill();
            });
            ctx.restore();
        });
    }

    function drawBar(ctx, width, height, data) {
        var labels = toArray(data.labels);
        var dataset = toArray(data.datasets)[0] || {};
        var values = toArray(dataset.data).map(toNumber);
        if (!labels.length || !values.some(function (v) { return v !== 0; })) return drawNoData(ctx, width, height);

        var padding = { top: 24, right: 18, bottom: 42, left: 52 };
        var maxValue = Math.max.apply(Math, values.concat([1])) * 1.15;
        drawAxis(ctx, width, height, padding, maxValue);

        var plotWidth = width - padding.left - padding.right;
        var plotHeight = height - padding.top - padding.bottom;
        var gap = 12;
        var barWidth = Math.max((plotWidth - gap * (values.length - 1)) / values.length, 12);
        var colors = toArray(dataset.backgroundColor);
        values.forEach(function (value, index) {
            var x = padding.left + index * (barWidth + gap);
            var h = (value / maxValue) * plotHeight;
            var y = height - padding.bottom - h;
            ctx.fillStyle = colors[index % colors.length] || '#3B82F6';
            ctx.fillRect(x, y, barWidth, h);
        });
        ctx.save();
        ctx.fillStyle = '#9CA3AF';
        ctx.font = '11px Arial, sans-serif';
        ctx.textAlign = 'center';
        labels.forEach(function (label, index) {
            var x = padding.left + index * (barWidth + gap) + barWidth / 2;
            ctx.fillText(String(label).slice(0, 6), x, height - 16);
        });
        ctx.restore();
    }

    function drawDoughnut(ctx, width, height, data, options) {
        var labels = toArray(data.labels);
        var dataset = toArray(data.datasets)[0] || {};
        var values = toArray(dataset.data).map(toNumber);
        var total = values.reduce(function (sum, value) { return sum + Math.max(value, 0); }, 0);
        if (!labels.length || total <= 0) return drawNoData(ctx, width, height);

        var colors = toArray(dataset.backgroundColor);
        var centerX = width / 2;
        var centerY = height / 2 - 8;
        var radius = Math.max(Math.min(width, height) / 2 - 34, 42);
        var cutout = parseInt((options && options.cutout) || '60', 10) / 100;
        var start = -Math.PI / 2;
        values.forEach(function (value, index) {
            var angle = Math.max(value, 0) / total * Math.PI * 2;
            ctx.beginPath();
            ctx.moveTo(centerX, centerY);
            ctx.arc(centerX, centerY, radius, start, start + angle);
            ctx.closePath();
            ctx.fillStyle = colors[index % colors.length] || '#3B82F6';
            ctx.fill();
            start += angle;
        });

        ctx.globalCompositeOperation = 'destination-out';
        ctx.beginPath();
        ctx.arc(centerX, centerY, radius * cutout, 0, Math.PI * 2);
        ctx.fill();
        ctx.globalCompositeOperation = 'source-over';

        ctx.save();
        ctx.font = '12px Arial, sans-serif';
        ctx.textBaseline = 'middle';
        var y = height - 18;
        var x = 12;
        labels.slice(0, 4).forEach(function (label, index) {
            ctx.fillStyle = colors[index % colors.length] || '#3B82F6';
            ctx.fillRect(x, y - 5, 10, 10);
            ctx.fillStyle = '#6B7280';
            ctx.fillText(String(label), x + 14, y);
            x += ctx.measureText(String(label)).width + 42;
        });
        ctx.restore();
    }

    function SimpleChart(context, config) {
        this.canvas = context.canvas || context;
        this.ctx = context.canvas ? context : this.canvas.getContext('2d');
        this.config = config || {};
        this.render = this.render.bind(this);
        this.render();
        SimpleChart.instances.push(this);
    }

    SimpleChart.instances = [];
    SimpleChart.prototype.render = function () {
        var fitted = fitCanvas(this.canvas);
        var ctx = fitted.ctx;
        var width = fitted.width;
        var height = fitted.height;
        var type = this.config.type || 'line';
        var data = this.config.data || {};
        var options = this.config.options || {};
        ctx.clearRect(0, 0, width, height);
        if (type === 'bar') drawBar(ctx, width, height, data);
        else if (type === 'doughnut' || type === 'pie') drawDoughnut(ctx, width, height, data, options);
        else drawLine(ctx, width, height, data);
    };
    SimpleChart.prototype.destroy = function () {};

    var resizeTimer = null;
    window.addEventListener('resize', function () {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(function () {
            SimpleChart.instances.forEach(function (chart) {
                chart.render();
            });
        }, 120);
    });

    window.Chart = SimpleChart;
})();

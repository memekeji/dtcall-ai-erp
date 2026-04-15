FROM python:3.11-slim

# 环境变量设置
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV DJANGO_SETTINGS_MODULE dtcall.settings

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt /app/
RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    pip install gunicorn

# 复制项目代码
COPY . /app/

# 收集静态文件并应用数据迁移 (通常在启动脚本中执行，此处仅做结构准备)
# RUN python manage.py collectstatic --noinput

# 启动脚本
COPY docker-entrypoint.sh /app/
RUN chmod +x /app/docker-entrypoint.sh

# 暴露端口
EXPOSE 8000
EXPOSE 9090

# 启动命令
ENTRYPOINT ["/app/docker-entrypoint.sh"]

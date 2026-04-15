# 贡献指南

感谢您对 DT 企业智能管理系统的关注！我们欢迎任何形式的贡献，包括但不限于代码改进、文档完善、Bug 修复、功能建议等。

## 如何贡献

### 报告问题

如果您发现任何问题或有任何建议，请通过 GitHub Issues 进行报告。请确保提供以下信息：

- 问题的详细描述
- 复现步骤（如果适用）
- 您的环境信息（操作系统、Python 版本等）
- 相关的错误日志或截图

### 提交代码

1. **Fork 仓库**：首先点击仓库页面右上角的 "Fork" 按钮
2. **克隆仓库**：将 Fork 的仓库克隆到本地
   ```bash
   git clone https://github.com/YOUR_USERNAME/dtcall-ai-erp.git
   ```
3. **创建分支**：创建一个新分支进行开发
   ```bash
   git checkout -b feature/your-feature-name
   ```
4. **进行开发**：在分支上进行您的开发工作
5. **提交更改**：提交您的更改
   ```bash
   git commit -m 'Add some feature'
   ```
6. **推送分支**：将分支推送到您的 Fork 仓库
   ```bash
   git push origin feature/your-feature-name
   ```
7. **创建 Pull Request**：在 GitHub 上创建 Pull Request

## 开发规范

### 代码规范

- 遵循 [PEP 8](https://www.python.org/dev/peps/pep-0008/) Python 代码风格指南
- 使用 4 空格缩进
- 保持代码简洁清晰
- 添加适当的注释，特别是复杂逻辑部分

### Django 开发规范

- 遵循 Django 官方最佳实践
- 模型、视图、URL 命名清晰一致
- 使用 Django REST Framework 构建 API
- 遵循项目的应用结构设计

### 提交信息规范

提交信息应清晰描述所做的更改：

- 使用中文或英文
- 使用祈使句
- 第一行不超过 50 个字符
- 如需详细说明，可在正文部分添加

### Pull Request 规范

- 确保代码通过所有测试
- 确保没有引入新的 lint 错误
- 描述清楚 PR 的目的和更改内容
- 关联相关的 Issue（如果适用）

## 项目结构

```
dtcall/
├── apps/                 # Django 应用模块
├── dtcall/              # 项目配置
├── static/             # 静态资源
├── templates/          # 模板文件
├── media/             # 上传文件
├── scripts/           # 运维脚本
└── docs/              # 项目文档
```

## 许可证

通过贡献代码，您同意将您的贡献以 MIT 许可证开源。

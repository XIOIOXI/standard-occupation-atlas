# 标准职业图鉴

面向应届毕业生的求职信息工作台，支持职业目录浏览、岗位搜索与筛选、每日新增岗位和招聘来源追溯。

## 当前功能

- 浏览 SNO 职业目录及关联的原始招聘岗位。
- 按公司、地点、行业、招聘届次、状态和日期检索与筛选。
- 查看每日新增岗位和招聘来源详情。
- 本机运营者手动导入 CSV/XLSX，通过受限的单 Agent 工作流完成增量识别、校验与分类。

统计由确定性代码计算。普通页面浏览不会调用模型；原始岗位标题和来源证据始终保留。项目不抓取招聘网站，也不自动下载招聘信息。简历匹配、个人投递工作区和对话式求职助手属于后续规划。

## 本地启动

克隆时请安装 Git LFS，以取得大文件数据：

```sh
git lfs install
git lfs pull
cd frontend
npm ci
npm run dev
```

前端使用 React + Vite，需要 Node.js 20.19+ 或 22.12+；具体地址以启动输出为准。

```sh
cd frontend
npm run build
npm run preview
```

前端展示数据位于 `data/processed/record_role_classification_v1/full_drafts/sno_v31_reasonable_primary_v4_display/`。相关说明见 [frontend/README.md](frontend/README.md)。

## 本机管理更新

管理后端使用 Python 3.12。现有启动脚本要求根目录存在 `.venv-role-vectors` 虚拟环境；在新机器上可先创建环境：

```powershell
py -3.12 -m venv .venv-role-vectors
.\scripts\start_local_recruitment_console.ps1
```

管理 API 只监听本机回环地址。使用模型模式前，在本机环境变量或 `.env` 配置所需 API Key；密钥不进入前端，也不提交到仓库。部分历史分析脚本具有各自的可选依赖，以上启动步骤针对当前 MVP。

## 目录

- `frontend/`：用户界面与前端测试。
- `backend/`：数据模型、校验、持久化与受限 Agent。
- `scripts/`：导入、增量更新与离线处理工具。
- `data/`：招聘来源、版本化数据、职业目录与可追溯处理结果。
- `docs/`：产品说明、架构与审计记录。
- `tests/`：确定性处理与数据契约测试。

项目边界和数据治理规则见 [AGENTS.md](AGENTS.md)。保留的课程分析等历史模块不属于当前 MVP。

## 验证记录

2026-10-22 清理后前端构建成功，招聘相关后端测试 21 项通过。前端测试 21 项通过，另有 1 项已有失败：`display-occupation-groups.test.mjs` 引用了缺失的历史模块。详情见 [项目清理记录](docs/reports/project-cleanup-2026-10-22.md)。

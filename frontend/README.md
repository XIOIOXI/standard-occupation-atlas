# Graduate Job Search Workbench · Occupation Directory

React + Vite；默认首页为面向应届生的职业目录与每日新增岗位浏览页。

```sh
cd frontend
npm install
npm run dev
```

默认地址由 Vite 输出（通常为 http://127.0.0.1:5173/ ）。需要 Node.js 20.19+ 或 22.12+。

```sh
npm run build
npm run preview
node --test tests/bubble-layout.test.mjs
```

职业目录、每日新增和来源详情使用 `data/processed/record_role_classification_v1/full_drafts/sno_v31_reasonable_primary_v4_display/` 中的只读展示投影；Vite 在开发和构建时提供这些静态 JSON。

普通求职者浏览页面不会调用模型。仅本机运营者可通过“管理更新”打开 CSV/XLSX 上传入口；其本机管理 API 仅绑定回环地址，复用 `scripts/process_recruitment_update.py` 的增量处理。模型模式下，受限招聘更新 Agent 只处理程序识别出的新增岗位，API Key 只保存在后端环境变量或 `.env`，不会进入前端。

用于本机运营更新的启动命令：

```powershell
.\scripts\start_local_recruitment_console.ps1
```

职业目录和每日新增的静态展示数据由处理脚本刷新。现有 Market Map 脚本和课程相关产物是保留的历史/可选能力，不定义当前求职工具台 MVP。

以下命令仍可从现有 frozen artifacts 重建历史 Market Map 投影；它不运行 Agent，也不代表当前用户功能：

```sh
python scripts/build_market_map_data.py
python -m unittest discover -s tests -p test_market_map_data.py -v
```

显示层层级在主 Market Map 产物已存在后单独构建，不重跑全量 Market Map pipeline：

```sh
python scripts/build_market_map_display_hierarchy.py
python -m unittest discover -s tests -p test_market_map_display_hierarchy.py -v
```

当前前端主要结构：

- `App.jsx`：职业图鉴、每日新增、通知和本机管理入口的导航状态。
- `SnoExplorer`、目录气泡与详情组件：职业目录逐级浏览、来源追溯和地点提及展示。
- `DailyUpdatesView`：按原始更新时间浏览每日新增岗位。
- `RecruitmentUpdateAdmin`：仅本机运营者使用的上传、运行状态、真实统计和受限 Agent 决策摘要。
- `UpdateNotifications`：基于持久化批次结果的本机浏览器通知。

职业目录中的数量来自已持久化的原子岗位；模型不能生成或修改统计数。岗位搜索与筛选已实现为前端读取的确定性索引；个人看板、简历匹配和对话式求职助手仍为后续规划。

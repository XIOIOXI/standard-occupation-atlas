# 项目清理记录（2026-10-22）

本次先清理再进行 Git 上传；尚未初始化 Git 或上传文件。未读取或分析完整原始招聘数据，未执行模型请求、重分类或数据迁移。

## 已完成的三个批次

| 批次 | 内容 | 文件数 | 原大小 |
| --- | --- | ---: | ---: |
| 01-cache | backend、scripts、tests 中的 Python 字节码缓存 | 34 | 365,555 字节 |
| 02-old-builds | outputs 下 12 个旧页面构建副本 | 156 | 873,110,893 字节 |
| 03-unrelated-resumes | 个人简历、简历生成脚本及临时文件、旧网页抓取探测文件 | 12 | 846,322 字节 |

共从项目目录移出 202 个文件、874,322,770 字节（约 834 MiB）。先压缩备份，再对压缩包内每个文件验证 SHA-256，确认一致后才删除原文件。三个压缩包共 125,912,446 字节（约 120 MiB），位于项目外，不会随项目提交。

## 保留范围

- 全部原始招聘数据、导入文件、处理后数据、更新批次与撤回档案、taxonomy、模型运行记录及推理结果；这些文件可能参与追溯或离线重建，不能仅按修改日期删除。
- `.venv-role-vectors` 被本机启动脚本依赖，`frontend/node_modules` 是现有前端依赖，均保留。
- `frontend/dist`、`frontend/.preview-build` 和 outputs 中隔离测试环境暂时保留，避免影响现有预览或隔离环境。当前环境无法读取运行进程的完整信息，未据此冒险移除。
- 全部应用源码及现有测试保留。仅无关的简历生成脚本和两个网页探测结果归档移出。

补充了根目录 `.gitignore`，排除环境配置、依赖、Python 缓存、日志、构建预览、本机 outputs、临时目录和根目录个人 Word 文档；不会删除被忽略的文件。

## 验证结果

- 清理前、清理缓存后、全部清理后的招聘相关后端测试均为 21 项通过。
- 清理前后前端生产构建均成功，13 个构建文件的 SHA-256 全部一致，包括职业目录、每日新增、来源证据、搜索索引与静态资源。
- 清理前后前端测试均为 21 项通过、1 项失败。原有失败来自 `frontend/tests/display-occupation-groups.test.mjs` 引用不存在的 `frontend/src/lib/displayOccupationGroups.js`，不是此次清理造成；未删测试或修改业务逻辑来隐藏失败。
- 验证未启动真实增量更新，未调用付费模型。现有构建的大文件警告仍保留。

## 备份和恢复

备份目录：

`C:\Users\25223\.codex\visualizations\2026\10\22\01a1630b-f53d-7ad0-bf9e-e6d5753771cc\project-cleanup-backup`

每批都有同名 `.zip` 和 `.manifest.json`，清单包含原始相对路径、大小和 SHA-256。备份目录含个人简历，应保留在本机，不上传 GitHub。

在项目根目录执行下列命令可恢复某一批（把最后参数替换为另外两个批次名即可）：

```powershell
.\.venv-role-vectors\Scripts\python.exe -B 'C:\Users\25223\.codex\visualizations\2026\10\22\01a1630b-f53d-7ad0-bf9e-e6d5753771cc\project-cleanup-backup\restore.py' 02-old-builds
```

批次名为 `01-cache`、`02-old-builds`、`03-unrelated-resumes`。恢复工具验证校验值，不覆盖内容不同的现有文件。备份目录另外保留校验结果 `verification.json`、构建和测试日志、修改前的 `.gitignore` 内容。

# Agent Instructions

## 工具使用优先级

- 多步骤任务：使用 `task_create` / `task_update` / `task_list`
- 短期清单：使用 `TodoWrite`
- 复杂查询：使用 `task` 委托子 agent
- 专业知识：使用 `load_skill` 加载技能

## 心跳任务

`HEARTBEAT.md` 定义周期性检查任务：

- **添加任务**：`edit_file` 追加内容
- **删除任务**：`edit_file` 移除已完成项
- **重写全部**：`write_file` 替换

## 代码风格

- 保持简洁，避免过度设计
- 优先修改现有文件而非创建新文件
- 注释仅在逻辑不明显时添加
后端任务完成：

## 1. trips.py - 增加 exclude_conflicts 参数

`list_trips` 函数新增 `exclude_conflicts` 参数：
- 接收布尔值（`?exclude_conflicts=true`）
- 如果为 True，自动检测每个行程是否与用户现有任务/行程冲突
- 冲突定义：deadline 在用户已有日程的 ±2 小时内
- 返回结果包含 `conflicts` 列表，记录所有冲突信息
- 每个冲突行程包含 `_has_conflicts: true` 和 `_conflicts` 字段

新增辅助函数 `get_user_conflicts(user_id, deadline)` 用于检测冲突。

## 2. schedule.py -增强 get_schedule_items 返回格式

`get_schedule_items` 返回字段更新为：
- `id`, `title`, `type`, `day`, `hour`, `time`, `date`, `completed`, `deadline`, `participant_count`, `max_participants`, `description`

新增 `group_items_by_date(items)` 函数：
- 将日程按今天/明天/后天/XX日后分组
- 不显示过去的任务（due_date < today）
- 返回结构：`{'today': [...], 'tomorrow': [...], 'day_after_tomorrow': [...], 'future': {'N days': [...]}}`

`view_schedule` 视图函数新增传递 `list_groups` 变量给模板。

请 review。
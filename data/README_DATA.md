# 数据说明

## 开源范围

| 内容 | 是否包含 | 说明 |
|------|----------|------|
| `bus_rice_data` 表结构 | ✅ | `schema/ddl/01_bus_rice_data.sql` |
| `bus_rice_data` 商业品种记录 | ✅ | `data/bus_rice_data.sql`（MySQL dump，约 3.1 MB） |
| `bus_rice_cache_results` | ✅ 结构 | 运行时由工作流写入 |
| `chat_memory` / `request_status` | ✅ 结构 | 见 `schema/ddl/` |

## 导入

```bash
mysql -u root -p cropmonster_demo < schema/ddl/01_bus_rice_data.sql
mysql -u root -p cropmonster_demo < data/bus_rice_data.sql
mysql -u root -p cropmonster_demo < schema/ddl/02_bus_rice_cache_results.sql
```

`bus_rice_data.sql` 已包含 `DROP TABLE` 与 `INSERT`，可直接导入；若表已存在且仅需增量数据，请先备份后执行。

## 与工作流的关系

- 请求体设置 `"commercialMode": true` 且作物为水稻时，工作流路由到 `bus_rice` / `bus_rice_data`。

## 合规提示

公开仓库前请确认商业品种数据的发布范围符合单位与数据提供方协议；若仅允许私有部署，请勿将 `bus_rice_data.sql` 推送到公开 GitHub。

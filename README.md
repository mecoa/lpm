# LPM - 本地包管理器

## 项目简介

LPM（Local Package Manager）是一个轻量级的本地文件管理与追踪工具，用于追踪和管理本地文件的安装、查询和卸载操作。所有追踪信息存储在用户主目录下的 SQLite 数据库中。

## 功能特性

- **安装追踪**：记录从源文件复制到目标目录的所有文件
- **列表查看**：以多种视图查看已安装的软件及其文件
- **安全卸载**：自动删除已安装的文件并清理数据库记录
- **搜索功能**：根据软件名称或文件路径快速查找
- **取消追踪**：停止追踪文件而不删除实际文件
- **数据持久化**：使用 SQLite 数据库，数据永久保存

## 安装要求

- Python 3.12 或更高版本
- 依赖包：click ≥ 8.3.2

## 快速开始

### 1. 安装项目

```bash
# 使用 pip 安装
pip install -e .

# 或使用 uv（推荐）
uv pip install -e .
```

### 2. 验证安装

```bash
lpm --version
# 输出：LPM, version 0.1.1
```

## 命令详解

### `lpm install` - 安装文件

从源文件复制到目标目录并开始追踪。

```bash
lpm install <源文件路径> <软件名称> <安装目录>
```

**参数说明：**
- `源文件路径`：要安装的文件或目录路径（必须存在）
- `软件名称`：软件的唯一标识名称，用于分组管理
- `安装目录`：文件要复制到的目标目录

**示例：**
```bash
# 安装单个文件
lpm install ~/Downloads/app.exe myapp ~/Applications

# 安装整个目录（保留目录结构）
lpm install ~/Downloads/software_package mysoftware /opt/apps
```

**特性：**
- 自动创建目标目录
- 保留文件的元数据（使用 `shutil.copy2`）
- 检测重复安装：同一软件名称只能安装一次，需先卸载旧版本
- 支持事务回滚：安装失败时自动清理已复制的文件

---

### `lpm list` - 列出追踪的文件

查看已追踪的文件，支持三种显示模式。

```bash
# 模式1：汇总视图（默认）
lpm list
# 输出示例：
# myapp: 5 files installed at 2025-04-13T14:30:00
# mysoftware: 12 files installed at 2025-04-12T09:15:00

# 模式2：查看特定软件的文件
lpm list --software myapp
# 或简写：
lpm list -s myapp

# 模式3：查看所有追踪记录
lpm list --all
# 或简写：
lpm list -a
```

---

### `lpm uninstall` - 卸载软件

删除指定软件的所有已安装文件并清除数据库记录。

```bash
lpm uninstall <软件名称> [--force]
```

**参数说明：**
- `软件名称`：要卸载的软件名称
- `--force` / `-f`：强制卸载，即使文件已不存在也清除数据库记录

**示例：**
```bash
# 正常卸载
lpm uninstall myapp

# 强制卸载（清理残缺记录）
lpm uninstall myapp --force
```

**行为说明：**
1. 删除所有实际存在的文件
2. 显示已删除和缺失的文件数量统计
3. 从数据库中移除所有追踪记录

---

### `lpm search` - 搜索文件

根据关键词搜索被追踪的文件。

```bash
lpm search <关键词>
```

**搜索范围：**
- 文件完整路径
- 软件名称

**示例：**
```bash
lpm search myapp
# 输出示例：
# Found 2 result(s):
#   [1] /home/user/.local/share/myapp/config.json
#       Software: myapp | Installed: 2025-04-13T14:30:00
```

---

### `lpm untrack` - 取消追踪

停止追踪指定文件，但保留实际文件。

```bash
lpm untrack <文件路径>
```

**与 `uninstall` 的区别：**
- `uninstall`：删除文件 + 清除记录
- `untrack`：仅清除记录，文件保留在原处

**示例：**
```bash
lpm untrack ~/Applications/myapp/config.json
```

## 数据库结构

LPM 使用 SQLite 数据库存储追踪信息，位置：`~/.lpm/tracked_files.db`

### 表结构：`tracked_files`

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER | 自增主键，唯一标识 |
| `file_path` | TEXT | 文件的绝对路径（唯一约束） |
| `software_name` | TEXT | 软件名称 |
| `installed_at` | TIMESTAMP | 文件安装时间（ISO 格式） |
| `created_at` | TIMESTAMP | 数据库记录创建时间（自动填充） |

**索引与约束：**
- `file_path` 字段具有唯一约束，防止重复追踪同一文件
- 按 `software_name` 分组可查询聚合信息

### 小巧思
是不是可以给ai用，或许可以做成skills
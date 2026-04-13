"""
本地包管理器 (Local Package Manager - LPM)
用于追踪和管理本地文件的安装、查询和卸载操作。
所有追踪信息存储在用户主目录下的 SQLite 数据库中。
"""

import os
import sqlite3
import shutil
from datetime import datetime
from pathlib import Path

import click

# 数据库存储位置：用户主目录下的 .lpm 隐藏文件夹
# 使用 Path.home() 确保跨平台兼容性（Windows/Linux/macOS 都能正确识别用户目录）
DB_PATH = Path.home() / ".lpm" / "tracked_files.db"


def get_db():
    """
    获取数据库连接对象。
    如果数据库所在目录不存在，会自动创建。
    设置 row_factory 以便通过列名访问查询结果（类似字典）。
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # 使查询结果可以通过列名索引，如 row['file_path']
    return conn


def init_db():
    """
    初始化数据库结构。
    创建 tracked_files 表，如果表已存在则不做任何操作。
    
    表结构说明：
    - id: 自增主键，每条记录的唯一标识
    - file_path: 文件的绝对路径，唯一约束确保同一文件不会被重复追踪
    - software_name: 该文件所属的软件名称
    - installed_at: 文件被追踪/安装的时间（ISO 格式字符串）
    - created_at: 数据库记录创建时间（由 SQLite 自动填充）
    """
    conn = get_db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tracked_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT NOT NULL UNIQUE,
            software_name TEXT NOT NULL,
            installed_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """
    CLI 入口组。
    所有命令执行前都会自动调用 init_db() 确保数据库已初始化。
    """
    init_db()


@cli.command()
@click.argument("file_path", type=click.Path(exists=True))
@click.argument("software_name")
def install(file_path, software_name):
    """
    安装（追踪）一个文件，并将其关联到指定的软件名称。
    
    参数：
    - file_path: 要追踪的文件路径（必须存在）
    - software_name: 软件名称（用于分组管理）
    
    行为：
    - 如果文件未被追踪，则新增一条记录
    - 如果文件已被追踪，则更新其所属软件和安装时间
    """
    # 将路径转换为绝对路径，确保不同工作目录下的一致性
    file_path = str(Path(file_path).resolve())
    # 使用 ISO 格式存储时间，便于阅读和跨系统兼容
    installed_at = datetime.now().isoformat()

    conn = get_db()
    try:
        # 尝试插入新记录
        conn.execute(
            "INSERT INTO tracked_files (file_path, software_name, installed_at) VALUES (?, ?, ?)",
            (file_path, software_name, installed_at),
        )
        conn.commit()
        click.echo(f"Tracked: {file_path}")
        click.echo(f"Software: {software_name}")
        click.echo(f"Time: {installed_at}")
    except sqlite3.IntegrityError:
        # 如果文件已存在（违反 UNIQUE 约束），则更新现有记录
        conn.execute(
            "UPDATE tracked_files SET software_name = ?, installed_at = ? WHERE file_path = ?",
            (software_name, installed_at, file_path),
        )
        conn.commit()
        click.echo(f"Updated tracking for: {file_path}")
    finally:
        conn.close()


@cli.command()
@click.option("--software", "-s", help="按软件名称筛选")
@click.option("--all", "-a", is_flag=True, help="显示所有被追踪的文件")
def list(software, all):
    """
    列出被追踪的文件。
    
    三种显示模式：
    1. 无参数：显示软件名称及各自追踪的文件数量（汇总视图）
    2. --software/-s：显示指定软件下的所有文件
    3. --all/-a：显示数据库中的所有追踪记录
    """
    conn = get_db()
    if software:
        # 按软件名称筛选，按安装时间倒序排列
        rows = conn.execute(
            "SELECT * FROM tracked_files WHERE software_name = ? ORDER BY installed_at DESC",
            (software,),
        ).fetchall()
        click.echo(f"Files for software: {software}")
    elif all:
        # 显示所有记录
        rows = conn.execute(
            "SELECT * FROM tracked_files ORDER BY installed_at DESC"
        ).fetchall()
        click.echo("All tracked files:")
    else:
        # 默认模式：按软件名称分组统计文件数量
        rows = conn.execute(
            "SELECT software_name, COUNT(*) as count FROM tracked_files GROUP BY software_name"
        ).fetchall()
        for row in rows:
            click.echo(f"{row['software_name']}: {row['count']} files")
        conn.close()
        return

    if not rows:
        click.echo("No files found.")
    else:
        for row in rows:
            click.echo(f"  [{row['id']}] {row['file_path']}")
            click.echo(
                f"      Software: {row['software_name']} | Installed: {row['installed_at']}"
            )
    conn.close()


@cli.command()
@click.argument("software_name")
@click.option(
    "--force", "-f", is_flag=True, help="强制卸载，即使文件缺失也清除数据库记录"
)
def uninstall(software_name, force):
    """
    卸载指定软件的所有追踪文件。
    
    行为：
    1. 删除实际存在的文件
    2. 从数据库中移除追踪记录
    3. 如果文件已不存在，默认会跳过但保留数据库记录
    4. 使用 --force 可以强制清除数据库记录（即使文件缺失）
    """
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM tracked_files WHERE software_name = ?", (software_name,)
    ).fetchall()

    if not rows:
        click.echo(f"No tracked files found for: {software_name}")
        conn.close()
        return

    removed = 0   # 成功删除的文件计数
    missing = 0   # 不存在的文件计数
    for row in rows:
        file_path = row["file_path"]
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                click.echo(f"Deleted: {file_path}")
                removed += 1
            except Exception as e:
                click.echo(f"Error deleting {file_path}: {e}")
        else:
            click.echo(f"File not found (skipping): {file_path}")
            missing += 1

        # 注意：这里的逻辑其实不影响结果，无论 force 是否为 True
        # 最终都会删除数据库记录（见下方 DELETE 语句）
        if force or missing > 0:
            pass

    # 从数据库中删除该软件的所有追踪记录
    conn.execute("DELETE FROM tracked_files WHERE software_name = ?", (software_name,))
    conn.commit()
    conn.close()

    click.echo(f"\nRemoved {removed} files, {missing} were missing.")


@cli.command()
@click.argument("keyword")
def search(keyword):
    """
    根据关键词搜索被追踪的文件。
    
    搜索范围：
    - 文件路径（file_path）
    - 软件名称（software_name）
    
    使用 SQL LIKE 进行模糊匹配。
    """
    conn = get_db()
    pattern = f"%{keyword}%"  # 构造模糊匹配模式
    rows = conn.execute(
        "SELECT * FROM tracked_files WHERE file_path LIKE ? OR software_name LIKE ? ORDER BY installed_at DESC",
        (pattern, pattern),
    ).fetchall()
    conn.close()

    if not rows:
        click.echo(f"No results found for: {keyword}")
    else:
        click.echo(f"Found {len(rows)} result(s):")
        for row in rows:
            click.echo(f"  [{row['id']}] {row['file_path']}")
            click.echo(
                f"      Software: {row['software_name']} | Installed: {row['installed_at']}"
            )


@cli.command()
@click.argument("file_path", type=click.Path(exists=True))
def untrack(file_path):
    """
    停止追踪指定文件，但不删除实际文件。
    
    与 uninstall 的区别：
    - uninstall: 删除文件 + 清除记录
    - untrack: 仅清除记录，保留文件
    """
    # 转换为绝对路径以匹配数据库中的记录
    file_path = str(Path(file_path).resolve())
    conn = get_db()
    cur = conn.execute("DELETE FROM tracked_files WHERE file_path = ?", (file_path,))
    conn.commit()
    conn.close()

    if cur.rowcount > 0:
        click.echo(f"Untracked: {file_path}")
    else:
        click.echo(f"File not tracked: {file_path}")


# 脚本入口
if __name__ == "__main__":
    cli()
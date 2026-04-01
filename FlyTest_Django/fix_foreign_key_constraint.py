"""修复外键约束错误 - 清理 agent_execution 表中的孤儿记录"""
import sqlite3
import os
from pathlib import Path

# 数据库路径
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / 'db.sqlite3'

print(f"数据库路径: {DB_PATH}")

if not DB_PATH.exists():
    print("❌ 数据库文件不存在!")
    exit(1)

# 连接数据库
conn = sqlite3.connect(str(DB_PATH))
cursor = conn.cursor()

try:
    # 1. 检查 agent_execution 表是否存在
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='agent_execution'
    """)
    
    if cursor.fetchone() is None:
        print("✅ agent_execution 表不存在,无需清理")
    else:
        print("🔍 发现 agent_execution 表")
        
        # 2. 查看孤儿记录
        cursor.execute("""
            SELECT COUNT(*) FROM agent_execution 
            WHERE task_id NOT IN (SELECT id FROM orchestrator_task)
        """)
        orphan_count = cursor.fetchone()[0]
        
        if orphan_count > 0:
            print(f"⚠️  发现 {orphan_count} 条孤儿记录")
            
            # 3. 删除孤儿记录
            cursor.execute("""
                DELETE FROM agent_execution 
                WHERE task_id NOT IN (SELECT id FROM orchestrator_task)
            """)
            conn.commit()
            print(f"✅ 已删除 {cursor.rowcount} 条孤儿记录")
        else:
            print("✅ 没有孤儿记录")
    
    print("\n🎉 数据库清理完成!")
    
except Exception as e:
    print(f"❌ 错误: {e}")
    conn.rollback()
finally:
    conn.close()

print("\n现在可以运行: uv run python manage.py migrate orchestrator_integration")
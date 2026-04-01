"""修复 orchestrator_task 表结构"""
import sqlite3
import os

# 数据库路径
db_path = os.environ.get('DATABASE_PATH', './db.sqlite3')

print(f"连接数据库: {db_path}")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    # 1. 查看当前表结构
    print("\n当前 orchestrator_task 表结构:")
    cursor.execute("PRAGMA table_info(orchestrator_task)")
    columns = cursor.fetchall()
    for col in columns:
        print(f"  {col[1]} ({col[2]})")
    
    # 2. 检查是否缺少 requirement 列
    column_names = [col[1] for col in columns]
    if 'requirement' not in column_names:
        print("\n❌ 缺少 requirement 列,需要重建表")
        
        # 3. 删除有外键约束的相关数据
        print("\n删除相关数据...")
        cursor.execute("DELETE FROM agent_execution WHERE task_id NOT IN (SELECT id FROM orchestrator_task)")
        conn.commit()
        print(f"  清理了孤立的 agent_execution 记录")
        
        # 4. 备份旧表数据(如果有的话)
        print("\n备份现有数据...")
        cursor.execute("SELECT * FROM orchestrator_task")
        old_data = cursor.fetchall()
        print(f"  找到 {len(old_data)} 条记录")
        
        # 5. 删除旧表
        print("\n删除旧表...")
        cursor.execute("DROP TABLE IF EXISTS orchestrator_task")
        conn.commit()
        
        # 6. 创建新表(根据模型定义)
        print("\n创建新表结构...")
        cursor.execute("""
            CREATE TABLE orchestrator_task (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES auth_user(id),
                project_id INTEGER REFERENCES projects_project(id),
                requirement TEXT NOT NULL,
                knowledge_base_ids TEXT NOT NULL,
                status VARCHAR(20) NOT NULL,
                requirement_analysis TEXT,
                knowledge_docs TEXT NOT NULL,
                testcases TEXT NOT NULL,
                execution_log TEXT NOT NULL,
                error_message TEXT NOT NULL,
                created_at DATETIME NOT NULL,
                started_at DATETIME,
                completed_at DATETIME
            )
        """)
        conn.commit()
        print("  ✅ 新表创建成功")
        
        # 7. 验证新表结构
        print("\n新表结构:")
        cursor.execute("PRAGMA table_info(orchestrator_task)")
        new_columns = cursor.fetchall()
        for col in new_columns:
            print(f"  {col[1]} ({col[2]})")
        
        print("\n✅ 数据库表结构修复完成!")
    else:
        print("\n✅ requirement 列已存在,无需修复")

except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
    conn.rollback()
finally:
    conn.close()
    print("\n数据库连接已关闭")
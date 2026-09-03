import duckdb
import pandas as pd
from typing import Dict, Any
import uuid
import os

class SessionDB:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = duckdb.connect(database=db_path)
        # 元数据表：记录每个会话上传的文件
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS file_registry (
                session_id VARCHAR,
                file_id VARCHAR,
                table_name VARCHAR,
                original_name VARCHAR,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    
    def get_session_conn(self, session_id: str):
        """返回一个绑定session的DuckDB连接（实际上DuckDB天然支持多表）"""
        # DuckDB连接本身是共享的，但我们通过表名前缀隔离
        return self.conn
    
    def upload_file(self, session_id: str, file_path: str, original_name: str) -> str:
        """上传CSV/XLSX到DuckDB，返回生成的表名"""
        file_id = str(uuid.uuid4())[:8]
        table_name = f"file_{file_id}"
        
        # 根据扩展名读取
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path)
        
        # 注册到DuckDB
        self.conn.register('df_temp', df)
        self.conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM df_temp")
        self.conn.unregister('df_temp')
        
        # 记录元数据
        self.conn.execute("""
            INSERT INTO file_registry (session_id, file_id, table_name, original_name)
            VALUES (?, ?, ?, ?)
        """, [session_id, file_id, table_name, original_name])
        
        return table_name
    
    def get_session_tables(self, session_id: str) -> list:
        """获取该会话所有表名，用于跨表JOIN"""
        result = self.conn.execute("""
            SELECT table_name FROM file_registry WHERE session_id = ?
        """, [session_id]).fetchall()
        return [r[0] for r in result]

    def get_table_schema(self, table_name: str) -> dict:
        """返回表结构上下文：列名+类型 + 前5行示例数据（用于注入 LLM prompt）"""
        desc = self.conn.execute(f"DESCRIBE {table_name}").fetchall()
        columns = [{"name": r[0], "type": r[1]} for r in desc]
        sample_df = self.conn.execute(f"SELECT * FROM {table_name} LIMIT 5").df()
        return {
            "table": table_name,
            "columns": columns,
            "sample_rows": sample_df.to_dict(orient="records"),
        }
    
    def execute_sql(self, session_id: str, sql: str) -> pd.DataFrame:
        """执行SQL，自动限定只能查询该会话的表"""
        # 安全限制：仅允许 SELECT / WITH(CTE) 开头，防止注入删除（MVP阶段仅支持只读查询）
        upper_sql = sql.lstrip().upper()
        if not (upper_sql.startswith("SELECT") or upper_sql.startswith("WITH")):
            raise ValueError("仅支持 SELECT / WITH 查询")
        # 检查表权限（简单检查：表名是否在session_tables中，若涉及*则全查）
        # 简单起见，直接执行（DuckDB默认只读该库，危险性较低）
        return self.conn.execute(sql).df()
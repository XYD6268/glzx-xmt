"""
PostgreSQL查询优化工具
"""
from sqlalchemy import text, func
from models.base import db
import logging

logger = logging.getLogger(__name__)


class QueryOptimizer:
    """PostgreSQL查询优化器"""
    
    @staticmethod
    def analyze_table(table_name: str):
        """分析表统计信息"""
        try:
            db.session.execute(text(f"ANALYZE {table_name}"))
            db.session.commit()
            logger.info(f"已分析表: {table_name}")
        except Exception as e:
            logger.error(f"分析表失败 {table_name}: {e}")
    
    @staticmethod
    def vacuum_table(table_name: str, full: bool = False):
        """清理表"""
        try:
            vacuum_cmd = f"VACUUM {'FULL' if full else ''} {table_name}"
            db.session.execute(text(vacuum_cmd))
            db.session.commit()
            logger.info(f"已清理表: {table_name}")
        except Exception as e:
            logger.error(f"清理表失败 {table_name}: {e}")
    
    @staticmethod
    def reindex_table(table_name: str):
        """重建表索引"""
        try:
            db.session.execute(text(f"REINDEX TABLE {table_name}"))
            db.session.commit()
            logger.info(f"已重建索引: {table_name}")
        except Exception as e:
            logger.error(f"重建索引失败 {table_name}: {e}")
    
    @staticmethod
    def get_table_stats(table_name: str) -> dict:
        """获取表统计信息"""
        try:
            result = db.session.execute(text("""
                SELECT 
                    schemaname,
                    tablename,
                    attname,
                    inherited,
                    null_frac,
                    avg_width,
                    n_distinct,
                    most_common_vals,
                    most_common_freqs,
                    histogram_bounds
                FROM pg_stats 
                WHERE tablename = :table_name
            """), {'table_name': table_name}).fetchall()
            
            return [dict(row) for row in result]
        except Exception as e:
            logger.error(f"获取表统计失败 {table_name}: {e}")
            return []
    
    @staticmethod
    def get_slow_queries() -> list:
        """获取慢查询（需要pg_stat_statements扩展）"""
        try:
            result = db.session.execute(text("""
                SELECT 
                    query,
                    calls,
                    total_time,
                    mean_time,
                    stddev_time,
                    rows
                FROM pg_stat_statements 
                WHERE mean_time > 1000  -- 超过1秒的查询
                ORDER BY mean_time DESC 
                LIMIT 20
            """)).fetchall()
            
            return [dict(row) for row in result]
        except Exception as e:
            logger.warning(f"获取慢查询失败（可能需要安装pg_stat_statements）: {e}")
            return []
    
    @staticmethod
    def optimize_all_tables():
        """优化所有表"""
        tables = ['users', 'photos', 'votes', 'login_records', 'settings']
        
        for table in tables:
            QueryOptimizer.analyze_table(table)
    
    @staticmethod
    def create_custom_indexes():
        """创建自定义索引"""
        try:
            # 照片复合索引
            db.session.execute(text("""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_photos_status_votes 
                ON photos (status, vote_count DESC, created_at DESC)
            """))
            
            # 投票时间索引
            db.session.execute(text("""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_votes_created_at
                ON votes (created_at DESC)
            """))
            
            # 用户登录索引
            db.session.execute(text("""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_login_records_user_time
                ON login_records (user_id, created_at DESC)
            """))
            
            db.session.commit()
            logger.info("自定义索引创建完成")
            
        except Exception as e:
            logger.error(f"创建自定义索引失败: {e}")


class BatchProcessor:
    """批量处理工具"""
    
    @staticmethod
    def batch_update(model_class, updates: list, batch_size: int = 100):
        """批量更新"""
        try:
            for i in range(0, len(updates), batch_size):
                batch = updates[i:i + batch_size]
                
                for update_data in batch:
                    instance = model_class.query.get(update_data['id'])
                    if instance:
                        for key, value in update_data.items():
                            if key != 'id' and hasattr(instance, key):
                                setattr(instance, key, value)
                
                db.session.commit()
                logger.info(f"批量更新完成: {len(batch)} 条记录")
                
        except Exception as e:
            db.session.rollback()
            logger.error(f"批量更新失败: {e}")
            raise
    
    @staticmethod
    def batch_delete(model_class, ids: list, batch_size: int = 100):
        """批量删除"""
        try:
            for i in range(0, len(ids), batch_size):
                batch_ids = ids[i:i + batch_size]
                model_class.query.filter(model_class.id.in_(batch_ids)).delete(synchronize_session=False)
                db.session.commit()
                logger.info(f"批量删除完成: {len(batch_ids)} 条记录")
                
        except Exception as e:
            db.session.rollback()
            logger.error(f"批量删除失败: {e}")
            raise


class ConnectionManager:
    """数据库连接管理"""
    
    @staticmethod
    def get_connection_info() -> dict:
        """获取连接信息"""
        try:
            result = db.session.execute(text("""
                SELECT 
                    count(*) as total_connections,
                    count(*) FILTER (WHERE state = 'active') as active_connections,
                    count(*) FILTER (WHERE state = 'idle') as idle_connections
                FROM pg_stat_activity 
                WHERE datname = current_database()
            """)).fetchone()
            
            return dict(result)
        except Exception as e:
            logger.error(f"获取连接信息失败: {e}")
            return {}
    
    @staticmethod
    def kill_idle_connections(idle_minutes: int = 30):
        """杀死空闲连接"""
        try:
            result = db.session.execute(text("""
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity 
                WHERE datname = current_database()
                AND state = 'idle'
                AND state_change < now() - interval ':minutes minutes'
                AND pid <> pg_backend_pid()
            """), {'minutes': idle_minutes})
            
            terminated_count = len(result.fetchall())
            logger.info(f"终止了 {terminated_count} 个空闲连接")
            return terminated_count
            
        except Exception as e:
            logger.error(f"终止空闲连接失败: {e}")
            return 0


def setup_postgresql_optimizations():
    """设置PostgreSQL优化"""
    try:
        # 设置工作内存
        db.session.execute(text("SET work_mem = '256MB'"))
        
        # 设置随机页面成本
        db.session.execute(text("SET random_page_cost = 1.1"))
        
        # 设置有效缓存大小
        db.session.execute(text("SET effective_cache_size = '4GB'"))
        
        db.session.commit()
        logger.info("PostgreSQL优化设置完成")
        
    except Exception as e:
        logger.error(f"PostgreSQL优化设置失败: {e}")


def create_database_extensions():
    """创建数据库扩展"""
    extensions = [
        'pg_stat_statements',  # 查询统计
        'pg_trgm',            # 相似度搜索
        'unaccent',           # 去除重音符号
        'uuid-ossp'           # UUID生成
    ]
    
    for ext in extensions:
        try:
            db.session.execute(text(f"CREATE EXTENSION IF NOT EXISTS \"{ext}\""))
            db.session.commit()
            logger.info(f"扩展 {ext} 已启用")
        except Exception as e:
            logger.warning(f"启用扩展 {ext} 失败: {e}")
            db.session.rollback()
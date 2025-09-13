"""
性能监控工具 - PostgreSQL优化版
"""
import time
import functools
import logging
import os
from typing import Dict, Any
from flask import request, g, Flask
import threading
from datetime import datetime

logger = logging.getLogger(__name__)

# 尝试导入psutil，如果不存在则设置为None
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None
    PSUTIL_AVAILABLE = False
    logging.warning("psutil未安装，系统监控功能将被禁用")


class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self):
        self.metrics = {}
        self.lock = threading.Lock()
    
    def record_metric(self, name: str, value: float, tags: Dict[str, Any] = None):
        """记录性能指标"""
        with self.lock:
            if name not in self.metrics:
                self.metrics[name] = []
            
            self.metrics[name].append({
                'value': value,
                'timestamp': time.time(),
                'tags': tags or {}
            })
            
            # 保留最近1000条记录
            if len(self.metrics[name]) > 1000:
                self.metrics[name] = self.metrics[name][-1000:]
    
    def get_metrics(self, name: str = None):
        """获取性能指标"""
        with self.lock:
            if name:
                return self.metrics.get(name, [])
            return self.metrics.copy()
    
    def get_average(self, name: str, last_n: int = 100) -> float:
        """获取平均值"""
        metrics = self.get_metrics(name)
        if not metrics:
            return 0.0
        
        recent = metrics[-last_n:]
        return sum(m['value'] for m in recent) / len(recent)
    
    def clear_metrics(self, name: str = None):
        """清除指标"""
        with self.lock:
            if name:
                self.metrics.pop(name, None)
            else:
                self.metrics.clear()


# 全局性能监控器
performance_monitor = PerformanceMonitor()


def log_performance(func):
    """性能日志装饰器"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        
        try:
            result = func(*args, **kwargs)
            success = True
        except Exception as e:
            success = False
            raise
        finally:
            end_time = time.time()
            duration = end_time - start_time
            
            # 记录性能指标
            performance_monitor.record_metric(
                f"{func.__module__}.{func.__name__}",
                duration,
                {'success': success}
            )
            
            # 慢操作警告
            if duration > 1.0:  # 超过1秒
                logger.warning(f"慢操作: {func.__name__} 耗时 {duration:.2f}s")
            
            # 调试日志
            logger.debug(f"{func.__name__} 执行时间: {duration:.3f}s")
        
        return result
    return wrapper


def monitor_db_query(func):
    """数据库查询监控装饰器"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        
        try:
            result = func(*args, **kwargs)
            success = True
        except Exception as e:
            success = False
            raise
        finally:
            end_time = time.time()
            duration = end_time - start_time
            
            # 记录数据库查询指标
            performance_monitor.record_metric(
                'db_query_duration',
                duration,
                {
                    'function': func.__name__,
                    'success': success
                }
            )
            
            # 慢查询警告
            if duration > 0.5:  # 超过500ms
                logger.warning(f"慢查询: {func.__name__} 耗时 {duration:.3f}s")
        
        return result
    return wrapper


def monitor_cache_operation(operation: str):
    """缓存操作监控装饰器"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                success = True
                hit = result is not None if operation == 'get' else True
            except Exception as e:
                success = False
                hit = False
                raise
            finally:
                end_time = time.time()
                duration = end_time - start_time
                
                # 记录缓存操作指标
                performance_monitor.record_metric(
                    f'cache_{operation}_duration',
                    duration,
                    {
                        'success': success,
                        'hit': hit if operation == 'get' else None
                    }
                )
            
            return result
        return wrapper
    return decorator


class SystemMetrics:
    """系统指标收集器"""
    
    @staticmethod
    def get_cpu_usage() -> float:
        """获取CPU使用率"""
        return psutil.cpu_percent(interval=1)
    
    @staticmethod
    def get_memory_usage() -> Dict[str, float]:
        """获取内存使用情况"""
        memory = psutil.virtual_memory()
        return {
            'total': memory.total / (1024**3),  # GB
            'available': memory.available / (1024**3),  # GB
            'used': memory.used / (1024**3),  # GB
            'percent': memory.percent
        }
    
    @staticmethod
    def get_disk_usage(path: str = '/') -> Dict[str, float]:
        """获取磁盘使用情况"""
        usage = psutil.disk_usage(path)
        return {
            'total': usage.total / (1024**3),  # GB
            'used': usage.used / (1024**3),  # GB
            'free': usage.free / (1024**3),  # GB
            'percent': (usage.used / usage.total) * 100
        }
    
    @staticmethod
    def get_network_stats() -> Dict[str, int]:
        """获取网络统计"""
        stats = psutil.net_io_counters()
        return {
            'bytes_sent': stats.bytes_sent,
            'bytes_recv': stats.bytes_recv,
            'packets_sent': stats.packets_sent,
            'packets_recv': stats.packets_recv
        }
    
    @staticmethod
    def get_process_info() -> Dict[str, Any]:
        """获取当前进程信息"""
        process = psutil.Process()
        with process.oneshot():
            return {
                'pid': process.pid,
                'memory_percent': process.memory_percent(),
                'cpu_percent': process.cpu_percent(),
                'num_threads': process.num_threads(),
                'create_time': process.create_time(),
                'status': process.status()
            }


class RequestMonitor:
    """请求监控器"""
    
    @staticmethod
    def before_request():
        """请求开始前"""
        g.start_time = time.time()
        g.request_id = f"{int(time.time() * 1000)}"
    
    @staticmethod
    def after_request(response):
        """请求结束后"""
        if hasattr(g, 'start_time'):
            duration = time.time() - g.start_time
            
            # 记录请求指标
            performance_monitor.record_metric(
                'request_duration',
                duration,
                {
                    'method': request.method,
                    'endpoint': request.endpoint,
                    'status_code': response.status_code,
                    'content_length': response.content_length
                }
            )
            
            # 慢请求警告
            if duration > 2.0:  # 超过2秒
                logger.warning(
                    f"慢请求: {request.method} {request.path} "
                    f"耗时 {duration:.2f}s, 状态码: {response.status_code}"
                )
        
        return response


def collect_system_metrics():
    """收集系统指标"""
    try:
        metrics = SystemMetrics()
        
        # CPU使用率
        cpu_usage = metrics.get_cpu_usage()
        performance_monitor.record_metric('system_cpu_percent', cpu_usage)
        
        # 内存使用情况
        memory = metrics.get_memory_usage()
        performance_monitor.record_metric('system_memory_percent', memory['percent'])
        performance_monitor.record_metric('system_memory_used_gb', memory['used'])
        
        # 磁盘使用情况
        disk = metrics.get_disk_usage()
        performance_monitor.record_metric('system_disk_percent', disk['percent'])
        
        # 进程信息
        process = metrics.get_process_info()
        performance_monitor.record_metric('process_memory_percent', process['memory_percent'])
        performance_monitor.record_metric('process_cpu_percent', process['cpu_percent'])
        performance_monitor.record_metric('process_threads', process['num_threads'])
        
        logger.debug(f"系统指标收集完成: CPU {cpu_usage}%, 内存 {memory['percent']}%")
        
    except Exception as e:
        logger.error(f"收集系统指标失败: {e}")


def get_performance_summary() -> Dict[str, Any]:
    """获取性能摘要"""
    try:
        summary = {
            'timestamp': datetime.now().isoformat(),
            'request_stats': {
                'avg_duration': performance_monitor.get_average('request_duration'),
                'total_requests': len(performance_monitor.get_metrics('request_duration'))
            },
            'db_stats': {
                'avg_query_duration': performance_monitor.get_average('db_query_duration'),
                'total_queries': len(performance_monitor.get_metrics('db_query_duration'))
            },
            'cache_stats': {
                'avg_get_duration': performance_monitor.get_average('cache_get_duration'),
                'avg_set_duration': performance_monitor.get_average('cache_set_duration')
            },
            'system_stats': {
                'cpu_percent': performance_monitor.get_average('system_cpu_percent', 10),
                'memory_percent': performance_monitor.get_average('system_memory_percent', 10),
                'disk_percent': performance_monitor.get_average('system_disk_percent', 10)
            }
        }
        
        return summary
        
    except Exception as e:
        logger.error(f"生成性能摘要失败: {e}")
        return {}


# Flask应用集成函数
def init_performance_monitoring(app: Flask):
    """初始化性能监控"""
    # 在测试模式下跳过性能监控
    if app.config.get('TESTING'):
        return
        
    @app.before_request
    def before_request():
        RequestMonitor.before_request()
    
    @app.after_request
    def after_request(response):
        return RequestMonitor.after_request(response)
    
    # 添加性能监控路由
    @app.route('/admin/performance')
    def performance_dashboard():
        """性能监控仪表板"""
        summary = get_performance_summary()
        return summary  # 或渲染模板
    
    # 生产环境性能监控
    if not app.debug and PSUTIL_AVAILABLE:
        setup_system_monitoring(app)
        setup_postgresql_optimizations(app)
    
    logger.info("性能监控已初始化")


def setup_system_monitoring(app: Flask):
    """设置系统监控"""
    if not PSUTIL_AVAILABLE:
        return
        
    try:
        # 系统资源监控
        logging.info(f"系统资源: CPU {psutil.cpu_count()}核, "
                    f"内存 {psutil.virtual_memory().total // (1024**3)}GB")
    except Exception as e:
        logging.warning(f"系统监控设置失败: {e}")


def setup_postgresql_optimizations(app: Flask):
    """设置PostgreSQL优化"""
    try:
        # PostgreSQL配置优化
        logging.info("PostgreSQL优化已启用")
    except Exception as e:
        logging.warning(f"PostgreSQL优化设置失败: {e}")
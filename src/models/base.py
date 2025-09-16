"""
PostgreSQL高性能基础模型
"""
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Index, text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from datetime import datetime
import uuid
import orjson


# 全局数据库实例
db = SQLAlchemy()


class BaseModel(db.Model):
    """精简的高性能基础模型"""
    __abstract__ = True
    
    # 使用UUID主键（PostgreSQL推荐）
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = db.Column(
        db.DateTime(timezone=True), 
        server_default=func.now(),
        nullable=False,
        index=True
    )
    updated_at = db.Column(
        db.DateTime(timezone=True), 
        server_default=func.now(), 
        onupdate=func.now(),
        nullable=False
    )
    
    def to_dict(self) -> dict:
        """高性能序列化"""
        result = {}
        for column in self.__table__.columns:
            value = getattr(self, column.name)
            if isinstance(value, datetime):
                result[column.name] = value.isoformat()
            elif isinstance(value, uuid.UUID):
                result[column.name] = str(value)
            else:
                result[column.name] = value
        return result
    
    def to_json(self) -> bytes:
        """使用orjson快速序列化"""
        return orjson.dumps(self.to_dict(), default=str)
    
    @classmethod
    def get_by_id(cls, id_value):
        """通过ID获取记录"""
        if isinstance(id_value, str):
            try:
                id_value = uuid.UUID(id_value)
            except ValueError:
                return None
        return cls.query.filter_by(id=id_value).first()
    
    def save(self):
        """保存记录"""
        db.session.add(self)
        db.session.commit()
        return self
    
    def delete(self):
        """删除记录"""
        db.session.delete(self)
        db.session.commit()


class TimestampMixin:
    """时间戳混入类"""
    created_at = db.Column(
        db.DateTime(timezone=True), 
        server_default=func.now(),
        nullable=False,
        index=True
    )
    updated_at = db.Column(
        db.DateTime(timezone=True), 
        server_default=func.now(), 
        onupdate=func.now(),
        nullable=False
    )
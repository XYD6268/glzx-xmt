"""
SQLite基础模型
"""
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import orjson


# 全局数据库实例
db = SQLAlchemy()


class BaseModel(db.Model):
    """基础模型"""
    __abstract__ = True
    
    # 使用整数主键（SQLite兼容）
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(
        db.DateTime, 
        default=datetime.utcnow,
        nullable=False,
        index=True
    )
    updated_at = db.Column(
        db.DateTime, 
        default=datetime.utcnow, 
        onupdate=datetime.utcnow,
        nullable=False
    )
    
    def to_dict(self) -> dict:
        """序列化"""
        result = {}
        for column in self.__table__.columns:
            value = getattr(self, column.name)
            if isinstance(value, datetime):
                result[column.name] = value.isoformat()
            else:
                result[column.name] = value
        return result
    
    def to_json(self) -> bytes:
        """使用orjson快速序列化"""
        return orjson.dumps(self.to_dict(), default=str)
    
    @classmethod
    def get_by_id(cls, id_value):
        """通过ID获取记录"""
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
        db.DateTime, 
        default=datetime.utcnow,
        nullable=False,
        index=True
    )
    updated_at = db.Column(
        db.DateTime, 
        default=datetime.utcnow, 
        onupdate=datetime.utcnow,
        nullable=False
    )
"""
用户模型 - SQLite简化版
"""
from sqlalchemy import Index
from werkzeug.security import generate_password_hash, check_password_hash
from .base import BaseModel, db


class User(BaseModel):
    """用户模型"""
    __tablename__ = 'users'
    
    # SQLite索引策略
    __table_args__ = (
        Index('idx_user_name_active', 'real_name'),
        Index('idx_user_role', 'role'),
        Index('idx_user_created', 'created_at'),
    )
    
    # 基础字段
    real_name = db.Column(db.String(50), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(128), nullable=False)
    school_id = db.Column(db.String(20), unique=True, nullable=True, index=True)
    qq_number = db.Column(db.String(15), nullable=False)
    class_name = db.Column(db.String(50), nullable=False, index=True)
    role = db.Column(db.SmallInteger, default=1, nullable=False, index=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    
    # 关系定义（使用字符串引用避免循环依赖）
    photos = db.relationship('Photo', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    votes = db.relationship('Vote', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    login_records = db.relationship('LoginRecord', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<User {self.real_name}>'
    
    def set_password(self, password: str):
        """设置密码哈希"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password: str) -> bool:
        """验证密码"""
        return check_password_hash(self.password_hash, password)
    
    def is_admin(self) -> bool:
        """是否为管理员"""
        return self.role >= 2
    
    def is_super_admin(self) -> bool:
        """是否为系统管理员"""
        return self.role >= 3
    
    @classmethod
    def get_by_name(cls, name: str):
        """通过姓名获取活跃用户"""
        return cls.query.filter_by(real_name=name, is_active=True).first()
    
    @classmethod
    def get_active_users(cls, limit: int = 50):
        """获取活跃用户列表"""
        return cls.query.filter_by(is_active=True).order_by(cls.created_at.desc()).limit(limit).all()
    
    @classmethod
    def search_users(cls, search_term: str, limit: int = 20):
        """用户搜索"""
        if not search_term or len(search_term.strip()) < 2:
            return []
        
        search_pattern = f"%{search_term.strip()}%"
        return cls.query.filter(
            db.or_(
                cls.real_name.ilike(search_pattern),
                cls.class_name.ilike(search_pattern),
                cls.qq_number.ilike(search_pattern)
            ),
            cls.is_active == True
        ).limit(limit).all()
    
    def get_photo_count(self) -> int:
        """获取用户照片数量"""
        return self.photos.count()
    
    def get_vote_count(self) -> int:
        """获取用户投票数量"""
        return self.votes.count()
    
    def to_dict(self) -> dict:
        """序列化，排除敏感信息"""
        result = super().to_dict()
        # 移除密码哈希
        result.pop('password_hash', None)
        return result


class LoginRecord(BaseModel):
    """登录记录模型"""
    __tablename__ = 'login_records'
    
    __table_args__ = (
        Index('idx_login_user_time', 'user_id', 'created_at'),
        Index('idx_login_ip_time', 'ip_address', 'created_at'),
    )
    
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    ip_address = db.Column(db.String(45), nullable=False, index=True)
    user_agent = db.Column(db.String(500), nullable=True)
    login_time = db.Column(db.DateTime, default=db.func.now())
    
    @classmethod
    def get_recent_logins(cls, user_id, hours: int = 24):
        """获取用户最近登录记录"""
        from datetime import datetime, timedelta
        time_threshold = datetime.utcnow() - timedelta(hours=hours)
        return cls.query.filter(
            cls.user_id == user_id,
            cls.created_at >= time_threshold
        ).order_by(cls.created_at.desc()).all()
    
    @classmethod
    def get_ip_login_count(cls, ip_address: str, hours: int = 24) -> int:
        """获取IP地址登录次数"""
        from datetime import datetime, timedelta
        time_threshold = datetime.utcnow() - timedelta(hours=hours)
        return cls.query.filter(
            cls.ip_address == ip_address,
            cls.created_at >= time_threshold
        ).count()


class IpBanRecord(BaseModel):
    """IP封禁记录"""
    __tablename__ = 'ip_ban_records'
    
    __table_args__ = (
        Index('idx_ip_ban_active', 'ip_address', 'is_active'),
    )
    
    ip_address = db.Column(db.String(45), nullable=False, unique=True, index=True)
    ban_reason = db.Column(db.String(200), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    banned_at = db.Column(db.DateTime, default=db.func.now())
    
    @classmethod
    def is_banned(cls, ip_address: str) -> bool:
        """检查IP是否被封禁"""
        record = cls.query.filter_by(ip_address=ip_address, is_active=True).first()
        return record is not None
    
    @classmethod
    def ban_ip(cls, ip_address: str, reason: str):
        """封禁IP地址"""
        existing = cls.query.filter_by(ip_address=ip_address).first()
        if existing:
            existing.is_active = True
            existing.ban_reason = reason
            existing.banned_at = db.func.now()
        else:
            ban_record = cls(ip_address=ip_address, ban_reason=reason)
            db.session.add(ban_record)
        db.session.commit()
    
    @classmethod
    def unban_ip(cls, ip_address: str):
        """解封IP地址"""
        record = cls.query.filter_by(ip_address=ip_address).first()
        if record:
            record.is_active = False
            db.session.commit()


class IpWhitelist(BaseModel):
    """IP白名单"""
    __tablename__ = 'ip_whitelist'
    
    ip_address = db.Column(db.String(45), nullable=False, unique=True, index=True)
    description = db.Column(db.String(200), nullable=True)
    created_by = db.Column(db.String(50), nullable=False)
    
    @classmethod
    def is_whitelisted(cls, ip_address: str) -> bool:
        """检查IP是否在白名单"""
        return cls.query.filter_by(ip_address=ip_address).first() is not None


class UserWhitelist(BaseModel):
    """用户白名单"""
    __tablename__ = 'user_whitelist'
    
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    description = db.Column(db.String(200), nullable=True)
    created_by = db.Column(db.String(50), nullable=False)
    
    # 关系定义
    user = db.relationship('User', backref='whitelist_record')
    
    @classmethod
    def is_whitelisted(cls, user_id) -> bool:
        """检查用户是否在白名单"""
        return cls.query.filter_by(user_id=user_id).first() is not None
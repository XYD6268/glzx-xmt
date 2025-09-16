"""
系统设置和协议模型 - SQLite简化版
"""
from .base import BaseModel, db


class Settings(BaseModel):
    """系统设置模型"""
    __tablename__ = 'settings'
    
    # 基础设置
    contest_title = db.Column(db.String(100), default="2025年摄影比赛")
    allow_upload = db.Column(db.Boolean, default=True, nullable=False)
    allow_vote = db.Column(db.Boolean, default=True, nullable=False)
    one_vote_per_user = db.Column(db.Boolean, default=False, nullable=False)
    
    # 时间设置
    vote_start_time = db.Column(db.DateTime, nullable=True)
    vote_end_time = db.Column(db.DateTime, nullable=True)
    
    # 显示设置
    show_rankings = db.Column(db.Boolean, default=True, nullable=False)
    icp_number = db.Column(db.String(100), nullable=True)
    
    # 风控设置
    risk_control_enabled = db.Column(db.Boolean, default=True, nullable=False)
    max_votes_per_ip = db.Column(db.Integer, default=10)
    vote_time_window = db.Column(db.Integer, default=60)  # 分钟
    max_accounts_per_ip = db.Column(db.Integer, default=5)
    account_time_window = db.Column(db.Integer, default=1440)  # 分钟
    
    # 水印设置
    watermark_enabled = db.Column(db.Boolean, default=True, nullable=False)
    watermark_text = db.Column(db.String(200), default="{contest_title}-{student_name}-{qq_number}")
    watermark_opacity = db.Column(db.Float, default=0.3)
    watermark_position = db.Column(db.String(20), default="bottom_right")
    watermark_font_size = db.Column(db.Integer, default=20)
    
    @classmethod
    def get_current(cls):
        """获取当前设置"""
        settings = cls.query.first()
        if not settings:
            # 创建默认设置
            settings = cls()
            db.session.add(settings)
            db.session.commit()
        return settings
    
    @classmethod
    def update_setting(cls, key: str, value):
        """更新单个设置"""
        settings = cls.get_current()
        if hasattr(settings, key):
            setattr(settings, key, value)
            db.session.commit()
            return True
        return False
    
    def is_voting_allowed(self) -> bool:
        """检查是否允许投票"""
        if not self.allow_vote:
            return False
        
        from datetime import datetime
        now = datetime.utcnow()
        
        if self.vote_start_time and now < self.vote_start_time:
            return False
        
        if self.vote_end_time and now > self.vote_end_time:
            return False
        
        return True
    
    def is_upload_allowed(self) -> bool:
        """检查是否允许上传"""
        return self.allow_upload
    
    def to_dict(self) -> dict:
        """序列化设置"""
        result = super().to_dict()
        result.update({
            'is_voting_allowed': self.is_voting_allowed(),
            'is_upload_allowed': self.is_upload_allowed()
        })
        return result


class Agreement(BaseModel):
    """协议模型"""
    __tablename__ = 'agreements'
    
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    agreement_type = db.Column(db.String(20), nullable=False, index=True)
    min_read_time = db.Column(db.Integer, default=10)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    
    # 关系定义
    agreement_records = db.relationship('UserAgreementRecord', backref='agreement', lazy='dynamic')
    
    @classmethod
    def get_by_type(cls, agreement_type: str):
        """根据类型获取活跃协议"""
        return cls.query.filter_by(
            agreement_type=agreement_type, 
            is_active=True
        ).first()
    
    @classmethod
    def get_active_agreements(cls):
        """获取所有活跃协议"""
        return cls.query.filter_by(is_active=True).order_by(cls.created_at.desc()).all()


class UserAgreementRecord(BaseModel):
    """用户协议记录"""
    __tablename__ = 'user_agreement_records'
    
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    agreement_id = db.Column(db.Integer, db.ForeignKey('agreements.id'), nullable=False)
    ip_address = db.Column(db.String(45), nullable=False, index=True)
    read_time = db.Column(db.Integer, nullable=False)  # 秒
    session_id = db.Column(db.String(100), nullable=True)
    agreed_at = db.Column(db.DateTime, default=db.func.now())
    
    @classmethod
    def has_agreed(cls, user_id, agreement_id) -> bool:
        """检查用户是否已同意协议"""
        return cls.query.filter_by(
            user_id=user_id, 
            agreement_id=agreement_id
        ).first() is not None
    
    @classmethod
    def record_agreement(cls, user_id, agreement_id, ip_address: str, read_time: int, session_id: str = None):
        """记录协议同意"""
        record = cls(
            user_id=user_id,
            agreement_id=agreement_id,
            ip_address=ip_address,
            read_time=read_time,
            session_id=session_id
        )
        db.session.add(record)
        db.session.commit()
        return record
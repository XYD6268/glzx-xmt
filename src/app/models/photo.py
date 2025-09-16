"""
照片模型 - SQLite简化版
"""
from sqlalchemy import Index
from .base import BaseModel, db


class Photo(BaseModel):
    """照片模型"""
    __tablename__ = 'photos'
    
    # SQLite索引策略
    __table_args__ = (
        # 核心查询索引
        Index('idx_photo_approved', 'vote_count', 'created_at'),
        # 用户照片索引
        Index('idx_photo_user', 'user_id', 'status'),
        # 状态索引
        Index('idx_photo_status', 'status', 'created_at'),
    )
    
    # 基础字段
    url = db.Column(db.String(256), nullable=False)
    thumb_url = db.Column(db.String(256), nullable=True)
    title = db.Column(db.String(100), nullable=True)
    class_name = db.Column(db.String(32), nullable=False, index=True)
    student_name = db.Column(db.String(32), nullable=False, index=True)
    vote_count = db.Column(db.Integer, default=0, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.SmallInteger, default=0, nullable=False, index=True)
    # 0=待审核, 1=已通过, 2=已拒绝, 3=已删除
    
    # 关系定义
    votes = db.relationship('Vote', backref='photo', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Photo {self.title or "Untitled"} by {self.student_name}>'
    
    @property
    def is_approved(self) -> bool:
        """是否已审核通过"""
        return self.status == 1
    
    @property  
    def is_pending(self) -> bool:
        """是否待审核"""
        return self.status == 0
    
    @property
    def is_rejected(self) -> bool:
        """是否已拒绝"""
        return self.status == 2
    
    def approve(self):
        """审核通过"""
        self.status = 1
    
    def reject(self):
        """审核拒绝"""
        self.status = 2
    
    def delete_photo(self):
        """软删除照片"""
        self.status = 3
    
    @classmethod
    def get_approved(cls, limit: int = 50, offset: int = 0):
        """获取已审核照片"""
        return cls.query.filter_by(status=1).order_by(
            cls.vote_count.desc(), 
            cls.created_at.desc()
        ).offset(offset).limit(limit).all()
    
    @classmethod
    def get_pending(cls, limit: int = 50):
        """获取待审核照片"""
        return cls.query.filter_by(status=0).order_by(
            cls.created_at.asc()
        ).limit(limit).all()
    
    @classmethod
    def get_by_user(cls, user_id, include_deleted: bool = False):
        """获取用户照片"""
        query = cls.query.filter_by(user_id=user_id)
        if not include_deleted:
            query = query.filter(cls.status != 3)
        return query.order_by(cls.created_at.desc()).all()
    
    @classmethod
    def get_top_voted(cls, limit: int = 10):
        """获取得票最多的照片"""
        return cls.query.filter_by(status=1).order_by(
            cls.vote_count.desc()
        ).limit(limit).all()
    
    @classmethod
    def get_recent(cls, days: int = 7, limit: int = 20):
        """获取最近上传的照片"""
        from datetime import datetime, timedelta
        time_threshold = datetime.utcnow() - timedelta(days=days)
        return cls.query.filter(
            cls.status == 1,
            cls.created_at >= time_threshold
        ).order_by(cls.created_at.desc()).limit(limit).all()
    
    @classmethod
    def get_statistics(cls):
        """获取照片统计信息"""
        from sqlalchemy import func
        stats = db.session.query(
            func.count(cls.id).label('total'),
            func.count(cls.id).filter(cls.status == 0).label('pending'),
            func.count(cls.id).filter(cls.status == 1).label('approved'),
            func.count(cls.id).filter(cls.status == 2).label('rejected'),
            func.sum(cls.vote_count).label('total_votes')
        ).first()
        
        return {
            'total': stats.total or 0,
            'pending': stats.pending or 0,
            'approved': stats.approved or 0,
            'rejected': stats.rejected or 0,
            'total_votes': stats.total_votes or 0
        }
    
    def increment_vote_count(self, count: int = 1):
        """增加投票数"""
        self.vote_count = (self.vote_count or 0) + count
    
    def decrement_vote_count(self, count: int = 1):
        """减少投票数"""
        self.vote_count = max((self.vote_count or 0) - count, 0)
    
    def to_dict(self) -> dict:
        """序列化"""
        result = super().to_dict()
        result.update({
            'is_approved': self.is_approved,
            'is_pending': self.is_pending,
            'is_rejected': self.is_rejected,
            'vote_count': self.vote_count or 0
        })
        return result


class Vote(BaseModel):
    """投票模型"""
    __tablename__ = 'votes'
    
    # SQLite索引策略
    __table_args__ = (
        # 确保用户对每张照片只能投一票
        db.UniqueConstraint('user_id', 'photo_id', name='uq_user_photo_vote'),
        # 照片投票索引
        Index('idx_vote_photo', 'photo_id', 'created_at'),
        # 用户投票索引
        Index('idx_vote_user', 'user_id', 'created_at'),
        # IP投票监控索引
        Index('idx_vote_ip_time', 'ip_address', 'created_at'),
    )
    
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    photo_id = db.Column(db.Integer, db.ForeignKey('photos.id'), nullable=False)
    ip_address = db.Column(db.String(45), nullable=True, index=True)
    
    def __repr__(self):
        return f'<Vote user:{self.user_id} photo:{self.photo_id}>'
    
    @classmethod
    def get_user_vote(cls, user_id, photo_id):
        """获取用户对照片的投票"""
        return cls.query.filter_by(user_id=user_id, photo_id=photo_id).first()
    
    @classmethod
    def has_voted(cls, user_id, photo_id) -> bool:
        """检查用户是否已投票"""
        return cls.query.filter_by(user_id=user_id, photo_id=photo_id).first() is not None
    
    @classmethod
    def get_photo_votes(cls, photo_id, limit: int = 50):
        """获取照片的投票记录"""
        return cls.query.filter_by(photo_id=photo_id).order_by(
            cls.created_at.desc()
        ).limit(limit).all()
    
    @classmethod
    def get_user_votes(cls, user_id, limit: int = 50):
        """获取用户的投票记录"""
        return cls.query.filter_by(user_id=user_id).order_by(
            cls.created_at.desc()
        ).limit(limit).all()
    
    @classmethod
    def get_ip_vote_count(cls, ip_address: str, hours: int = 24) -> int:
        """获取IP地址投票次数"""
        from datetime import datetime, timedelta
        time_threshold = datetime.utcnow() - timedelta(hours=hours)
        return cls.query.filter(
            cls.ip_address == ip_address,
            cls.created_at >= time_threshold
        ).count()
    
    @classmethod
    def delete_vote(cls, user_id, photo_id) -> bool:
        """删除投票"""
        vote = cls.query.filter_by(user_id=user_id, photo_id=photo_id).first()
        if vote:
            db.session.delete(vote)
            db.session.commit()
            return True
        return False
    
    @classmethod
    def get_vote_statistics(cls, photo_id=None):
        """获取投票统计"""
        from sqlalchemy import func
        query = db.session.query(
            func.count(cls.id).label('total_votes'),
            func.count(func.distinct(cls.user_id)).label('unique_voters'),
            func.count(func.distinct(cls.ip_address)).label('unique_ips')
        )
        
        if photo_id:
            query = query.filter(cls.photo_id == photo_id)
        
        stats = query.first()
        return {
            'total_votes': stats.total_votes or 0,
            'unique_voters': stats.unique_voters or 0,
            'unique_ips': stats.unique_ips or 0
        }
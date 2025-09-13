"""
高性能图片处理工具 - Pillow-SIMD优化版
"""
import os
import uuid
import logging
from typing import Tuple, Optional
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import tempfile

logger = logging.getLogger(__name__)


class ImageProcessor:
    """高性能图片处理器"""
    
    # 支持的图片格式
    SUPPORTED_FORMATS = {'JPEG', 'PNG', 'GIF', 'BMP', 'WEBP'}
    
    # 默认配置
    DEFAULT_THUMBNAIL_SIZE = (180, 120)
    DEFAULT_MAX_SIZE = (1920, 1080)
    DEFAULT_QUALITY = 85
    
    @staticmethod
    def validate_image(file_path: str) -> bool:
        """验证图片文件"""
        try:
            with Image.open(file_path) as img:
                return img.format in ImageProcessor.SUPPORTED_FORMATS
        except Exception as e:
            logger.warning(f"图片验证失败 {file_path}: {e}")
            return False
    
    @staticmethod
    def get_image_info(file_path: str) -> dict:
        """获取图片信息"""
        try:
            with Image.open(file_path) as img:
                return {
                    'format': img.format,
                    'mode': img.mode,
                    'size': img.size,
                    'width': img.width,
                    'height': img.height,
                    'file_size': os.path.getsize(file_path)
                }
        except Exception as e:
            logger.error(f"获取图片信息失败 {file_path}: {e}")
            return {}
    
    @staticmethod
    def create_thumbnail(input_path: str, output_dir: str = 'static/thumbs', 
                        size: Tuple[int, int] = None, quality: int = None) -> Optional[str]:
        """
        创建高质量缩略图
        
        Args:
            input_path: 输入图片路径
            output_dir: 输出目录
            size: 缩略图尺寸
            quality: 图片质量
            
        Returns:
            缩略图文件名或None
        """
        try:
            if size is None:
                size = ImageProcessor.DEFAULT_THUMBNAIL_SIZE
            if quality is None:
                quality = ImageProcessor.DEFAULT_QUALITY
            
            # 确保输出目录存在
            os.makedirs(output_dir, exist_ok=True)
            
            with Image.open(input_path) as img:
                # 转换为RGB模式
                if img.mode not in ('RGB', 'L'):
                    img = img.convert('RGB')
                
                # 使用高质量重采样算法
                img.thumbnail(size, Image.Resampling.LANCZOS)
                
                # 生成输出文件名
                filename = f"thumb_{uuid.uuid4().hex}.jpg"
                output_path = os.path.join(output_dir, filename)
                
                # 保存缩略图，启用优化
                img.save(output_path, 'JPEG', 
                        quality=quality, 
                        optimize=True,
                        progressive=True)
                
                logger.info(f"缩略图创建成功: {output_path}")
                return filename
                
        except Exception as e:
            logger.error(f"创建缩略图失败 {input_path}: {e}")
            return None
    
    @staticmethod
    def resize_image(input_path: str, output_path: str = None, 
                    max_size: Tuple[int, int] = None, quality: int = None) -> Optional[str]:
        """
        调整图片尺寸
        """
        try:
            if max_size is None:
                max_size = ImageProcessor.DEFAULT_MAX_SIZE
            if quality is None:
                quality = ImageProcessor.DEFAULT_QUALITY
            
            if output_path is None:
                output_path = input_path
            
            with Image.open(input_path) as img:
                # 检查是否需要调整尺寸
                if img.width <= max_size[0] and img.height <= max_size[1]:
                    return input_path
                
                # 计算新尺寸（保持宽高比）
                ratio = min(max_size[0] / img.width, max_size[1] / img.height)
                new_size = (int(img.width * ratio), int(img.height * ratio))
                
                # 调整尺寸
                resized = img.resize(new_size, Image.Resampling.LANCZOS)
                
                # 转换为RGB模式
                if resized.mode not in ('RGB', 'L'):
                    resized = resized.convert('RGB')
                
                # 保存
                resized.save(output_path, 'JPEG', 
                           quality=quality, 
                           optimize=True)
                
                logger.info(f"图片尺寸调整完成: {output_path}")
                return output_path
                
        except Exception as e:
            logger.error(f"调整图片尺寸失败 {input_path}: {e}")
            return None
    
    @staticmethod
    def optimize_image(input_path: str, output_path: str = None, quality: int = 85) -> bool:
        """优化图片文件大小"""
        try:
            if output_path is None:
                output_path = input_path
            
            with Image.open(input_path) as img:
                # 转换为RGB模式
                if img.mode not in ('RGB', 'L'):
                    img = img.convert('RGB')
                
                # 保存优化后的图片
                img.save(output_path, 'JPEG', 
                        quality=quality, 
                        optimize=True,
                        progressive=True)
                
                return True
                
        except Exception as e:
            logger.error(f"优化图片失败 {input_path}: {e}")
            return False


class WatermarkProcessor:
    """高性能水印处理器"""
    
    # 水印位置枚举
    POSITIONS = {
        'top_left': 'TL',
        'top_right': 'TR', 
        'bottom_left': 'BL',
        'bottom_right': 'BR',
        'center': 'C'
    }
    
    @staticmethod
    def add_watermark(input_path: str, watermark_text: str, 
                     output_dir: str = 'static/uploads',
                     position: str = 'bottom_right',
                     opacity: float = 0.3,
                     font_size: int = 20,
                     font_color: Tuple[int, int, int, int] = None) -> Optional[str]:
        """
        添加高质量水印
        
        Args:
            input_path: 输入图片路径
            watermark_text: 水印文本
            output_dir: 输出目录
            position: 水印位置
            opacity: 透明度 (0.0-1.0)
            font_size: 字体大小
            font_color: 字体颜色 (R, G, B, A)
            
        Returns:
            输出文件名或None
        """
        try:
            if font_color is None:
                font_color = (255, 255, 255, int(255 * opacity))
            
            # 确保输出目录存在
            os.makedirs(output_dir, exist_ok=True)
            
            with Image.open(input_path) as img:
                # 转换为RGBA模式支持透明度
                if img.mode != 'RGBA':
                    img = img.convert('RGBA')
                
                # 创建水印层
                watermark_layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
                draw = ImageDraw.Draw(watermark_layer)
                
                # 获取字体
                font = WatermarkProcessor._get_font(font_size)
                
                # 计算文本尺寸
                bbox = draw.textbbox((0, 0), watermark_text, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                
                # 计算水印位置
                x, y = WatermarkProcessor._calculate_position(
                    img.size, text_width, text_height, position
                )
                
                # 绘制文本阴影（增强可读性）
                shadow_color = (0, 0, 0, int(255 * opacity * 0.8))
                draw.text((x + 2, y + 2), watermark_text, font=font, fill=shadow_color)
                
                # 绘制主文本
                draw.text((x, y), watermark_text, font=font, fill=font_color)
                
                # 合并图层
                watermarked = Image.alpha_composite(img, watermark_layer)
                
                # 转换回RGB模式
                watermarked = watermarked.convert('RGB')
                
                # 生成输出文件名
                filename = f"watermarked_{uuid.uuid4().hex}.jpg"
                output_path = os.path.join(output_dir, filename)
                
                # 保存带水印的图片
                watermarked.save(output_path, 'JPEG', 
                               quality=90, 
                               optimize=True)
                
                logger.info(f"水印添加成功: {output_path}")
                return filename
                
        except Exception as e:
            logger.error(f"添加水印失败 {input_path}: {e}")
            return None
    
    @staticmethod
    def _get_font(font_size: int):
        """获取字体"""
        # 尝试系统字体路径
        font_paths = [
            # Windows
            'C:/Windows/Fonts/msyh.ttc',
            'C:/Windows/Fonts/simhei.ttf',
            'C:/Windows/Fonts/arial.ttf',
            # macOS
            '/System/Library/Fonts/STHeiti Light.ttc',
            '/System/Library/Fonts/Arial.ttf',
            # Linux
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
            '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
        ]
        
        # 尝试加载字体
        for font_path in font_paths:
            try:
                if os.path.exists(font_path):
                    return ImageFont.truetype(font_path, font_size)
            except Exception:
                continue
        
        # 使用默认字体
        try:
            return ImageFont.load_default()
        except Exception:
            return ImageFont.load_default()
    
    @staticmethod
    def _calculate_position(img_size: Tuple[int, int], text_width: int, 
                          text_height: int, position: str) -> Tuple[int, int]:
        """计算水印位置"""
        img_width, img_height = img_size
        margin = 20
        
        positions = {
            'top_left': (margin, margin),
            'top_right': (img_width - text_width - margin, margin),
            'bottom_left': (margin, img_height - text_height - margin),
            'bottom_right': (img_width - text_width - margin, img_height - text_height - margin),
            'center': ((img_width - text_width) // 2, (img_height - text_height) // 2)
        }
        
        return positions.get(position, positions['bottom_right'])


class ImageCache:
    """图片缓存管理器"""
    
    @staticmethod
    def get_cache_key(operation: str, input_path: str, **kwargs) -> str:
        """生成缓存键"""
        import hashlib
        
        # 获取文件修改时间
        try:
            mtime = str(os.path.getmtime(input_path))
        except:
            mtime = "0"
        
        # 创建缓存键
        key_data = f"{operation}:{input_path}:{mtime}:{str(sorted(kwargs.items()))}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    @staticmethod
    def cache_result(cache_key: str, result: str, cache_dir: str = 'cache/images'):
        """缓存处理结果"""
        try:
            os.makedirs(cache_dir, exist_ok=True)
            cache_file = os.path.join(cache_dir, f"{cache_key}.txt")
            
            with open(cache_file, 'w') as f:
                f.write(result)
                
        except Exception as e:
            logger.warning(f"缓存结果失败: {e}")
    
    @staticmethod
    def get_cached_result(cache_key: str, cache_dir: str = 'cache/images') -> Optional[str]:
        """获取缓存结果"""
        try:
            cache_file = os.path.join(cache_dir, f"{cache_key}.txt")
            
            if os.path.exists(cache_file):
                with open(cache_file, 'r') as f:
                    result = f.read().strip()
                    
                # 验证缓存文件是否存在
                if os.path.exists(result):
                    return result
                    
        except Exception as e:
            logger.warning(f"获取缓存失败: {e}")
        
        return None


# 便捷函数
def create_thumbnail(input_path: str, **kwargs) -> Optional[str]:
    """创建缩略图（带缓存）"""
    cache_key = ImageCache.get_cache_key('thumbnail', input_path, **kwargs)
    
    # 检查缓存
    cached = ImageCache.get_cached_result(cache_key)
    if cached:
        return os.path.basename(cached)
    
    # 处理图片
    result = ImageProcessor.create_thumbnail(input_path, **kwargs)
    
    # 缓存结果
    if result:
        full_path = os.path.join(kwargs.get('output_dir', 'static/thumbs'), result)
        ImageCache.cache_result(cache_key, full_path)
    
    return result


def add_watermark(input_path: str, watermark_text: str, **kwargs) -> Optional[str]:
    """添加水印（带缓存）"""
    cache_key = ImageCache.get_cache_key('watermark', input_path, text=watermark_text, **kwargs)
    
    # 检查缓存
    cached = ImageCache.get_cached_result(cache_key)
    if cached:
        return os.path.basename(cached)
    
    # 处理图片
    result = WatermarkProcessor.add_watermark(input_path, watermark_text, **kwargs)
    
    # 缓存结果
    if result:
        full_path = os.path.join(kwargs.get('output_dir', 'static/uploads'), result)
        ImageCache.cache_result(cache_key, full_path)
    
    return result


def optimize_image(input_path: str, **kwargs) -> bool:
    """优化图片"""
    return ImageProcessor.optimize_image(input_path, **kwargs)
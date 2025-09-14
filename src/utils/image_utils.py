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
    DEFAULT_THUMBNAIL_SIZE = (300, 200)
    DEFAULT_MAX_SIZE = (3840, 2160)
    DEFAULT_QUALITY = 100
    
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
    def create_thumbnail(input_path: str, size: Tuple[int, int] = (180, 120), 
                        output_dir: str = 'photo/thumbs', quality: int = 100) -> Optional[str]:
        """
        创建缩略图
        
        Args:
            input_path: 输入图片路径
            size: 缩略图尺寸 (宽, 高)，默认(180, 120)
            output_dir: 输出目录，默认为photo/thumbs
            quality: 图片保存质量，默认100 (最高质量)
            
        Returns:
            str: 缩略图文件名，失败时返回None
        """
        try:
            # 确保输出目录存在
            os.makedirs(output_dir, exist_ok=True)
            
            # 生成缩略图文件名
            filename = os.path.basename(input_path)
            name, ext = os.path.splitext(filename)
            thumb_filename = f"{name}_thumb{ext}"
            thumb_path = os.path.join(output_dir, thumb_filename)
            
            # 打开并处理图片
            with Image.open(input_path) as img:
                # 转换为RGB模式（如果需要）
                if img.mode in ('RGBA', 'LA', 'P'):
                    # 如果原图有透明通道，使用白色背景
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # 生成缩略图
                img.thumbnail(size, Image.Resampling.LANCZOS)
                
                # 保存缩略图
                img.save(thumb_path, 'JPEG', quality=quality, optimize=True)
            
            logger.info(f"缩略图创建成功: {thumb_path}")
            return thumb_filename
            
        except Exception as e:
            logger.error(f"创建缩略图失败: {e}")
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
    def optimize_image(input_path: str, output_path: str = None, quality: int = 100) -> bool:
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
    @staticmethod
    def add_watermark(input_path: str, watermark_text: str,
                     output_dir: str = 'photo/uploads',
                     position: str = 'bottom_right',
                     opacity: float = 0.3,
                     font_size: int = 20,
                     font_color: Tuple[int, int, int, int] = None) -> Optional[str]:
        """
        添加高质量水印
        """
        try:
            # 打开原始图片
            with Image.open(input_path) as img:
                # 确保图片是RGB模式
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # 创建水印图层
                watermark = Image.new('RGBA', img.size, (0, 0, 0, 0))
                draw = ImageDraw.Draw(watermark)
                
                # 使用默认字体或系统字体
                def _get_font(font_size: int):
                    """获取字体"""
                    # 只使用项目内置的鸿蒙字体以提高性能
                    font_path = 'static/fonts/HarmonyOS_Sans_SC_Regular.ttf'
                    
                    try:
                        if os.path.exists(font_path):
                            return ImageFont.truetype(font_path, font_size)
                    except Exception:
                        pass
                    
                    # 使用默认字体
                    try:
                        return ImageFont.load_default()
                    except Exception:
                        return ImageFont.load_default()
                
                font = _get_font(font_size)
                
                # 计算水印文本尺寸
                bbox = draw.textbbox((0, 0), watermark_text, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                
                # 创建水印文本
                text_layer = Image.new('RGBA', (text_width, text_height), (0, 0, 0, 0))
                text_draw = ImageDraw.Draw(text_layer)
                
                # 使用默认的白色字体颜色
                if font_color is None:
                    font_color = (255, 255, 255, int(255 * opacity))
                
                text_draw.text((0, 0), watermark_text, font=font, fill=font_color)
                
                # 旋转水印文本（可选）
                # text_layer = text_layer.rotate(30, expand=1)
                
                # 计算水印位置
                margin = 20
                if position == 'top_left':
                    x, y = margin, margin
                elif position == 'top_right':
                    x, y = img.width - text_width - margin, margin
                elif position == 'bottom_left':
                    x, y = margin, img.height - text_height - margin
                elif position == 'center':
                    x, y = (img.width - text_width) // 2, (img.height - text_height) // 2
                else:  # bottom_right
                    x, y = img.width - text_width - margin, img.height - text_height - margin
                
                # 将水印应用到图层上
                watermark.paste(text_layer, (x, y), text_layer)
                
                # 将水印合并到原图
                watermarked = Image.alpha_composite(img.convert('RGBA'), watermark)
                
                # 生成唯一的文件名
                filename = f"watermarked_{uuid.uuid4().hex}.jpg"
                watermarked_path = os.path.join(output_dir, filename)
                
                # 确保输出目录存在
                os.makedirs(output_dir, exist_ok=True)
                
                # 保存带水印的图片，使用最高质量
                watermarked.convert('RGB').save(watermarked_path, 'JPEG', quality=100, optimize=True)
                
                logger.info(f"水印添加成功: {watermarked_path}")
                
                return filename
                
        except Exception as e:
            logger.error(f"添加水印失败: {e}")
            return None


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
        full_path = os.path.join(kwargs.get('output_dir', 'photo/thumbs'), result)
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
        full_path = os.path.join(kwargs.get('output_dir', 'photo/uploads'), result)
        ImageCache.cache_result(cache_key, full_path)
    
    return result


def optimize_image(input_path: str, **kwargs) -> bool:
    """优化图片"""
    return ImageProcessor.optimize_image(input_path, **kwargs)
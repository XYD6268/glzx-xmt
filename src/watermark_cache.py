#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
水印功能优化版本 - 添加缓存机制
注意：这是一个可选的优化方案，可以在生产环境中使用
"""

import os
import hashlib
from PIL import Image, ImageDraw, ImageFont
import tempfile
from datetime import datetime

# 缓存配置
WATERMARK_CACHE_DIR = 'cache/watermarks'
CACHE_MAX_AGE = 3600  # 缓存1小时

def get_watermark_cache_key(photo_id, watermark_text, opacity, position, font_size):
    """生成缓存键"""
    key_string = f"{photo_id}_{watermark_text}_{opacity}_{position}_{font_size}"
    return hashlib.md5(key_string.encode()).hexdigest()

def get_cached_watermark(cache_key):
    """获取缓存的水印图片"""
    cache_path = os.path.join(WATERMARK_CACHE_DIR, f"{cache_key}.jpg")
    
    if os.path.exists(cache_path):
        # 检查缓存是否过期
        cache_time = os.path.getmtime(cache_path)
        current_time = datetime.now().timestamp()
        
        if current_time - cache_time < CACHE_MAX_AGE:
            return cache_path
        else:
            # 缓存过期，删除文件
            try:
                os.remove(cache_path)
            except:
                pass
    
    return None

def save_watermark_to_cache(image_path, cache_key):
    """保存水印图片到缓存"""
    try:
        os.makedirs(WATERMARK_CACHE_DIR, exist_ok=True)
        cache_path = os.path.join(WATERMARK_CACHE_DIR, f"{cache_key}.jpg")
        
        # 复制文件到缓存
        with open(image_path, 'rb') as src, open(cache_path, 'wb') as dst:
            dst.write(src.read())
        
        return cache_path
    except Exception as e:
        print(f"缓存保存失败: {e}")
        return image_path

def add_watermark_to_image_cached(image_path, photo_id, settings, photo, user):
    """带缓存的水印添加函数"""
    if not settings.watermark_enabled:
        return image_path
    
    # 格式化水印文本
    watermark_text = settings.watermark_text.format(
        contest_title=settings.contest_title,
        student_name=photo.student_name,
        qq_number=user.qq_number,
        class_name=photo.class_name,
        title=photo.title or '作品'
    )
    
    # 生成缓存键
    cache_key = get_watermark_cache_key(
        photo_id, watermark_text, 
        settings.watermark_opacity, 
        settings.watermark_position, 
        settings.watermark_font_size
    )
    
    # 检查缓存
    cached_path = get_cached_watermark(cache_key)
    if cached_path:
        return cached_path
    
    # 生成新的水印图片
    try:
        # 打开原始图片
        img = Image.open(image_path)
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        
        # 创建水印层
        watermark = Image.new('RGBA', img.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(watermark)
        
        # 尝试加载字体
        try:
            font = ImageFont.truetype("arial.ttf", settings.watermark_font_size)
        except:
            try:
                font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", settings.watermark_font_size)
            except:
                font = ImageFont.load_default()
        
        # 获取文本尺寸
        bbox = draw.textbbox((0, 0), watermark_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # 计算水印位置
        margin = 20
        if settings.watermark_position == "top_left":
            x, y = margin, margin
        elif settings.watermark_position == "top_right":
            x, y = img.width - text_width - margin, margin
        elif settings.watermark_position == "bottom_left":
            x, y = margin, img.height - text_height - margin
        elif settings.watermark_position == "center":
            x, y = (img.width - text_width) // 2, (img.height - text_height) // 2
        else:  # bottom_right (默认)
            x, y = img.width - text_width - margin, img.height - text_height - margin
        
        # 绘制水印文字
        alpha = int(255 * settings.watermark_opacity)
        draw.text((x, y), watermark_text, font=font, fill=(255, 255, 255, alpha))
        
        # 合并图片和水印
        watermarked = Image.alpha_composite(img, watermark)
        watermarked = watermarked.convert('RGB')
        
        # 生成临时文件
        temp_dir = tempfile.mkdtemp()
        temp_filename = f"watermarked_{photo_id}_{int(datetime.now().timestamp())}.jpg"
        temp_path = os.path.join(temp_dir, temp_filename)
        
        # 保存带水印的图片
        watermarked.save(temp_path, "JPEG", quality=85)
        
        # 保存到缓存
        cached_path = save_watermark_to_cache(temp_path, cache_key)
        
        # 如果缓存成功，返回缓存路径；否则返回临时路径
        if cached_path != temp_path:
            # 清理临时文件
            try:
                os.remove(temp_path)
                os.rmdir(temp_dir)
            except:
                pass
            return cached_path
        else:
            return temp_path
        
    except Exception as e:
        print(f"水印添加失败: {e}")
        return image_path

def clean_watermark_cache():
    """清理过期的缓存文件"""
    if not os.path.exists(WATERMARK_CACHE_DIR):
        return
    
    current_time = datetime.now().timestamp()
    cleaned_count = 0
    
    try:
        for filename in os.listdir(WATERMARK_CACHE_DIR):
            file_path = os.path.join(WATERMARK_CACHE_DIR, filename)
            if os.path.isfile(file_path):
                file_time = os.path.getmtime(file_path)
                if current_time - file_time > CACHE_MAX_AGE:
                    os.remove(file_path)
                    cleaned_count += 1
        
        print(f"清理了 {cleaned_count} 个过期缓存文件")
    except Exception as e:
        print(f"缓存清理失败: {e}")

# 示例：在应用启动时清理缓存
if __name__ == "__main__":
    print("清理水印缓存...")
    clean_watermark_cache()
    print("缓存清理完成")

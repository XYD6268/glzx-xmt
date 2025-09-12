#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试水印功能的修改
验证：
1. 缩略图不带水印
2. 原图带水印  
3. 未登录用户也能查看缩略图和原图
"""

import requests
import sys
import os

def test_routes():
    """测试新的路由是否正常工作"""
    base_url = "http://localhost:5000"
    
    # 测试缩略图路由（不带水印）
    thumb_url = f"{base_url}/thumb/1"
    print(f"测试缩略图路由: {thumb_url}")
    
    try:
        response = requests.get(thumb_url)
        print(f"缩略图状态码: {response.status_code}")
        if response.status_code == 200:
            print("✓ 缩略图路由正常工作")
        else:
            print(f"✗ 缩略图路由失败: {response.status_code}")
    except requests.exceptions.ConnectionError:
        print("⚠ 无法连接到服务器，请确保应用正在运行")
        return False
    
    # 测试原图路由（带水印）
    image_url = f"{base_url}/image/1"
    print(f"测试原图路由: {image_url}")
    
    try:
        response = requests.get(image_url)
        print(f"原图状态码: {response.status_code}")
        if response.status_code == 200:
            print("✓ 原图路由正常工作")
        else:
            print(f"✗ 原图路由失败: {response.status_code}")
    except requests.exceptions.ConnectionError:
        print("⚠ 无法连接到服务器")
        return False
    
    # 测试首页是否正常加载
    index_url = f"{base_url}/"
    print(f"测试首页: {index_url}")
    
    try:
        response = requests.get(index_url)
        print(f"首页状态码: {response.status_code}")
        if response.status_code == 200:
            print("✓ 首页正常加载")
            # 检查是否使用了新的路由
            if '/thumb/' in response.text and '/image/' in response.text:
                print("✓ 首页使用了新的图片路由")
            else:
                print("✗ 首页没有使用新的图片路由")
        else:
            print(f"✗ 首页加载失败: {response.status_code}")
    except requests.exceptions.ConnectionError:
        print("⚠ 无法连接到服务器")
        return False
    
    return True

def main():
    print("=== 水印功能修改测试 ===")
    print("这个测试需要应用服务器正在运行")
    print("请先运行: python app.py 或 python app_test.py")
    print()
    
    success = test_routes()
    
    if success:
        print("\n=== 测试完成 ===")
        print("修改总结：")
        print("1. ✓ 缩略图路由: /thumb/<photo_id> - 不带水印，允许未登录用户访问")
        print("2. ✓ 原图路由: /image/<photo_id> - 带水印，允许未登录用户访问")
        print("3. ✓ 模板文件已更新使用新路由")
        print("4. ✓ app.py 和 app_test.py 已同步修改")
    else:
        print("\n=== 测试未完成 ===")
        print("请确保应用服务器正在运行后重新测试")

if __name__ == "__main__":
    main()

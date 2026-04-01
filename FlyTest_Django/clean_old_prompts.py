#!/usr/bin/env python
"""
清理旧的5个分析提示词并重新初始化
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'flytest_django.settings')
django.setup()

from prompts.models import UserPrompt
from django.contrib.auth.models import User

def clean_and_reinit():
    print("=" * 80)
    print("清理旧提示词并重新初始化")
    print("=" * 80)
    
    # 需要清理的提示词名称
    analysis_prompt_names = [
        '完整性分析',
        '一致性分析',
        '可测性分析',
        '可行性分析',
        '清晰度分析'
    ]
    
    # 获取所有用户
    users = User.objects.all()
    total_deleted = 0
    
    for user in users:
        print(f"\n处理用户: {user.username}")
        
        for name in analysis_prompt_names:
            deleted_count = UserPrompt.objects.filter(
                user=user,
                name=name
            ).delete()[0]
            
            if deleted_count > 0:
                print(f"  ✅ 删除提示词: {name} ({deleted_count}个)")
                total_deleted += deleted_count
            else:
                print(f"  ⚠️  未找到提示词: {name}")
    
    print(f"\n{'='*80}")
    print(f"✅ 清理完成！共删除 {total_deleted} 个旧提示词")
    print(f"{'='*80}")
    print("\n📌 下一步操作:")
    print("请在前端点击\"初始化提示词\"按钮，创建新版本的提示词")

if __name__ == '__main__':
    try:
        clean_and_reinit()
    except Exception as e:
        print(f"\n❌ 清理失败: {e}")
        import traceback
        traceback.print_exc()

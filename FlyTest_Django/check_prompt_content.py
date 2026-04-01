#!/usr/bin/env python
"""检查提示词内容的诊断脚本"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'flytest_django.settings')
django.setup()

from prompts.models import UserPrompt
from django.contrib.auth.models import User

def check_prompts():
    print("=" * 80)
    print("提示词内容诊断")
    print("=" * 80)
    
    # 检查所有用户
    users = User.objects.all()
    print(f"\n📋 系统中共有 {users.count()} 个用户\n")
    
    for user in users:
        print(f"\n{'='*60}")
        print(f"👤 用户: {user.username}")
        print(f"{'='*60}")
        
        # 检查5个专项分析提示词
        analysis_types = [
            'completeness_analysis',
            'consistency_analysis',
            'testability_analysis',
            'feasibility_analysis',
            'clarity_analysis'
        ]
        
        for prompt_type in analysis_types:
            prompts = UserPrompt.objects.filter(user=user, prompt_type=prompt_type)
            count = prompts.count()
            
            print(f"\n🔍 {prompt_type}:")
            print(f"   数量: {count}")
            
            if count == 0:
                print("   ❌ 未找到此类型提示词")
            else:
                for prompt in prompts:
                    print(f"\n   📝 名称: {prompt.name}")
                    print(f"   🆔 ID: {prompt.id}")
                    print(f"   ✅ 激活: {prompt.is_active}")
                    print(f"   📅 更新时间: {prompt.updated_at}")
                    
                    # 检查内容中是否包含旧占位符
                    content = prompt.content
                    has_global_context = '{global_context}' in content
                    has_module_analyses = '{module_analyses}' in content
                    has_document = '{document}' in content
                    
                    print(f"   🔎 占位符检查:")
                    print(f"      - {{global_context}}: {'❌ 存在（旧版本）' if has_global_context else '✅ 不存在'}")
                    print(f"      - {{module_analyses}}: {'❌ 存在（旧版本）' if has_module_analyses else '✅ 不存在'}")
                    print(f"      - {{document}}: {'✅ 存在（新版本）' if has_document else '❌ 不存在'}")
                    
                    # 显示内容预览
                    print(f"\n   📄 内容预览（前300字符）:")
                    print(f"   {'-'*56}")
                    preview = content[:300].replace('\n', '\n   ')
                    print(f"   {preview}")
                    if len(content) > 300:
                        print(f"   ... (还有 {len(content) - 300} 字符)")
                    print(f"   {'-'*56}")

if __name__ == '__main__':
    try:
        check_prompts()
        print("\n\n✅ 诊断完成！")
    except Exception as e:
        print(f"\n\n❌ 诊断失败: {e}")
        import traceback
        traceback.print_exc()

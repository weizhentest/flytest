# 导入用户保存前后信号，用于在用户状态变化时执行自动化处理。
from django.db.models.signals import post_save, pre_save

# 导入信号装饰器。
from django.dispatch import receiver

# 导入内置用户与权限模型。
from django.contrib.auth.models import User, Permission

# 导入日志模块用于记录自动权限和提示词初始化结果。
import logging

# 初始化模块级日志记录器。
logger = logging.getLogger(__name__)


@receiver(pre_save, sender=User)
def track_staff_status_change(sender, instance, **kwargs):
    """
    在保存用户前，记录 is_staff 状态变化
    """
    # 仅当用户已存在时才读取旧值；新用户没有“变化”概念。
    if instance.pk:
        try:
            # 保存前缓存旧状态，供 post_save 阶段判断是否发生了管理员状态切换。
            old_instance = User.objects.get(pk=instance.pk)
            instance._old_is_staff = old_instance.is_staff
        except User.DoesNotExist:
            # 理论上极少触发（并发删除等场景），退化为“无旧状态”处理。
            instance._old_is_staff = None
    else:
        # 新建用户统一标记为无旧状态，避免误判为状态变化。
        instance._old_is_staff = None


@receiver(post_save, sender=User)
def auto_assign_admin_permissions(sender, instance, created, **kwargs):
    """
    用户保存后，根据 is_staff 状态自动分配或移除权限
    """
    old_is_staff = getattr(instance, '_old_is_staff', None)
    current_is_staff = instance.is_staff
    
    # 条件：新建管理员或 staff 状态发生变化；动作：同步直接权限；结果：权限状态与 is_staff 保持一致。
    staff_status_changed = old_is_staff is not None and old_is_staff != current_is_staff
    is_new_staff_user = created and current_is_staff
    
    if is_new_staff_user or staff_status_changed:
        if current_is_staff:
            # 条件：当前是管理员；动作：赋予全部直接权限；结果：管理员开箱即用可管理全局资源。
            all_permissions = Permission.objects.all()
            instance.user_permissions.set(all_permissions)
            logger.info(f"用户 {instance.username} 设置为管理员，已自动分配 {all_permissions.count()} 个权限")
        elif staff_status_changed and not current_is_staff:
            # 条件：从管理员降级；动作：清空直接权限；结果：保留组权限但移除管理员直授能力。
            instance.user_permissions.clear()
            logger.info(f"用户 {instance.username} 取消管理员，已移除所有直接权限（用户组权限保留）")
    
    # 清理临时缓存字段，避免污染后续业务逻辑。
    if hasattr(instance, '_old_is_staff'):
        delattr(instance, '_old_is_staff')


@receiver(post_save, sender=User)
def auto_initialize_user_prompts(sender, instance, created, **kwargs):
    """
    新用户创建后，自动初始化默认提示词
    """
    # 仅在新建用户时执行默认提示词初始化，避免每次保存都触发重建。
    if created:
        try:
            from prompts.services import initialize_user_prompts

            # 调用提示词初始化服务，确保新用户首次登录即可使用默认提示词集。
            result = initialize_user_prompts(instance)
            logger.info(
                f"新用户 {instance.username} 的提示词已自动初始化: "
                f"创建 {result['summary']['created_count']} 个, "
                f"跳过 {result['summary']['skipped_count']} 个"
            )
        except Exception as e:
            # 初始化失败不阻断用户创建流程，仅记录错误供后续补偿处理。
            logger.error(f"初始化用户 {instance.username} 的提示词失败: {e}")

"""
知识库信号处理器
确保数据库与 Qdrant 的数据一致性
"""
import os
import shutil
import logging
from django.db.models.signals import post_delete, pre_delete
from django.dispatch import receiver
from django.conf import settings

logger = logging.getLogger(__name__)


@receiver(pre_delete, sender='knowledge.KnowledgeBase')
def cleanup_knowledge_base(sender, instance, **kwargs):
    """
    知识库删除前清理所有相关数据
    确保 Qdrant Collection 与数据库记录同步删除
    """
    try:
        from .services import VectorStoreManager
        
        logger.info(f"🗑️  开始清理知识库: {instance.name} (ID: {instance.id})")
        
        # 1. 清理向量存储缓存（会同时删除 Qdrant 集合）
        VectorStoreManager.clear_cache(instance.id)
        logger.info("  ✅ 已清理向量存储缓存和 Qdrant 集合")
        
        # 2. 删除知识库文件目录
        kb_directory = os.path.join(
            settings.MEDIA_ROOT,
            'knowledge_bases',
            str(instance.id)
        )
        
        if os.path.exists(kb_directory):
            shutil.rmtree(kb_directory)
            logger.info(f"  ✅ 已删除文件目录: {kb_directory}")
        else:
            logger.info(f"  ⚠️  目录不存在,跳过: {kb_directory}")
        
        logger.info(f"🎉 知识库 '{instance.name}' 清理完成")
        
    except Exception as e:
        logger.error(f"❌ 清理知识库失败: {e}", exc_info=True)


@receiver(post_delete, sender='knowledge.Document')
def cleanup_document_cache(sender, instance, **kwargs):
    """
    文档删除后清理相关缓存
    DocumentChunk 会通过 CASCADE 自动删除,但缓存需要手动清理
    """
    try:
        from .services import VectorStoreManager
        
        # 清理知识库的向量存储缓存
        # 因为 Collection 中的文档数量已经变化
        VectorStoreManager.clear_cache(instance.knowledge_base.id)
        logger.info(f"✅ 已清理文档 '{instance.title}' 相关的向量缓存")
        
    except Exception as e:
        logger.error(f"❌ 清理文档缓存失败: {e}", exc_info=True)
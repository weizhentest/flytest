"""
Django管理命令：检查知识库系统状态
"""
import os
import time
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from knowledge.models import KnowledgeBase, Document
from knowledge.services import VectorStoreManager


class Command(BaseCommand):
    help = '检查知识库系统状态和配置'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fix',
            action='store_true',
            help='尝试自动修复发现的问题',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='显示详细信息',
        )

    def handle(self, *args, **options):
        self.verbose = options['verbose']
        self.fix_issues = options['fix']
        
        self.stdout.write(
            self.style.SUCCESS('🤖 知识库系统状态检查')
        )
        self.stdout.write('=' * 50)
        
        issues = []
        
        # 检查环境变量
        issues.extend(self.check_environment())
        
        # 检查依赖库
        issues.extend(self.check_dependencies())
        
        # 检查BGE-M3模型
        issues.extend(self.check_embedding_model())
        
        # 检查数据库状态
        issues.extend(self.check_database())
        
        # 检查向量存储
        issues.extend(self.check_vector_stores())
        
        # 总结
        self.stdout.write('\n' + '=' * 50)
        if issues:
            self.stdout.write(
                self.style.WARNING(f'⚠️  发现 {len(issues)} 个问题:')
            )
            for i, issue in enumerate(issues, 1):
                self.stdout.write(f'  {i}. {issue}')
                
            if self.fix_issues:
                self.stdout.write('\n🔧 尝试自动修复...')
                self.attempt_fixes()
        else:
            self.stdout.write(
                self.style.SUCCESS('✅ 知识库系统状态良好！')
            )

    def check_environment(self):
        """检查环境变量配置"""
        self.stdout.write('\n🔍 检查环境变量...')
        issues = []
        
        # 检查HuggingFace缓存目录配置
        cache_dir = Path('.cache/huggingface')
        
        if not cache_dir.exists():
            issues.append('HuggingFace缓存目录不存在')
            if self.fix_issues:
                cache_dir.mkdir(parents=True, exist_ok=True)
                self.stdout.write('  ✅ 已创建缓存目录')
        
        # 检查环境变量
        env_vars = {
            'HF_HOME': str(cache_dir),
            'HF_HUB_CACHE': str(cache_dir),
            'SENTENCE_TRANSFORMERS_HOME': str(cache_dir),
        }
        
        for var, expected in env_vars.items():
            current = os.environ.get(var)
            if current != expected:
                if self.verbose:
                    self.stdout.write(f'  ⚠️  {var}: {current} -> {expected}')
                os.environ[var] = expected
        
        self.stdout.write('  ✅ 环境变量配置完成')
        return issues

    def check_dependencies(self):
        """检查依赖库"""
        self.stdout.write('\n📦 检查依赖库...')
        issues = []
        
        required_packages = {
            'langchain_qdrant': 'LangChain Qdrant集成',
            'qdrant_client': 'Qdrant客户端',
            'fastembed': 'FastEmbed (BM25稀疏向量)',
        }
        
        optional_packages = {
            'langchain_huggingface': 'LangChain HuggingFace集成 (可选)',
            'sentence_transformers': 'SentenceTransformers库 (可选)',
            'torch': 'PyTorch深度学习框架 (可选)',
        }
        
        for package, description in required_packages.items():
            try:
                __import__(package)
                self.stdout.write(f'  ✅ {description}')
            except ImportError:
                issue = f'缺少依赖库: {package} ({description})'
                issues.append(issue)
                self.stdout.write(f'  ❌ {issue}')
        
        return issues

    def check_embedding_model(self):
        """检查BGE-M3嵌入模型"""
        self.stdout.write('\n🤖 检查BGE-M3嵌入模型...')
        issues = []
        
        cache_dir = Path('.cache/huggingface')
        model_name = "BAAI/bge-m3"
        model_cache_name = model_name.replace('/', '--')
        model_path = cache_dir / f'models--{model_cache_name}'
        
        if not model_path.exists():
            issue = 'BGE-M3模型未下载'
            issues.append(issue)
            self.stdout.write(f'  ❌ {issue}')
            self.stdout.write(f'     💡 请运行: python download_embedding_models.py --download bge-m3')
        else:
            self.stdout.write(f'  ✅ 模型文件存在: {model_path}')
            
            # 计算模型大小
            total_size = sum(f.stat().st_size for f in model_path.rglob('*') if f.is_file())
            size_gb = total_size / (1024**3)
            self.stdout.write(f'     💾 模型大小: {size_gb:.1f}GB')
            
            # 测试模型加载
            try:
                from langchain_huggingface import HuggingFaceEmbeddings
                
                self.stdout.write('  🧪 测试模型加载...')
                start_time = time.time()
                
                embeddings = HuggingFaceEmbeddings(
                    model_name=model_name,
                    cache_folder=str(cache_dir),
                    model_kwargs={'device': 'cpu'},
                    encode_kwargs={'normalize_embeddings': True}
                )
                
                # 测试嵌入
                test_vector = embeddings.embed_query("测试文本")
                load_time = time.time() - start_time
                
                self.stdout.write(f'  ✅ 模型加载成功 (耗时: {load_time:.2f}s)')
                self.stdout.write(f'     📊 嵌入维度: {len(test_vector)}')
                
            except Exception as e:
                issue = f'BGE-M3模型加载失败: {str(e)}'
                issues.append(issue)
                self.stdout.write(f'  ❌ {issue}')
        
        return issues

    def check_database(self):
        """检查数据库状态"""
        self.stdout.write('\n💾 检查数据库状态...')
        issues = []
        
        try:
            # 检查知识库数量
            kb_count = KnowledgeBase.objects.count()
            active_kb_count = KnowledgeBase.objects.filter(is_active=True).count()
            doc_count = Document.objects.count()
            completed_doc_count = Document.objects.filter(status='completed').count()
            
            self.stdout.write(f'  📚 知识库总数: {kb_count} (活跃: {active_kb_count})')
            self.stdout.write(f'  📄 文档总数: {doc_count} (已处理: {completed_doc_count})')
            
            # 检查失败的文档
            failed_docs = Document.objects.filter(status='failed').count()
            if failed_docs > 0:
                issue = f'有 {failed_docs} 个文档处理失败'
                issues.append(issue)
                self.stdout.write(f'  ⚠️  {issue}')
            
        except Exception as e:
            issue = f'数据库查询失败: {str(e)}'
            issues.append(issue)
            self.stdout.write(f'  ❌ {issue}')
        
        return issues

    def check_vector_stores(self):
        """检查向量存储状态和数据一致性"""
        self.stdout.write('\n🗄️  检查向量存储...')
        issues = []
        self._inconsistent_kbs = []  # 保存不一致的知识库，供修复使用
        
        try:
            # 检查向量存储缓存
            cache_count = len(VectorStoreManager._vector_store_cache)
            self.stdout.write(f'  💾 向量存储缓存: {cache_count} 个实例')
            
            # 检查知识库目录
            kb_dir = Path(settings.MEDIA_ROOT) / 'knowledge_bases'
            if kb_dir.exists():
                kb_dirs = [d for d in kb_dir.iterdir() if d.is_dir()]
                self.stdout.write(f'  📁 知识库目录数量: {len(kb_dirs)}')
            
            # 检查 Qdrant 连接和数据一致性
            try:
                from qdrant_client import QdrantClient
                qdrant_url = os.environ.get('QDRANT_URL', 'http://localhost:8918')
                client = QdrantClient(url=qdrant_url)
                collections = client.get_collections().collections
                collection_names = {col.name for col in collections}
                self.stdout.write(f'  🗄️  Qdrant 集合数量: {len(collections)}')
                
                # 检查每个知识库的数据一致性
                self.stdout.write('\n  📊 数据一致性检查:')
                for kb in KnowledgeBase.objects.all():
                    collection_name = f'kb_{kb.id}'
                    doc_count = kb.documents.filter(status='completed').count()
                    
                    if collection_name in collection_names:
                        info = client.get_collection(collection_name)
                        points_count = info.points_count
                        if doc_count > 0 and points_count == 0:
                            issue = f'知识库 "{kb.name}" 有 {doc_count} 个文档但 Qdrant 向量为空'
                            issues.append(issue)
                            self._inconsistent_kbs.append(kb)
                            self.stdout.write(f'     ⚠️  {kb.name}: {doc_count} 文档, {points_count} 向量 (需要重新索引)')
                        else:
                            self.stdout.write(f'     ✅ {kb.name}: {doc_count} 文档, {points_count} 向量')
                    else:
                        if doc_count > 0:
                            issue = f'知识库 "{kb.name}" 有 {doc_count} 个文档但 Qdrant Collection 不存在'
                            issues.append(issue)
                            self._inconsistent_kbs.append(kb)
                            self.stdout.write(f'     ❌ {kb.name}: {doc_count} 文档, Collection 不存在 (需要重新索引)')
                        else:
                            self.stdout.write(f'     ℹ️  {kb.name}: 空知识库 (无需 Collection)')
                            
            except Exception as e:
                issue = f'Qdrant 连接失败: {e}'
                issues.append(issue)
                self.stdout.write(f'  ❌ {issue}')
                
        except Exception as e:
            issue = f'向量存储检查失败: {str(e)}'
            issues.append(issue)
            self.stdout.write(f'  ❌ {issue}')
        
        return issues

    def attempt_fixes(self):
        """尝试自动修复问题"""
        if not hasattr(self, '_inconsistent_kbs') or not self._inconsistent_kbs:
            self.stdout.write('  ℹ️  没有需要修复的知识库一致性问题')
            return
            
        self.stdout.write(f'\n🔧 发现 {len(self._inconsistent_kbs)} 个知识库需要重新索引')
        self.stdout.write('💡 建议操作:')
        for kb in self._inconsistent_kbs:
            self.stdout.write(f'   - 知识库 "{kb.name}" (ID: {kb.id}): 删除后重新上传文档')
        
        self.stdout.write('\n📌 你也可以通过以下方式修复:')
        self.stdout.write('   1. 在前端管理界面删除并重建知识库')
        self.stdout.write('   2. 或者调用 API 重新处理文档')

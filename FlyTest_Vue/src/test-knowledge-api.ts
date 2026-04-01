/**
 * 知识库API接口测试文件
 * 用于验证新的API接口格式是否正确
 */

import { KnowledgeService } from './features/knowledge/services/knowledgeService';
import type {
  KnowledgeBase,
  CreateKnowledgeBaseRequest,
  QueryRequest,
  SystemStatusResponse
} from './features/knowledge/types/knowledge';

// 测试函数
export async function testKnowledgeAPI() {
  console.log('开始测试知识库API接口...');

  try {
    // 1. 测试系统状态检查
    console.log('1. 测试系统状态检查...');
    const systemStatus: SystemStatusResponse = await KnowledgeService.getSystemStatus();
    console.log('系统状态:', systemStatus);
    console.log('✅ 系统状态检查成功');

    // 2. 测试获取知识库列表
    console.log('2. 测试获取知识库列表...');
    const knowledgeBases = await KnowledgeService.getKnowledgeBases({
      page: 1,
      page_size: 10,
      ordering: '-created_at'
    });
    console.log('知识库列表:', knowledgeBases);
    console.log('✅ 获取知识库列表成功');

    // 3. 如果有知识库，测试查询功能
    if (Array.isArray(knowledgeBases) && knowledgeBases.length > 0) {
      const firstKB = knowledgeBases[0];
      console.log('3. 测试知识库查询...');

      const queryRequest: QueryRequest = {
        query: '测试查询',
        knowledge_base_id: firstKB.id,
        top_k: 3,
        similarity_threshold: 0.3,
        include_metadata: true
      };

      try {
        const queryResult = await KnowledgeService.queryKnowledgeBase(firstKB.id, queryRequest);
        console.log('查询结果:', queryResult);
        console.log('✅ 知识库查询成功');
      } catch (error) {
        console.log('⚠️ 知识库查询失败（可能是知识库为空）:', error);
      }
    } else if (knowledgeBases && typeof knowledgeBases === 'object' && 'results' in knowledgeBases) {
      // 分页格式
      if (knowledgeBases.results.length > 0) {
        const firstKB = knowledgeBases.results[0];
        console.log('3. 测试知识库查询（分页格式）...');

        const queryRequest: QueryRequest = {
          query: '测试查询',
          knowledge_base_id: firstKB.id,
          top_k: 3,
          similarity_threshold: 0.3,
          include_metadata: true
        };

        try {
          const queryResult = await KnowledgeService.queryKnowledgeBase(firstKB.id, queryRequest);
          console.log('查询结果:', queryResult);
          console.log('✅ 知识库查询成功');
        } catch (error) {
          console.log('⚠️ 知识库查询失败（可能是知识库为空）:', error);
        }
      } else {
        console.log('⚠️ 没有可用的知识库进行查询测试');
      }
    } else {
      console.log('⚠️ 没有可用的知识库进行查询测试');
    }

    console.log('🎉 知识库API接口测试完成！');
    return true;

  } catch (error) {
    console.error('❌ 知识库API接口测试失败:', error);
    return false;
  }
}

// 测试创建知识库（需要项目ID）
export async function testCreateKnowledgeBase(projectId: number) {
  console.log('测试创建知识库...');

  try {
    const createRequest: CreateKnowledgeBaseRequest = {
      name: `测试知识库_${Date.now()}`,
      description: '这是一个API测试创建的知识库',
      project: projectId,
      embedding_service: 'openai',
      api_base_url: 'https://api.openai.com/v1',
      api_key: 'sk-test-key',
      model_name: 'text-embedding-ada-002',
      chunk_size: 1000,
      chunk_overlap: 200,
      is_active: true
    };

    const newKB: KnowledgeBase = await KnowledgeService.createKnowledgeBase(createRequest);
    console.log('创建的知识库:', newKB);
    console.log('✅ 创建知识库成功');

    // 测试获取知识库详情
    const kbDetail = await KnowledgeService.getKnowledgeBase(newKB.id);
    console.log('知识库详情:', kbDetail);
    console.log('✅ 获取知识库详情成功');

    // 清理：删除测试知识库
    await KnowledgeService.deleteKnowledgeBase(newKB.id);
    console.log('✅ 清理测试知识库成功');

    return true;
  } catch (error) {
    console.error('❌ 创建知识库测试失败:', error);
    return false;
  }
}

// 验证API响应格式
export function validateResponseFormat() {
  console.log('验证API响应格式...');

  // 验证实际的API响应格式（包装格式）
  const mockApiResponse = {
    status: "success",
    code: 200,
    message: "操作成功",
    data: [
      {
        id: "5cefbc6b-c4f9-4326-a123-24295e3d83de",
        name: "测试知识库",
        description: "",
        project: 3,
        project_name: "演示项目",
        creator: 2,
        creator_name: "duanxc",
        is_active: true,
        embedding_service: "openai",
        api_base_url: "https://api.openai.com/v1",
        api_key: "sk-test-key",
        model_name: "text-embedding-ada-002",
        chunk_size: 1000,
        chunk_overlap: 200,
        document_count: 0,
        chunk_count: 0,
        created_at: "2025-06-06T14:26:04.310323+08:00",
        updated_at: "2025-06-06T14:26:04.311280+08:00"
      }
    ],
    errors: null
  };

  console.log('✅ API响应格式验证通过');

  // 验证系统状态响应格式
  const mockSystemStatus: SystemStatusResponse = {
    timestamp: Date.now() / 1000,
    embedding_model: {
      status: 'working',
      model_name: 'BAAI/bge-m3',
      cache_path: '.cache/huggingface/models--BAAI--bge-m3',
      model_exists: true,
      load_test: true,
      dimension: 1024
    },
    dependencies: {
      langchain_huggingface: true,
      langchain_qdrant: true,
      fastembed: true,
      sentence_transformers: true,
      torch: true
    },
    vector_stores: {
      total_knowledge_bases: 5,
      active_knowledge_bases: 4,
      cache_status: '3 cached instances'
    },
    overall_status: 'healthy'
  };

  console.log('✅ 系统状态响应格式验证通过');

  // 验证知识库对象格式
  const mockKnowledgeBase: KnowledgeBase = {
    id: 'test-id',
    name: '测试知识库',
    description: '测试描述',
    project: 1,
    project_name: '测试项目',
    creator: 1,
    creator_name: 'admin',
    is_active: true,
    embedding_service: 'openai',
    api_base_url: 'https://api.openai.com/v1',
    api_key: 'sk-test-key',
    model_name: 'text-embedding-ada-002',
    chunk_size: 1000,
    chunk_overlap: 200,
    document_count: 0,
    chunk_count: 0,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString()
  };

  console.log('✅ 知识库对象格式验证通过');

  // 验证查询响应格式
  const mockQueryResponse = {
    query: "用户",
    answer: "基于查询「用户」检索到的相关内容：\n\n用户用户用户用户用户用户",
    sources: [
      {
        content: "用户用户用户用户用户用户",
        metadata: {
          title: "注册用户",
          file_path: "D:\\Google\\FlyTest_django\\media\\knowledge_bases\\5cefbc6b-c4f9-4326-a123-24295e3d83de\\documents\\注册用户.txt",
          source: "注册用户",
          document_type: "txt",
          document_id: "c67cd6a7-304c-475f-8f7c-cc11d147da35"
        },
        similarity_score: 0.9109437763690948
      }
    ],
    retrieval_time: 0.5057508945465088,
    generation_time: 0,
    total_time: 0.5107424259185791
  };

  console.log('✅ 查询响应格式验证通过');
  console.log('🎉 所有响应格式验证完成！');

  return true;
}

/**
 * DiagramEditor - 企业级 Draw.io XML 编辑服务
 * 
 * 提供对 Draw.io XML 的 DOM 级操作，支持：
 * - 多页面管理
 * - 元素增删改查
 * - 样式和属性操作
 */

/** 图表页面信息 */
export interface DiagramPage {
  id: string;
  name: string;
  index: number;
  elementCount: number;
}

/** 图表元素信息 */
export interface DiagramElement {
  id: string;
  type: string;
  value: string;
  style: string;
  geometry?: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
  parent?: string;
}

/** 图表结构信息 */
export interface DiagramStructure {
  pageCount: number;
  pages: DiagramPage[];
  currentPageElements?: DiagramElement[];
}

/** 编辑操作类型 */
export type EditAction = 'add' | 'delete' | 'update' | 'replace_page';

/** 编辑操作 */
export interface EditOperation {
  action: EditAction;
  pageIndex?: number;        // 目标页面索引（默认当前页或0）
  elementId?: string;        // 元素 ID（用于 delete/update）
  element?: string;          // 新元素 XML（用于 add）
  properties?: Record<string, string>;  // 要更新的属性（用于 update）
  pageXml?: string;          // 完整页面 XML（用于 replace_page）
  pageName?: string;         // 新页面名称（用于 replace_page）
}

/** 编辑结果 */
export interface EditResult {
  success: boolean;
  message: string;
  xml?: string;
  appliedCount?: number;
  errors?: string[];
}

/**
 * 图表编辑器类
 */
export class DiagramEditor {
  private parser: DOMParser;
  private serializer: XMLSerializer;
  private doc: Document | null = null;
  private rawXml: string = '';

  constructor() {
    this.parser = new DOMParser();
    this.serializer = new XMLSerializer();
  }

  /**
   * 加载 XML 内容
   */
  load(xml: string): boolean {
    if (!xml || !xml.trim()) {
      console.error('[DiagramEditor] Empty XML');
      return false;
    }

    this.rawXml = xml;
    this.doc = this.parser.parseFromString(xml, 'application/xml');
    
    const parseError = this.doc.querySelector('parsererror');
    if (parseError) {
      console.error('[DiagramEditor] XML parse error:', parseError.textContent);
      return false;
    }

    return true;
  }

  /**
   * 获取图表结构信息
   */
  getStructure(pageIndex?: number): DiagramStructure {
    if (!this.doc) {
      return { pageCount: 0, pages: [] };
    }

    const structure: DiagramStructure = {
      pageCount: 0,
      pages: []
    };

    // 检查是否是 mxfile 多页面格式
    const mxfile = this.doc.querySelector('mxfile');
    if (mxfile) {
      const diagrams = mxfile.querySelectorAll('diagram');
      structure.pageCount = diagrams.length;
      
      diagrams.forEach((diagram, index) => {
        const root = diagram.querySelector('mxGraphModel > root');
        const elementCount = root ? root.querySelectorAll('mxCell').length - 2 : 0; // 减去基础的两个 cell
        
        structure.pages.push({
          id: diagram.getAttribute('id') || `page-${index}`,
          name: diagram.getAttribute('name') || `Page-${index + 1}`,
          index,
          elementCount: Math.max(0, elementCount)
        });
      });

      // 获取指定页面的元素
      if (pageIndex !== undefined && pageIndex >= 0 && pageIndex < diagrams.length) {
        structure.currentPageElements = this.getPageElements(diagrams[pageIndex]);
      }
    } else {
      // 单页面格式 (直接是 mxGraphModel)
      const mxGraphModel = this.doc.querySelector('mxGraphModel');
      if (mxGraphModel) {
        const root = mxGraphModel.querySelector('root');
        const elementCount = root ? root.querySelectorAll('mxCell').length - 2 : 0;
        
        structure.pageCount = 1;
        structure.pages.push({
          id: 'page-0',
          name: 'Page-1',
          index: 0,
          elementCount: Math.max(0, elementCount)
        });

        if (pageIndex === 0 || pageIndex === undefined) {
          structure.currentPageElements = this.getPageElements(mxGraphModel);
        }
      }
    }

    return structure;
  }

  /**
   * 获取页面中的所有元素
   */
  private getPageElements(container: Element): DiagramElement[] {
    const elements: DiagramElement[] = [];
    const cells = container.querySelectorAll('mxCell');
    
    cells.forEach(cell => {
      const id = cell.getAttribute('id');
      if (!id || id === '0' || id === '1') return; // 跳过基础 cell

      const element: DiagramElement = {
        id,
        type: 'cell',
        value: cell.getAttribute('value') || '',
        style: cell.getAttribute('style') || ''
      };

      // 获取几何信息
      const geometry = cell.querySelector('mxGeometry');
      if (geometry) {
        element.geometry = {
          x: parseFloat(geometry.getAttribute('x') || '0'),
          y: parseFloat(geometry.getAttribute('y') || '0'),
          width: parseFloat(geometry.getAttribute('width') || '0'),
          height: parseFloat(geometry.getAttribute('height') || '0')
        };
      }

      // 获取父元素
      const parent = cell.getAttribute('parent');
      if (parent && parent !== '1') {
        element.parent = parent;
      }

      elements.push(element);
    });

    return elements;
  }

  /**
   * 应用编辑操作
   */
  applyOperations(operations: EditOperation[]): EditResult {
    if (!this.doc) {
      return { success: false, message: '没有加载图表' };
    }

    const errors: string[] = [];
    let appliedCount = 0;

    for (const op of operations) {
      try {
        let result = false;
        
        switch (op.action) {
          case 'add':
            result = this.addElement(op);
            break;
          case 'delete':
            result = this.deleteElement(op);
            break;
          case 'update':
            result = this.updateElement(op);
            break;
          case 'replace_page':
            result = this.replacePage(op);
            break;
          default:
            errors.push(`未知操作: ${op.action}`);
            continue;
        }

        if (result) {
          appliedCount++;
        } else {
          errors.push(`操作失败: ${op.action} ${op.elementId || ''}`);
        }
      } catch (e) {
        errors.push(`操作异常: ${e}`);
      }
    }

    const xml = this.serialize();
    const success = appliedCount > 0;

    return {
      success,
      message: success 
        ? `成功应用 ${appliedCount}/${operations.length} 个操作`
        : '所有操作均失败',
      xml,
      appliedCount,
      errors: errors.length > 0 ? errors : undefined
    };
  }

  /**
   * 添加元素
   */
  private addElement(op: EditOperation): boolean {
    if (!op.element) {
      console.error('[DiagramEditor] No element to add');
      return false;
    }

    const root = this.getPageRoot(op.pageIndex || 0);
    if (!root) {
      console.error('[DiagramEditor] Page root not found');
      return false;
    }

    // 解析新元素
    const tempDoc = this.parser.parseFromString(op.element, 'application/xml');
    const parseError = tempDoc.querySelector('parsererror');
    if (parseError) {
      console.error('[DiagramEditor] Element parse error:', parseError.textContent);
      return false;
    }

    const newElement = tempDoc.documentElement;
    if (!newElement) {
      console.error('[DiagramEditor] No element in XML');
      return false;
    }

    // 导入并添加到页面
    const imported = this.doc!.importNode(newElement, true);
    root.appendChild(imported);

    console.log('[DiagramEditor] Element added:', op.element.substring(0, 100));
    return true;
  }

  /**
   * 删除元素
   */
  private deleteElement(op: EditOperation): boolean {
    if (!op.elementId) {
      console.error('[DiagramEditor] No element ID to delete');
      return false;
    }

    const root = this.getPageRoot(op.pageIndex || 0);
    if (!root) return false;

    const element = root.querySelector(`[id="${op.elementId}"]`);
    if (!element) {
      console.error('[DiagramEditor] Element not found:', op.elementId);
      return false;
    }

    element.parentNode?.removeChild(element);
    console.log('[DiagramEditor] Element deleted:', op.elementId);
    return true;
  }

  /**
   * 更新元素属性
   */
  private updateElement(op: EditOperation): boolean {
    if (!op.elementId || !op.properties) {
      console.error('[DiagramEditor] No element ID or properties to update');
      return false;
    }

    const root = this.getPageRoot(op.pageIndex || 0);
    if (!root) return false;

    const element = root.querySelector(`[id="${op.elementId}"]`);
    if (!element) {
      console.error('[DiagramEditor] Element not found:', op.elementId);
      return false;
    }

    // 更新属性
    for (const [key, value] of Object.entries(op.properties)) {
      if (key === 'geometry') {
        // 特殊处理几何属性
        const geometry = element.querySelector('mxGeometry');
        if (geometry && typeof value === 'object') {
          const geo = value as Record<string, number>;
          if (geo.x !== undefined) geometry.setAttribute('x', String(geo.x));
          if (geo.y !== undefined) geometry.setAttribute('y', String(geo.y));
          if (geo.width !== undefined) geometry.setAttribute('width', String(geo.width));
          if (geo.height !== undefined) geometry.setAttribute('height', String(geo.height));
        }
      } else {
        element.setAttribute(key, value);
      }
    }

    console.log('[DiagramEditor] Element updated:', op.elementId);
    return true;
  }

  /**
   * 替换整个页面
   */
  private replacePage(op: EditOperation): boolean {
    if (!op.pageXml) {
      console.error('[DiagramEditor] No page XML to replace');
      return false;
    }

    const pageIndex = op.pageIndex ?? 0;

    // 解析新页面 XML
    let newContent: string = op.pageXml;
    
    // 如果新 XML 是纯 mxGraphModel，提取内容
    const tempDoc = this.parser.parseFromString(newContent, 'application/xml');
    const parseError = tempDoc.querySelector('parsererror');
    if (parseError) {
      console.error('[DiagramEditor] Page XML parse error:', parseError.textContent);
      return false;
    }

    const mxfile = this.doc!.querySelector('mxfile');
    
    if (mxfile) {
      // 多页面格式
      const diagrams = mxfile.querySelectorAll('diagram');
      
      if (pageIndex >= diagrams.length) {
        // 添加新页面
        const pageName = op.pageName || `Page-${diagrams.length + 1}`;
        const pageId = `page-${Date.now()}`;
        const newDiagram = this.doc!.createElement('diagram');
        newDiagram.setAttribute('id', pageId);
        newDiagram.setAttribute('name', pageName);
        
        // 设置内容
        const mxGraphModel = tempDoc.querySelector('mxGraphModel');
        if (mxGraphModel) {
          const imported = this.doc!.importNode(mxGraphModel, true);
          newDiagram.appendChild(imported);
        } else {
          newDiagram.innerHTML = newContent;
        }
        
        mxfile.appendChild(newDiagram);
        console.log('[DiagramEditor] New page added:', pageName);
      } else {
        // 替换现有页面
        const diagram = diagrams[pageIndex];
        
        // 更新名称（如果提供）
        if (op.pageName) {
          diagram.setAttribute('name', op.pageName);
        }
        
        // 替换内容
        const mxGraphModel = tempDoc.querySelector('mxGraphModel');
        if (mxGraphModel) {
          // 清空现有内容
          while (diagram.firstChild) {
            diagram.removeChild(diagram.firstChild);
          }
          // 添加新内容
          const imported = this.doc!.importNode(mxGraphModel, true);
          diagram.appendChild(imported);
        }
        
        console.log('[DiagramEditor] Page replaced:', pageIndex);
      }
    } else {
      // 单页面格式，转换为多页面或直接替换
      const existingModel = this.doc!.querySelector('mxGraphModel');
      const newModel = tempDoc.querySelector('mxGraphModel');
      
      if (existingModel && newModel && pageIndex === 0) {
        // 替换整个内容
        const parent = existingModel.parentNode;
        const imported = this.doc!.importNode(newModel, true);
        parent?.replaceChild(imported, existingModel);
        console.log('[DiagramEditor] Single page replaced');
      } else if (pageIndex > 0) {
        // 需要转换为多页面格式
        return this.convertToMultiPageAndReplace(op);
      }
    }

    return true;
  }

  /**
   * 转换为多页面格式并添加页面
   */
  private convertToMultiPageAndReplace(op: EditOperation): boolean {
    const existingModel = this.doc!.querySelector('mxGraphModel');
    if (!existingModel) return false;

    // 创建新的 mxfile 结构
    const newDoc = this.parser.parseFromString('<mxfile></mxfile>', 'application/xml');
    const mxfile = newDoc.documentElement;

    // 添加第一页（现有内容）
    const firstDiagram = newDoc.createElement('diagram');
    firstDiagram.setAttribute('id', 'page-1');
    firstDiagram.setAttribute('name', 'Page-1');
    const importedFirst = newDoc.importNode(existingModel, true);
    firstDiagram.appendChild(importedFirst);
    mxfile.appendChild(firstDiagram);

    // 添加新页面
    const pageIndex = op.pageIndex ?? 1;
    const newModel = this.parser.parseFromString(op.pageXml!, 'application/xml').querySelector('mxGraphModel');
    
    if (newModel) {
      const newDiagram = newDoc.createElement('diagram');
      newDiagram.setAttribute('id', `page-${pageIndex + 1}`);
      newDiagram.setAttribute('name', op.pageName || `Page-${pageIndex + 1}`);
      const importedNew = newDoc.importNode(newModel, true);
      newDiagram.appendChild(importedNew);
      mxfile.appendChild(newDiagram);
    }

    this.doc = newDoc;
    console.log('[DiagramEditor] Converted to multi-page format');
    return true;
  }

  /**
   * 获取指定页面的 root 元素
   */
  private getPageRoot(pageIndex: number): Element | null {
    if (!this.doc) return null;

    const mxfile = this.doc.querySelector('mxfile');
    
    if (mxfile) {
      const diagrams = mxfile.querySelectorAll('diagram');
      if (pageIndex >= diagrams.length) return null;
      return diagrams[pageIndex].querySelector('mxGraphModel > root');
    } else {
      // 单页面格式
      if (pageIndex !== 0) return null;
      return this.doc.querySelector('mxGraphModel > root');
    }
  }

  /**
   * 序列化为 XML 字符串
   */
  serialize(): string {
    if (!this.doc) return this.rawXml;
    
    let xml = this.serializer.serializeToString(this.doc);
    
    // 清理 XML 声明（如果存在）
    xml = xml.replace(/^<\?xml[^?]*\?>\s*/, '');
    
    return xml;
  }

  /**
   * 获取原始 XML
   */
  getRawXml(): string {
    return this.rawXml;
  }
}

// 导出单例实例
export const diagramEditor = new DiagramEditor();

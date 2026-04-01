# 操作手册

::: warning 版本说明
本操作手册基于 **v1.4.0** 版本编写，部分界面和功能可能与最新版本存在差异。
:::

## 注意事项
**1、** docker部署会自动化初始化一些配置，只需要配置系统管理-LLM配置-填写对应的大模型配置。

**2、** docker部署后需要访问：http://localhost:8917/ 下载对应的 bge-m3 、bge-reranker-v2-m3。具体看下方知识库配置。
```bash
# 下载模型cmd命令
curl -X POST http://localhost:8917/v1/models -d "{\"model_name\": \"bge-reranker-v2-m3\", \"model_type\": \"rerank\"}"
curl -X POST http://localhost:8917/v1/models -d "{\"model_name\": \"bge-m3\", \"model_type\": \"embedding\"}"
```


## 1. 登录

- **输入账号**：admin
- **输入账号**：admin123456

  ![alt text](image.png)

## 2. 首页 

- **登录后默认进入首页**：

![alt text](image-1.png)

## 3. 项目管理

- **描述**：docker部署（推荐）的会有一个默认项目，源码部署需要运行init初始化文件

![alt text](image-2.png)

- **项目管理描述**：

1、平台数据是根据项目进行隔离的

2、admin 可以看见所有的项目，普通用户只能看见自己的项目，添加其他用户为项目成员后，其他用户可以访问被添加的项目。

3、项目中的项目凭证是给AI生成测试用例 时候看的，AI 会获取这里的信息，放到对应的用例之中。

![alt text](image-4.png)

![alt text](image-3.png)

## 4. 需求管理 

- **需求管理描述**：AI 进行需求评审并指出问题。

1、上传文件：仅支持提示指出的这些（推荐使用 docx 后缀文件）。

![alt text](image-5.png)

2、上传后-点击详情或者是点击拆分（其实进入的是一个页面）。

![alt text](image-6.png)

3、点击模块拆分，根据你文档的真实情况选择对应的H等级（如果没有H等级，可以按照最后的这个字数拆分但是不推荐）。

![alt text](image-7.png)

![alt text](image-8.png)

4、点击确定后，确认拆分的模块是否正确，确认无误后点击确认，即可进行需求评审或生成用例。

![alt text](image-9.png)

![alt text](image-10.png)

![alt text](image-11.png)

5、注意：拆分模块后，就可以进行生成用例了，不需要评审之后再进行生成用例。

![alt text](image-12.png)

6、点击评审，选择AI评审并发数（如果不支持高并发，就选低一点，要不然会报错），点击确认。

![alt text](image-13.png)

![alt text](image-14.png)

7、点击确认后，右上角会有实时进度条。

![alt text](image-15.png)

8、评审完成后，点击查看报告，即可查看各个维度的专项问题及评分。

![alt text](image-16.png)

![alt text](image-17.png)

9、评审中时，如想返回查看进度，可点击详情或者查看进度按钮（点那个都一样，进入的也是同一个页面）。

![alt text](image-18.png)

![alt text](image-19.png)

10、注意！！！

如何让AI按照你的想法去评审，点击LLM对话 - 点击提示词管理 - 修改对应的提示词内容即可定制评审规范。

![alt text](image-20.png)

![alt text](image-21.png)

![alt text](image-22.png)

## 5. 智能图表 

- **智能图表描述**：AI 根据文本生成对应的流程图等。

1、点击右下角小图标，进行对话

注意！！！当前图片仅保存在浏览器缓存中，如有需要请点击导出

![alt text](image-23.png)

![alt text](image-24.png)

![alt text](image-25.png)

## 6. 用例管理

### 6.1 用例管理 - 模块管理

1、添加用例模块：点击操作，点击添加根模块

![alt text](image-26.png)

![alt text](image-27.png)

![alt text](image-28.png)

2、模块后面的数据，表示当前模块下有多少条数据。

![alt text](image-29.png)

### 6.2 用例管理 - 添加用例

1、点击右上角添加用例，即可添加用例

![alt text](image-30.png)

### 6.3 用例管理 - AI 生成测试用例

注意！！！

生成用例之前需要先检查或创建对应的提示词（也就是生成规则）。

菜单路径：LLM对话 - 提示词管理 - 通用类型的提示词

1、完整生成：根据用户选择的需求文档，知识库内容，根据提示词规范进行生成完整用例（提示词中强烈要求可能会打破规则）。

适用场景：需要AI生成完整的测试用例。

![alt text](image-31.png)

2、标题生成：根据用户选择的需求文档，知识库内容，根据提示词规范进行生成用例标题（提示词中强烈要求可能会打破规则）。

适用场景：仅需要AI生成对应的测试用例标题名称等。

![alt text](image-32.png)

3、知识库补全：根据用户选择的知识库内容，根据提示词规范进行补全测试用例的步骤等内容（提示词中强烈要求可能会打破规则）。

适用场景：用户提供测试用例标题名称，步骤备注等内容需要完全根据知识库的历史相似用例进行补全。

![alt text](image-33.png)

4、知识生成：根据用户选择的需求文档，知识库内容，根据提示词规范进行生成测试用例的步骤等内容（提示词中强烈要求可能会打破规则）。

适用场景：用户提供测试用例标题名称，步骤备注等内容需要完全根据知识库的历史相似用例进行智能生成。

![alt text](image-34.png)

### 6.4 用例管理 - 审核状态 

1、在列表页面选择审核状态后，点击查看或是编辑，只会显示对应状态的用例。

![alt text](image-35.png)

![alt text](image-36.png)

![alt text](image-37.png)

2、 AI 生成完成后，所有用例默认状态为待审核

![alt text](image-38.png)

3、当其中某条用例不满意的时候，可点击优化，输入优化建议，AI会再次根据优化建议进行编辑。并把状态改为优化待审核。

![alt text](image-39.png)

![alt text](image-40.png)

![alt text](image-41.png)

![alt text](image-42.png)

![alt text](image-43.png)

4、如果AI生成的用例不可用，可以修改状态为不可用（用例列表页面默认不显示不可用状态的用例）。

![alt text](image-44.png)

5、首页会统计当前项目的AI生成用例的通过率、待审核、待优化、优化待审核、不可用。

![alt text](image-45.png)

### 6.4 用例管理 - 执行

1、点击执行，点击确认，AI会调用playwright来执行测试用例。

![alt text](image-46.png)

2、当勾选生成playwright脚本的时候，AI会根据实际情况，生成对应的playwright脚本。

![alt text](image-47.png)

3、点击执行后，用例后台执行，可点击弹窗查看执行过程。

![alt text](image-48.png)

![alt text](image-49.png)

![alt text](image-50.png)

4、生成的脚本

![alt text](image-51.png)

![alt text](image-52.png)

![alt text](image-53.png)

## 7. UI 脚本库

1、可以手动创建或AI创建，AI创建的就会保存在这里。

![alt text](image-54.png)

2、AI创建的脚本，可以点击右上角的调式，查看实际调用的浏览器的过程。

![alt text](image-55.png)

![alt text](image-56.png)

![alt text](image-57.png)

## 8. 测试套件

描述：可以批量执行生成的功能测试用例或者是脚本。

![alt text](image-58.png)

![alt text](image-59.png)

注意！！！

功能用例的执行依靠大模型，脚本执行纯代码执行。所以选择并发的时候，需要注意大模型的实际支持并发。

1、如果需要为功能测试用例生成对应的playwright脚本，可以勾选这个生成对应的playwright脚本。

![alt text](image-60.png)

2、执行结果可以在执行历史中查看

![alt text](image-61.png)

![alt text](image-62.png)

![alt text](image-63.png)

## 9. LLM对话

描述：和AI进行对话。

![alt text](image-65.png)

![alt text](image-64.png)

## 10. 知识库管理

描述：知识库为AI提供额外的知识。

目前采用的是 bge-m3 + BM25 + bge-reranker-v2-m3 实现知识检索。

1、全局唯一配置，整个平台的知识库都使用此处的配置。

![alt text](image-67.png)

![alt text](image-66.png)

注意！！！

此处默认配置为docker部署的向量模型，如果有自己的api可以进行更换。

2、新建知识库

![alt text](image-68.png)

3、点击知识库的名字，进入上传页面，点击上传文件进行上传。

![alt text](image-69.png)

![alt text](image-70.png)

注意！！！ 上传后需要等待知识库处理完成，才可以进行知识库检索，可以点击刷新查看处理状态。

![alt text](image-71.png)

4、测试知识库，点击查看，在知识库中随便找一个模块的名字，或者是片段，输入在下面，点击查询。

![alt text](image-72.png)

![alt text](image-73.png)

![alt text](image-74.png)

5、知识库统计，点击列表上的统计按钮即可。

![alt text](image-75.png)

## 11. 用户管理

描述：用户管理可以控制用户权限。

![alt text](image-76.png)

![alt text](image-77.png)

## 12. 组织管理

描述：批量控制用户权限。

![alt text](image-78.png)

## 13. 权限管理

描述：可以快改修改用户权限

![alt text](image-79.png)

## 14. LLM配置

描述：整个平台的AI应用的配置

![alt text](image-80.png)

![alt text](image-81.png)

![alt text](image-82.png)

## 15. key管理

描述：FlyTest平台的api的key。目前是给 flytest_mcp 使用的，可以使大模型拥有查询、保存、执行等能力。

注意！！！

如果 FlyTest 平台部署外网访问，强烈建议修改这个默认的key！！！

修改后记得修改 FlyTest_MCP 目录下的 FlyTest_tools.py 中对应的key。

v1.4.0（包括v1.4.0）之后的版本，还需要修改对应的skills。

![alt text](image-83.png)

## 16. MCP配置

描述：docker默认会配置俩个mcp。

FlyTest-Tools：使大模型拥有操控flytest平台的能力。

Playwright-MCP：使大模型拥有操作浏览器的能力。

mcp概念如果不是很清楚，建议了解一下。

![alt text](image-85.png)

![alt text](image-84.png)

## 17. Skills 管理

描述：skills 实现的能力和 mcp 类似。

注意！！！

目前网上的skills都是适配cc的，想要在平台上使用需要修改一下skill.md里面的一些描述和对应脚本文件的路径。

playwright 这个文件有点大，上传会有点慢。耐心的等一会就行。

1、上传FlyTest_Skills目录下的俩个zip文件即可使用。


![alt text](image-87.png)

![alt text](image-89.png)

![alt text](image-88.png)

![alt text](image-86.png)


### 注意！！！

mcp 和 skills 开一个就行，不要都开，会乱！！！

提示词对于AI是很重要的，注意维护自己的提示词！！！

AI生成用例效果不好怎么办 ？

AI执行用例没截图怎么办 ？

AI评审需求的关键点不想要怎么办 ？

AI没查知识库怎么办 ？

解决办法：改对应的提示词 or 换一个更聪明的模型！！！
# FlyTest APP Automation FastAPI

独立的 APP 自动化后端服务，负责设备、应用包、元素、测试用例、执行记录和环境设置等能力。

## 启动

```bash
cd FlyTest_FastAPI_AppAutomation
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8010 --reload
```

默认接口前缀由前端代理到 `/api/app-automation/*`。

## 可选 OCR 能力

如果需要使用 APP 自动化中的 OCR 断言、`foreach_assert`、全屏模板找图等能力，请额外安装：

```bash
python -m pip install easyocr numpy pillow opencv-python
```

未安装这些依赖时，服务仍可正常启动，但执行 OCR 或高级图片匹配相关动作时会返回明确的错误提示。

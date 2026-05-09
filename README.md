# GovProjectConsult-V2
# 科技项目政策智能咨询系统

科技项目政策智能咨询系统 V2 是一个基于**双源 RAG（检索增强生成）**技术的智能问答平台，同时支持政策文件检索和典型案例经验库。

## 核心特性

### 双源 RAG 架构
- **政策文件知识库**：存储官方政策文档、法规条文
- **典型案例经验库**：存储历史案例、实操经验
- **智能融合检索**：自动匹配政策和案例双重来源

### 功能列表
- **智能问答**：基于双源 RAG 的精准回答
- **OCR 识别**：支持 PDF 和图片文档的文字识别
- **AI 幻觉防护**：条款引用完整性验证，确保回答准确
- **反馈系统**：点赞/点踩功能，持续优化回答质量

### 系统组成
- **Backend**：FastAPI 后端服务，处理问答、OCR、知识库管理
- **Frontend**：React 前端界面，用户交互界面

## 技术栈

### 后端
- FastAPI - Web 框架
- PaddleOCR - 文字识别
- ChromaDB - 向量数据库
- OpenAI API - LLM 接口

### 前端
- React 18
- Vite - 构建工具
- TailwindCSS - 样式框架
- Axios - HTTP 客户端

## 项目结构
GovProjectConsult-V2/
├── backend/                    # 后端服务
│   ├── app/
│   │   ├── api/              # API 路由
│   │   ├── core/             # 核心配置（日志、工具）
│   │   ├── ocr/              # OCR 识别模块
│   │   │   └── parsers/     # 文档解析器（合同、发票、报告）
│   │   └── services/         # 业务服务
│   │       ├── chat_service.py    # RAG 问答服务
│   │       └── ingest.py          # 知识库管理
│   ├── requirements.txt      # Python 依赖
│   └── run_server.py        # 服务启动入口
├── frontend/                   # 前端应用
│   ├── src/
│   │   ├── App.jsx          # 主应用组件
│   │   ├── main.jsx         # 入口文件
│   │   ├── index.css        # 全局样式
│   │   └── assets/          # 静态资源
│   ├── package.json         # Node 依赖
│   ├── vite.config.js       # Vite 配置
│   ├── tailwind.config.js   # TailwindCSS 配置
│   └── index.html           # HTML 入口
├── .gitignore                # Git 忽略配置
└── README.md                 # 项目说明文档


## 本地开发

### 环境要求
- Python 3.10+
- Node.js 18+
- OpenAI API Key

### 后端启动

```bash
cd backend
pip install -r requirements.txt
python run_server.py
```

后端服务运行在 http://localhost:8000

### 前端启动

```bash
cd frontend
npm install
npm run dev
```

前端服务运行在 http://localhost:5173

## API 接口

| 接口 | 方法 | 描述 |
|------|------|------|
| `/api/v1/chat` | POST | 发送问答请求 |
| `/api/v1/feedback` | POST | 提交反馈（点赞/点踩） |
| `/api/v1/health` | GET | 健康检查 |
| `/api/v1/project-types` | GET | 获取项目类型列表 |
| `/api/v1/upload` | POST | 上传文档 |

## 配置说明

### 环境变量

在 `backend/` 目录下创建 `.env` 文件：

```env
OPENAI_API_KEY=your_api_key_here
OPENAI_BASE_URL=https://api.openai.com/v1
MODEL_NAME=gpt-4o-mini
```

## 可补充内容（未上传）

以下内容可根据实际需求补充：

### 知识库数据
- `data/` - 知识库目录
  - **policy/** - 政策文件知识库（ChromaDB 向量数据库）
  - **cases/** - 典型案例经验库
- 可通过 `backend/app/services/ingest.py` 导入政策文件和案例

### 依赖说明
- OCR 功能依赖 PaddleOCR 模型
- 向量数据库依赖 ChromaDB

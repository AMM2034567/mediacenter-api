# MediaCenter 后端服务 (FastAPI)

聚合网络多媒体中心中心化后端，专为移动端多媒体 App 提供统一、高速的数据聚合与解析接口。

## 🌟 特性

- **动态订阅自动同步**：服务启动时自动从远程 GitHub 拉取最新的 Base58 订阅源（如 `jin18.txt`），自动淘汰死源、纳入新源。
- **全网多源并发聚合**：基于 Python 异步协程（`asyncio` + `httpx`），秒级并发检索 20+ 个主流视频采集源。
- **统一数据协议**：屏蔽各源站差异，为安卓端提供规范的 JSON 数据模型与 `.m3u8` 原生切片串流。
- **开箱即用云端部署**：原生配置适配 **Hugging Face Spaces**（监听 `7860` 端口），同时也支持 Docker、VPS 或本地运行。

---

## 🚀 本地开发与运行

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 启动服务
```bash
uvicorn app.main:app --host 0.0.0.0 --port 7860 --reload
```

启动后访问：
- **Swagger 交互式 API 文档**：http://localhost:7860/docs
- **服务健康与源状态**：http://localhost:7860/

---

## 📡 核心 API 说明

| 接口 | 方法 | 说明 | 示例 |
| :--- | :--- | :--- | :--- |
| `/api/v1/sources` | `GET` | 获取当前注册的所有可用源列表 | `/api/v1/sources` |
| `/api/v1/sources/refresh` | `POST` | 手动/定时重新从 GitHub 拉取更新源 | `/api/v1/sources/refresh` |
| `/api/v1/search` | `GET` | 多源并发搜索影视/番剧 | `/api/v1/search?kw=凡人修仙传&limit=20` |
| `/api/v1/detail` | `GET` | 获取影片详情及所有播放线路与分集列表 | `/api/v1/detail?id=maccms:ikunzy.com:17712` |

---

## ☁️ 部署到 Hugging Face Spaces (永久免费)

1. 登录 Hugging Face，点击 **New Space**。
2. Space SDK 选择 **Docker** (Blank)。
3. 将当前 `backend/` 目录下的所有文件推送至该 Space 的 Git 仓库：
   ```bash
   git remote add space https://huggingface.co/spaces/<你的用户名>/<你的Space名>
   git push space main
   ```
4. 部署成功后，你将获得一个免费的公网 HTTPS API：
   `https://<你的用户名>-<你的Space名>.hf.space`

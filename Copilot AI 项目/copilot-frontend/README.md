# Copilot Frontend Docker 部署说明

## 构建Docker镜像

```bash
docker build -t copilot-frontend .
```

## 运行容器

### 方式1: 独立部署（连接到外部后端）

如果后端服务独立部署在宿主机上（端口5001），可以使用以下命令运行：

```bash
docker run -p 3000:3000 -e COPILOT_BACK_BASE_URL=http://host.docker.internal:5001 copilot-frontend
```
COPILOT_BACK_BASE_URL代表后端服务所在的地址，如果后端服务和前端分开部署，请将host.docker.internal改为真实的后端服务器IP地址。

### 方式2: 使用docker-compose

使用docker-compose-standalone.yml文件启动前端服务：

```bash
docker-compose -f docker-compose-standalone.yml up
```

## 环境变量

- `COPILOT_BACK_BASE_URL`: 后端服务的基础URL，默认为`http://localhost:5001`

## 访问应用

构建并运行成功后，可以通过以下地址访问应用：
http://localhost:3000

## 注意事项

1. 如果后端服务部署在不同的地址或端口，请相应修改`COPILOT_BACK_BASE_URL`环境变量。
2. 在Linux系统中，可能需要将`host.docker.internal`替换为宿主机的实际IP地址。

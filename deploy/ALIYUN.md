# 阿里云 ECS 部署

建议使用 Ubuntu 24.04 LTS、至少 2 核 4 GB（构建时 4 核 8 GB 更稳妥）、40 GB 系统盘。安全组仅放行 22、80；配置 HTTPS 后再放行 443。国内地域的公开域名需要 ICP 备案。

在 ECS 安装 Git、Docker Engine 与 Docker Compose plugin，然后执行：

```bash
git clone <repository-url> BrandVideo
cd BrandVideo
cp .env.deploy.example .env.deploy
nano .env.deploy
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps
curl -f http://127.0.0.1/api/health
```

必须修改 `SILICONFLOW_API_KEY` 和 `CORS_ORIGINS`。需要联网检索时再填写 `TAVILY_API_KEY`。不要提交 `.env.deploy`。

更新与查看日志：

```bash
git pull --ff-only
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml logs -f --tail=200 backend nginx
```

MongoDB 和 Redis 不映射公网端口，只允许 Compose 内部访问。长期运行应定时执行 `mongodump` 并将备份同步到 OSS。

当前 Nginx 配置提供 HTTP。域名解析到 ECS 后，可用 Certbot 或阿里云证书开启 HTTPS；之后把 `CORS_ORIGINS` 改成实际的 `https://域名` 并重启 backend。

## GitHub main 自动部署

工作流 `.github/workflows/deploy.yml` 在提交进入 `main` 后先运行测试，再通过 SSH 让 ECS 直接从 GitHub 拉取 `main` 并部署到 `$HOME/brandvideo`。也可以在 GitHub Actions 页面手动运行。

首次部署前，在 ECS 上执行：

```bash
mkdir -p "$HOME/brandvideo"
cp .env.deploy.example "$HOME/brandvideo/.env.deploy"
nano "$HOME/brandvideo/.env.deploy"
```

在 GitHub 仓库的 **Settings → Environments → production** 中创建环境，并在该环境添加以下 Secrets：

| Secret | 内容 |
| --- | --- |
| `ECS_HOST` | ECS 公网 IP 或域名 |
| `ECS_USER` | SSH 用户，例如 `ubuntu` |
| `ECS_PORT` | SSH 端口；可留空，默认 22 |
| `ECS_SSH_KEY` | 专门用于部署的 SSH 私钥全文 |
| `ECS_KNOWN_HOSTS` | 在可信电脑执行 `ssh-keyscan -H ECS_IP` 得到的整行结果 |

建议给 `production` 环境设置 required reviewers，并为 Actions 单独创建权限受限的部署用户和 SSH 密钥。服务器上的部署用户必须能运行 Docker。

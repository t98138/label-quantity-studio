# Debian 部署

此工具为静态网页，无服务端数据库。服务器只发送资源文件，PDF 计算在浏览器完成。

## 启动与本机验证

安装 Docker Engine 与 Compose 插件后，在仓库根目录运行：

```sh
docker compose -f deploy/compose.yaml up -d
curl -I http://127.0.0.1:8767/
```

默认只监听服务器回环地址。通过 SSH 隧道在自己的电脑访问：

```sh
ssh -L 8768:127.0.0.1:8767 user@server
```

打开 http://127.0.0.1:8768/ 。不要在生产环境使用 Python 开发服务器。

## 已有 HTTPS 反向代理

将站点挂在独立域名，或通过 `handle_path /qianshu/*` 挂载到已有域名。
代理必须覆盖全部资源，而不仅是首页。启用 HTTPS 和服务端登录保护后再分享入口。

Caddy 配置示例（替换域名和密码哈希，不把实际凭据放进仓库）：

```caddyfile
labels.example.com {
    basic_auth {
        user REPLACE_WITH_CADDY_PASSWORD_HASH
    }
    reverse_proxy 127.0.0.1:8767
}
```

密码哈希用 `caddy hash-password` 交互生成。如果 Caddy 本身在容器内运行，
应将两容器接入同一个 Docker 网络，通过服务名和容器端口代理；
容器里的 `127.0.0.1` 指向其自身，不能使用上面的主机地址。

## 私有共享标签库

不要把公司模板复制进 Git 工作树。将部署文件复制到仓库外的私有目录，
再将该目录作为 `/srv` 只读挂载，覆盖其中的 `samples/` 目录。
目录清单、PDF、预览图都必须走相同的 HTTPS 登录保护。
更新程序时保留私有 `samples/` 数据；不要直接覆盖整个部署目录。

公共代码和私有资源分别更新。浏览器个人导入仍只保存在当前浏览器，
不会自动回写服务器。部署完成后检查匿名访问所有私有路径都返回 401，
登录后页面、目录、PDF 和预览图均能正常访问。

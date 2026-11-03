# 可选：记住设备的私有登录

用 Cookie 会话替代浏览器 Basic Auth 弹窗。勾选“记住此设备”时有效期为 30 天；
未勾选时使用浏览器会话 Cookie，服务端最长允许 12 小时。浏览器若恢复会话，
会话 Cookie 也可能被恢复，因此公共设备应主动退出。

该网关只处理认证，不处理或保存标签。保持静态文件由 Caddy 提供。
登录密码派生值与会话数据库均在 Git 仓库之外。会话数据库只保存随机令牌的 SHA256，
使用 Secure、HttpOnly、SameSite=Lax Cookie；退出后服务端立即吊销。
浏览器清理站点数据、使用无痕窗口、切换浏览器或到期后需重新登录。

## Debian 配置

1. 将 `server.py` 和 `page.html` 放到 `/opt/qianshu/auth/`，目录与文件仅管理员可写。
2. 使用下列命令交互创建密码派生值。**输入现有网站密码**，不需要更换账号密码。
   输出文件应只允许 root 读取，文件路径不应放进静态站点或 Git 仓库。

```sh
sudo python3 deploy/auth/create_credential.py /opt/qianshu/auth-credential.json
```

3. 创建 `/opt/qianshu/auth.env`：

```ini
QS_ORIGIN=https://labels.example.com
QS_BIND=127.0.0.1
QS_PORT=8787
```

`QS_ORIGIN` 必须与浏览器入口完全一致（包含非标准端口）。
如果 Caddy 在 Docker 内运行，监听地址改为对应 Docker 网络的主机网关，
Caddy 的上游也用同一地址。认证端口不要对公网开放。

4. 安装 `qianshu-auth.service` 到 `/etc/systemd/system/`，执行：

```sh
sudo systemctl daemon-reload
sudo systemctl enable --now qianshu-auth
```

5. 把 `Caddyfile.example` 的路由合并到现有 HTTPS 站点中，替换内部上游地址，
   移除签数路径原有的 `basic_auth`。所有 `/qianshu/` 下的静态资源均须走 `forward_auth`。
   认证网关停止时，访问应失败，不能回退为公开静态文件。
   验证 Caddy 配置后再 reload，保留其他网站路由。
6. 在私有站点导航添加 `<a href="/qianshu/auth/logout">退出登录</a>`。

当前实现固定使用 `/qianshu/` 前缀，修改入口路径时应同步代码、Cookie 与代理配置。
凭据派生值变化并重启认证服务后，现存会话全部失效。

## 验证

```sh
python3 -m unittest discover -s deploy/auth -p 'test_*.py' -v
```

测试仅使用本机回环临时端口与可丢弃数据库，覆盖登录、30 天 Cookie、会话重启持久化、
未勾选记住设备、过期、退出吊销、CSRF、跳转限制与登录限速。
上线后仍须通过正式 HTTPS 入口检查网页、PDF、缩略图与目录清单的认证。

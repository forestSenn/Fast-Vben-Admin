# FAQ

## 本地测试报 `failed to resolve host 'db'`

`.env` 默认适配 Docker Compose，`POSTGRES_SERVER=db` 只在容器网络中可用。本机直接跑后端测试时覆盖为：

```powershell
$env:POSTGRES_SERVER='localhost'
```

## 如何启动本地 PostgreSQL

如果使用 Scoop 安装 PostgreSQL，可检查 `PGDATA` 并启动：

```powershell
pg_ctl status -D $env:PGDATA
pg_ctl start -D $env:PGDATA -l "$env:PGDATA\postgresql.log"
```

## 前端菜单不显示

确认当前用户有角色，角色绑定了对应菜单或按钮权限。前端默认从 `/menus/me` 加载菜单。

## API 类型没有更新

确认后端 OpenAPI 是最新的，再运行：

```powershell
pnpm generate:api
```

如果端口上有旧后端进程，可以导出本地 schema 文件后用 `OPENAPI_INPUT` 指向该文件。

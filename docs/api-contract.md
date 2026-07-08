# API 契约

## 基础路径

所有业务接口位于 `/api/v1` 下。

## 错误响应

统一错误响应格式：

```json
{
  "code": "VALIDATION_ERROR",
  "message": "Request validation failed",
  "details": {}
}
```

常见状态码：

- `401`：认证失败。
- `403`：无权限。
- `404`：资源不存在。
- `422`：请求参数校验失败。
- `500`：服务端错误。

## 分页响应

列表接口返回：

```json
{
  "items": [],
  "total": 0,
  "page": 1,
  "page_size": 20
}
```

## 认证

登录接口返回 Bearer token。前端请求通过 `Authorization: Bearer <token>` 访问受保护接口。

## 权限

管理接口通过 `require_permission("<permission_code>")` 校验。前端菜单和按钮隐藏只做体验优化，后端权限是最终边界。

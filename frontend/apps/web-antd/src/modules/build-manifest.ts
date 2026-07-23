export const buildManifest = {
  "schema_version": 2,
  "edition": "suite",
  "source_revision": "4de5683e16b81922aac6d3a8c5c4b2a2c6fca83c",
  "platform_contract_version": 1,
  "platform_version": "1.0.0",
  "modules": [
    {
      "code": "platform",
      "version": "1.0.0",
      "migration_namespace": "platform",
      "migration_heads": [
        "c7e1a5f9b3d6"
      ],
      "openapi_sha256": "sha256:91324c327537ab2baf38536ed6b852c4c13cbc6daba4055485e48e69a7c533ed"
    },
    {
      "code": "items",
      "version": "1.0.0",
      "migration_namespace": "items",
      "migration_heads": [
        "items_enable_tenant_rls"
      ],
      "openapi_sha256": "sha256:131ecf3acc5f1e4a6a3e06914bb117e12922ac87836d891486127afca13ce100"
    },
    {
      "code": "erp",
      "version": "0.1.0",
      "migration_namespace": "erp",
      "migration_heads": [
        "erp_trade_doc_snapshots"
      ],
      "openapi_sha256": "sha256:45d3b217d856a0f1e94122b6341aa33345a73e5376f6584972507a02c2b605a7"
    }
  ],
  "manifest_digest": "sha256:35cd3d3728a520f7efe5858af20ba530c75fbfd710e944265aa03deea62986e2"
} as const;

"""
Registrar pipeline package.

A recurring pipeline that scrapes California county registrar
websites for local ballot measures, stores raw artifacts in a
canonical artifact store (Cloudflare R2 in prod, local FS in dev),
and emits normalized records for the loader. See
docs/plans/registrar_pipeline_infra.md for full design.
"""

#!/bin/sh
set -e

echo "Initializing MinIO bucket and public read policy..."
mc alias set local http://minio:9000 "${MINIO_ROOT_USER:-minioadmin}" "${MINIO_ROOT_PASSWORD:-minioadmin_secret}"
mc mb --ignore-existing "local/${S3_BUCKET_NAME:-studio-assets}"
mc anonymous set download "local/${S3_BUCKET_NAME:-studio-assets}"
echo "Bucket '${S3_BUCKET_NAME:-studio-assets}' provisioned with public-read policy."

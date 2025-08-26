#!/bin/sh
set -eu

# Environment variables:
#   RESTORE_SOURCE: s3 or local
#   S3_BUCKET/S3_REGION/AWS creds: where backups are stored
#   S3_PATH: path/prefix in bucket (e.g., postgres)
#   LOCAL_PATH: fallback or local backup path (default /backup)
#   TARGET_HOST: postgres service hostname (default postgres-restore)
#   TARGET_DB: database name
#   TARGET_USER: db user

SRC=${RESTORE_SOURCE:-s3}
BUCKET=${S3_BUCKET:-}
REGION=${S3_REGION:-}
S3PATH=${S3_PATH:-postgres}
LOCAL=${LOCAL_PATH:-/backup}
HOST=${TARGET_HOST:-postgres-restore}
DB=${TARGET_DB:-n8n}
USER=${TARGET_USER:-n8n}

echo "Restore source: $SRC"

find_latest_s3() {
  aws s3 ls "$BUCKET/$S3PATH/" --recursive | awk '{print $4}' | sort | tail -n 1
}

find_latest_local() {
  ls -1t "$LOCAL" | head -n 1
}

fetch_s3() {
  key=$(find_latest_s3)
  if [ -z "$key" ]; then
    echo "No backups found in $BUCKET/$S3PATH" >&2
    exit 1
  fi
  echo "Downloading s3://$key"
  aws s3 cp "$BUCKET/$key" /work/restore.zst
}

fetch_local() {
  f=$(find_latest_local)
  if [ -z "$f" ]; then
    echo "No local backups found in $LOCAL" >&2
    exit 1
  fi
  echo "Using local backup: $f"
  cp "$LOCAL/$f" /work/restore.zst
}

export AWS_PAGER=""
if [ "$SRC" = "s3" ]; then
  [ -z "$BUCKET" ] && echo "S3_BUCKET not set" && exit 1
  [ -n "$REGION" ] && aws configure set region "$REGION"
  fetch_s3
else
  fetch_local
fi

echo "Decompressing and restoring to $HOST/$DB as $USER"
zstd -d -c /work/restore.zst | PGPASSWORD=${TARGET_PASSWORD:-} psql -h "$HOST" -U "$USER" -d "$DB" -v ON_ERROR_STOP=1
echo "Restore completed"


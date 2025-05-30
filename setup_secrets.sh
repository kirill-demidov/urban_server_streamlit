#!/bin/bash

# Создаем секреты
echo "Создание секретов в Google Cloud Secret Manager..."

# Создаем секрет для schema_name
echo -n "your_schema_name" | gcloud secrets create urban-server-schema-name --data-file=-

# Создаем секрет для base_url
echo -n "your_api_base_url" | gcloud secrets create urban-server-base-url --data-file=-

# Предоставляем доступ к секретам для Cloud Run
echo "Предоставление доступа к секретам для Cloud Run..."

# Получаем email сервисного аккаунта Cloud Run
SERVICE_ACCOUNT="$(gcloud run services describe urban-server --platform managed --region europe-west1 --format 'value(spec.template.spec.serviceAccountName)')"

# Предоставляем доступ к секретам
gcloud secrets add-iam-policy-binding urban-server-schema-name \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding urban-server-base-url \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/secretmanager.secretAccessor"

echo "Секреты успешно настроены!" 
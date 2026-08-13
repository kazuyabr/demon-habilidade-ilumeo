# Terraform GCP — deploy de referência

Módulo Terraform de **referência** para produção do RiskLens no GCP.

> **Status:** referência comentada — não executado neste case (exige conta GCP e
> credenciais). Serve como planta do deploy e prova de conhecimento em IaC.

## Recursos

| Recurso | Papel |
|---|---|
| Cloud SQL (Postgres 16) | fonte da verdade; habilite `CREATE EXTENSION vector` na primeira migração |
| Memorystore (Redis) | fila arq + cache + pub/sub do trace |
| GCS bucket | uploads (adapter `DocumentStorage`) |
| Cloud Run (api + worker) | mesma imagem, `args` diferentes; escala para 0 |
| Secret Manager | `JWT_SECRET`, `LLM_API_KEY` |
| VPC + Serverless VPC connector | Cloud Run → recursos privados |

## Como a aplicação mapeia

- `UPLOAD_DIR=gs://<bucket>` → o adapter GCS do `DocumentStorage`
- `DATABASE_URL` → Cloud SQL; `REDIS_URL` → Memorystore
- `LLM_API_KEY`/`LLM_BASE_URL` → Vertex AI (Gemini) via provider OpenAI-compatível
  ou adapter próprio — a camada de ports torna a troca pontual

## Canary e rollback

- Cloud Run: publique uma nova revisão e mude o percentual de tráfego (ex.: canary 5%),
  aguarde health checks, promova.
- Feature flags server-side (`ff_agent_review_enabled`, `ff_rag_hybrid_search`,
  `ff_eval_llm_judge`) controlam comportamento sem novo deploy.

## Como executar (quando tiver conta)

```bash
export GOOGLE_APPLICATION_CREDENTIALS=~/sa.json
terraform init
terraform plan -var "project_id=<PROJECT>" -var "api_image=gcr.io/<PROJECT>/risklens-api:<tag>" -var "db_password=<senha>"
terraform apply
```

## Alternativa AWS

Mesmo desenho: ECS Fargate (API/worker), S3 (uploads), SQS (fila), ElastiCache Redis,
Secrets Manager. Os adaptadores `DocumentStorage`/`JobQueue` isolam a troca.

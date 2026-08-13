output "api_url" {
  description = "URL pública da API (Cloud Run)"
  value       = google_cloud_run_v2_service.api.uri
}

output "worker_service" {
  description = "Nome do serviço do worker"
  value       = google_cloud_run_v2_service.worker.name
}

output "postgres_instance" {
  description = "Instância Cloud SQL"
  value       = google_sql_database_instance.main.name
}

output "uploads_bucket" {
  description = "Bucket de uploads (DocumentStorage adapter)"
  value       = google_storage_bucket.uploads.name
}

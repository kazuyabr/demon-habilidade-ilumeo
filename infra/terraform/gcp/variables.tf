variable "project_id" {
  description = "GCP project id"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "us-central1"
}

variable "api_image" {
  description = "Container image for API/worker (gcr.io/<project>/risklens-api:<tag>)"
  type        = string
}

variable "db_password" {
  description = "Password for the Cloud SQL app user"
  type        = string
  sensitive   = true
}

variable "run_sa" {
  description = "Service account used by Cloud Run (must have secret accessor role)"
  type        = string
  default     = "default"
}

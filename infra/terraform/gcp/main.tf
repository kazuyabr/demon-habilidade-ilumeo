# RiskLens — Terraform (GCP) · REFERÊNCIA
#
# Planta de deploy para produção. Não executado no case (exige conta GCP);
# a aplicação já está preparada para trocar os adaptadores:
#   DocumentStorage -> GCS   ·  JobQueue -> Pub/Sub (ou arq+Memorystore)
#   LLM local        -> Vertex AI (Gemini)
#
# Uso:
#   terraform init
#   terraform plan -var-file=terraform.tfvars
#   terraform apply
#
# Recomenda-se um backend remoto (GCS) para o tfstate em produção.

terraform {
  required_version = ">= 1.6"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# ---------------------------------------------------------------------------
# Cloud SQL (Postgres + pgvector) — fonte da verdade
# ---------------------------------------------------------------------------
resource "google_sql_database_instance" "main" {
  name             = "risklens-pg"
  database_version = "POSTGRES_16"
  region           = var.region

  settings {
    tier = "db-custom-1-3840"
    disk_size = 20
    ip_configuration {
      private_network = google_compute_network.vpc.id
      # Cloud SQL só acessível via VPC (Serverless VPC connector / Cloud Run)
    }
    database_flags {
      name  = "cloudsql.iam_authentication"
      value = "off"
    }
  }
}

resource "google_sql_database" "main" {
  name     = "risklens"
  instance = google_sql_database_instance.main.name
}

# O caso usa pgvector; habilite a extensão no primeiro boot da aplicação:
#   CREATE EXTENSION IF NOT EXISTS vector;
# (a migração Alembic já executa isso — mantenha a mesma migração em produção)

# ---------------------------------------------------------------------------
# Memorystore (Redis) — fila arq + cache + pub/sub do trace do agente
# ---------------------------------------------------------------------------
resource "google_redis_instance" "main" {
  name           = "risklens-redis"
  tier           = "STANDARD_HA"
  memory_size_gb = 1
  region         = var.region
  connect_mode   = "PRIVATE_SERVICE_ACCESS"
}

# ---------------------------------------------------------------------------
# GCS — uploads de documentos (DocumentStorage adapter)
# ---------------------------------------------------------------------------
resource "google_storage_bucket" "uploads" {
  name          = "${var.project_id}-risklens-uploads"
  location      = var.region
  force_destroy = true
  uniform_bucket_level_access = true
}

# ---------------------------------------------------------------------------
# VPC + connector para Cloud Run alcançar Cloud SQL/Redis privados
# ---------------------------------------------------------------------------
resource "google_compute_network" "vpc" {
  name                    = "risklens-vpc"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "main" {
  name          = "risklens-subnet"
  network       = google_compute_network.vpc.id
  region        = var.region
  ip_cidr_range = "10.0.0.0/24"
  private_ip_google_access = true
}

resource "google_vpc_access_connector" "main" {
  name    = "risklens-connector"
  region  = var.region
  subnet {
    name = google_compute_subnetwork.main.name
  }
  machine_type = "e2-micro"
  min_instances = 2
  max_instances = 3
}

# ---------------------------------------------------------------------------
# Secret Manager — secrets injectados como env vars no Cloud Run
# ---------------------------------------------------------------------------
resource "google_secret_manager_secret" "jwt_secret" {
  secret_id = "risklens-jwt-secret"
  replication {
    automatic = true
  }
}

resource "google_secret_manager_secret" "llm_key" {
  secret_id = "risklens-llm-key"
  replication {
    automatic = true
  }
}

# ---------------------------------------------------------------------------
# Cloud Run — API e Worker (mesma imagem, comandos diferentes)
# ---------------------------------------------------------------------------
resource "google_cloud_run_v2_service" "api" {
  name     = "risklens-api"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    scaling {
      min_instance_count = 0   # escala para 0 (custo)
      max_instance_count = 10
    }
    containers {
      image = var.api_image  # gcr.io/<project>/risklens-api:<tag>
      env {
        name  = "DATABASE_URL"
        value = "postgresql+asyncpg://${google_sql_user.api.name}@${google_sql_database_instance.main.public_ip_address}:5432/risklens"
      }
      env {
        name  = "REDIS_URL"
        value = "redis://${google_redis_instance.main.host}:6379/0"
      }
      env {
        name  = "JWT_SECRET"
        value_source {
          secret_key_ref { secret = google_secret_manager_secret.jwt_secret.secret_id }
        }
      }
      env {
        name  = "LLM_API_KEY"
        value_source {
          secret_key_ref { secret = google_secret_manager_secret.llm_key.secret_id }
        }
      }
      env {
        name  = "UPLOAD_DIR"
        value = "gs://${google_storage_bucket.uploads.name}"  # DocumentStorage GCS adapter
      }
    }
    vpc_access {
      connector = google_vpc_access_connector.main.id
      egress    = "ALL_TRAFFIC"
    }
  }
}

resource "google_cloud_run_v2_service" "worker" {
  name     = "risklens-worker"
  location = var.region

  template {
    scaling {
      min_instance_count = 0
      max_instance_count = 4   # scale horizontal quando provider for cloud
    }
    containers {
      image = var.api_image
      args  = ["risklens-worker"]
      env {
        name  = "DATABASE_URL"
        value = "postgresql+asyncpg://${google_sql_user.api.name}@${google_sql_database_instance.main.public_ip_address}:5432/risklens"
      }
      env {
        name  = "REDIS_URL"
        value = "redis://${google_redis_instance.main.host}:6379/0"
      }
    }
    vpc_access {
      connector = google_vpc_access_connector.main.id
      egress    = "ALL_TRAFFIC"
    }
  }
}

# ---------------------------------------------------------------------------
# IAM — least privilege
# ---------------------------------------------------------------------------
resource "google_sql_user" "api" {
  name     = "risklens-api"
  instance = google_sql_database_instance.main.name
  password = var.db_password  # em produção: gerar via Secret Manager
}

# Cloud Run (api) pode ler secrets e escrever no bucket
resource "google_project_iam_member" "run_secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${var.run_sa}"
}

# ---------------------------------------------------------------------------
# IAM para o Cloud Run invocar (allUsers anônimo em produção deve ser 401 da app)
# ---------------------------------------------------------------------------
resource "google_cloud_run_v2_service_iam_member" "public" {
  location = google_cloud_run_v2_service.api.location
  project  = google_cloud_run_v2_service.api.project
  service  = google_cloud_run_v2_service.api.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

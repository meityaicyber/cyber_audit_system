# Local Deployment & Certificate Setup Guide

This guide provides a comprehensive, step-by-step walkthrough for deploying the system locally for testing using Docker. It includes instructions for setting up local SSL certificates (HTTPS on localhost) and configuring the AI pipeline to use the requested Nemotron model.

## 1. System Prerequisites

Before starting, ensure your local machine meets the following requirements:

- **OS**: Windows (with WSL2), Linux, or macOS
- **Hardware**: NVIDIA GPU with sufficient VRAM for the target model.
- **Software**: 
  - Docker Desktop or Docker Engine & Docker Compose V2
  - NVIDIA GPU Drivers
  - NVIDIA Container Toolkit (if on Linux/WSL2) to allow Docker to access the GPU

---

## 2. Downloading the Nemotron Model

If you are targeting one of NVIDIA's Nemotron models (e.g., Nemotron-4-15B or Llama-3.1-Nemotron-70B), you can download it via the `huggingface-cli`.

1. **Install HuggingFace CLI** (if not already installed):
   ```bash
   pip install -U "huggingface_hub[cli]"
   ```

2. **Login to HuggingFace** (required if the model is gated):
   ```bash
   huggingface-cli login
   ```

3. **Download the Model**:
   Navigate to the root of your project (where the `models/` directory is located) and run the download command. 
   *(Replace `<nvidia/nemotron-model-id>` with the exact HuggingFace repository ID for your target model)*.

   ```bash
   mkdir -p ../document-standardization/models
   huggingface-cli download <nvidia/nemotron-model-id> \
     --local-dir ../document-standardization/models/nemotron \
     --local-dir-use-symlinks False
   ```

---

## 3. Updating `docker-compose.yml` for Nemotron

Update the `vllm` service in your `docker-compose.yml` to point to the new Nemotron model.

```yaml
  vllm:
    image: vllm/vllm-openai:latest
    container_name: cyber-audit-vllm
    volumes:
      - ../document-standardization:/document-standardization
    ports:
      - "8000:8000"
    command: >
      --model /document-standardization/models/nemotron
      --served-model-name nemotron
      --max-model-len 8192
      --gpu-memory-utilization 0.90
      --trust-remote-code
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    restart: unless-stopped
```

---

## 4. Setting up Local SSL Certificates (Localhost HTTPS)

Some frontend features might require a secure context (HTTPS) to function properly even when testing locally. We can use Caddy to automatically generate a self-signed local certificate for `localhost`.

Create a new file named `Caddyfile` in your `backend/` directory:

```caddyfile
localhost {
    # This tells Caddy to generate a local self-signed certificate
    tls internal
    
    reverse_proxy frontend:80
}

api.localhost {
    tls internal
    reverse_proxy backend:8002
}
```

Next, add the Caddy service to your `docker-compose.yml` (and modify the frontend ports so they aren't exposed directly):

```yaml
  caddy:
    image: caddy:2-alpine
    container_name: cyber-audit-caddy
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - caddy_data:/data
      - caddy_config:/config
    depends_on:
      - frontend
      - backend

volumes:
  postgres_data:
  seaweedfs_data:
  seaweedfs_master_data:
  seaweedfs_filer_data:
  caddy_data:      
  caddy_config:    
```

**Important**: Remove the `ports: - "3000:80"` block from your `frontend` service in `docker-compose.yml` so that traffic is routed locally through Caddy on port 443 (HTTPS).

---

## 5. Local Deployment Steps

To test everything locally on Docker:

1. **Download the model** into the `models/` directory as shown in Step 2.
2. **Configure Environment Variables**:
   Create a `.env` file in your `backend/` directory:
   ```env
   DB_PASSWORD=localpassword123
   SECRET_KEY=local-dev-secret-key
   FRONTEND_URL=https://localhost
   ```
3. **Build and Start the Containers**:
   Run the following command to build the images and start the local stack:
   ```bash
   docker compose up -d --build
   ```

4. **Verify the Deployment**:
   - Check the status of all containers:
     ```bash
     docker compose ps
     ```
   - Monitor the vLLM logs to ensure the Nemotron model loads successfully:
     ```bash
     docker logs -f cyber-audit-vllm
     ```

5. **Access the System Locally**:
   Navigate to `https://localhost` in your browser. 
   *(Note: Your browser will warn you that the certificate is self-signed/invalid. This is normal for local testing. Click "Advanced" and proceed to the site).*

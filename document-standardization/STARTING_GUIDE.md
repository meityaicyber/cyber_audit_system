# Starting Guide: Running the Pipeline with Qwen3-VL AWQ

This guide details the complete, step-by-step process for running the `report_to_json` pipeline using the **Qwen3-VL-4B-Instruct-AWQ** model on Windows, leveraging an isolated Docker container to bypass native PyTorch hardware support limitations (such as missing kernels for cutting-edge GPUs like Blackwell).

## Prerequisites

1. **Python 3.12** installed on your system.
2. **Docker Desktop** installed and running, with **WSL2** integration and GPU support enabled.

---

## Step 1: Start the vLLM Inference Server (Docker)

To run the highly compressed 4-bit AWQ model smoothly on your GPU, we use `vllm` inside an optimized Linux Docker container. 

Open a PowerShell terminal and run the following command. It mounts your local `models` folder into the container, exposes the server on port 8000, and explicitly defines the quantization method required by Qwen.

```powershell
docker run --runtime nvidia --gpus all `
  -v "E:\Meity Main\document-standardization\document-standardization\models:/models" `
  -p 8000:8000 --ipc=host `
  vllm/vllm-openai:latest /models/Qwen3-VL-4B-Instruct-AWQ-4bit `
  --quantization compressed-tensors `
  --max-model-len 32768
```

> **Note:** Leave this terminal open. Wait until the logs show `Uvicorn running on http://0.0.0.0:8000` before proceeding to the next steps.

---

## Step 2: Setup the Python Environment

Open a **new** PowerShell terminal to set up the client-side Python application.

1. Navigate to the project directory:
   ```powershell
   cd "E:\Meity Main\document-standardization\document-standardization"
   ```

2. Create a virtual environment using Python 3.12 (if you haven't already):
   ```powershell
   py -3.12 -m venv .venv_gpu
   ```

3. Activate the environment:
   ```powershell
   .\.venv_gpu\Scripts\activate
   ```

4. Install the pipeline dependencies:
   ```powershell
   pip install -r requirements.txt
   ```

---

## Step 3: Configure Environment Variables

The Python application needs to know (1) where the vLLM server is running, and (2) what name the vLLM server assigned to the model locally.

In your active PowerShell terminal, set the following environment variables:

```powershell
# Point the pipeline to the local Docker server (Option 1)
$env:R2J_MODEL_ENDPOINT="http://localhost:8000/v1"

# Bridge the naming gap: tell the app the exact model path the server is serving
$env:R2J_QWEN3_VL_4B_INSTRUCT_AWQ_SERVED_NAME="/models/Qwen3-VL-4B-Instruct-AWQ-4bit"
```

---

## Step 4: Launch the Pipeline

With the Docker server running and your environment configured, you are ready to process documents! Run the main application:

```powershell
python -m report_to_json
```

The GUI will launch, and all heavy transcription and structuring work will be securely routed to your GPU-accelerated Docker container.
